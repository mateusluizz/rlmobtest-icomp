#!/usr/bin/env python3
"""
Main entry point for RLMobTest - RL-based Android mobile app testing.

Supports two modes:
- Original DQN (legacy)
- Improved DQN (Double DQN + Dueling + Target Network + PER)

Training can be limited by:
- Time (--time 300 for 5 minutes)
- Episodes (--episodes 100 for 100 episodes)

Usage:
    python main.py                      # Uses improved DQN, time from settings
    python main.py --mode original      # Uses original DQN
    python main.py --time 600           # Train for 10 minutes
    python main.py --episodes 50        # Train for 50 episodes
"""

import json
import logging
import math
import random
import time
from collections import deque, namedtuple
from datetime import datetime
from itertools import count
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from torch import nn, optim

from rlmobtest.android import AndroidEnv
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OutputPaths
from rlmobtest.transcription import transcriber as tm
from rlmobtest.utils.config_reader import AppConfig, ConfRead

# =============================================================================
# CONFIGURATION
# =============================================================================

# Rich console for colored output
console = Console()


def setup_logging(run_id: str, logs_path: Path):
    """Setup logging for this specific run."""
    run_log_path = logs_path / f"run_{run_id}.log"

    # Create a new logger for this run
    logger = logging.getLogger(f"rlmobtest_{run_id}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Don't send logs to console

    # File handler for this run
    file_handler = logging.FileHandler(run_log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s", "%H:%M:%S")
    )

    logger.addHandler(file_handler)

    console.print(f"[dim]Log file: {run_log_path}[/dim]")
    return logger, run_log_path


# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Tensor types for compatibility
FloatTensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if torch.cuda.is_available() else torch.LongTensor
BoolTensor = torch.cuda.BoolTensor if torch.cuda.is_available() else torch.BoolTensor
Tensor = FloatTensor
Transition = namedtuple("Transition", ("state", "action", "next_state", "reward"))


# =============================================================================
# TRAINING METRICS
# =============================================================================


class TrainingMetrics:
    """Sistema de monitoramento e registro de métricas de treinamento com Rich."""

    def __init__(self, save_path: Path, plots_path: Path, run_id: str):
        self.save_path = Path(save_path)
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.plots_path = Path(plots_path)
        self.plots_path.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id

        # Métricas por episódio
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_losses = []
        self.episode_q_values = []
        self.episode_durations = []  # Duração de cada episódio em segundos
        self.epsilon_values = []
        self.episode_activity_counts = []

        # Tracking de activities do episódio atual
        self.current_episode_activities = []

        # Métricas recentes (para médias móveis)
        self.recent_losses = deque(maxlen=1000)
        self.recent_q_values = deque(maxlen=1000)

        # Contadores
        self.total_steps = 0
        self.total_episodes = 0
        self.current_episode_reward = 0
        self.current_episode_steps = 0
        self.current_episode_losses = []
        self.current_episode_q_values = []

        # Timing
        self.start_time = datetime.now()
        self.episode_start_time = datetime.now()

    def log_step(self, reward, loss=None, q_value=None, epsilon=None):
        """Registra métricas de um step."""
        self.total_steps += 1
        self.current_episode_steps += 1
        self.current_episode_reward += reward

        if loss is not None:
            self.recent_losses.append(loss)
            self.current_episode_losses.append(loss)
        if q_value is not None:
            self.recent_q_values.append(q_value)
            self.current_episode_q_values.append(q_value)
        if epsilon is not None:
            self.epsilon_values.append(epsilon)

    def log_activity(self, activity):
        """Registra uma activity visitada no episódio atual."""
        if activity not in self.current_episode_activities:
            self.current_episode_activities.append(activity)

    def start_episode(self):
        """Marca o início de um novo episódio."""
        self.episode_start_time = datetime.now()

    def end_episode(self):
        """Finaliza o episódio atual e calcula métricas."""
        self.total_episodes += 1

        # Calcula duração do episódio
        episode_duration = (datetime.now() - self.episode_start_time).total_seconds()
        self.episode_durations.append(episode_duration)

        # Salva métricas do episódio
        self.episode_rewards.append(self.current_episode_reward)
        self.episode_lengths.append(self.current_episode_steps)

        if self.current_episode_losses:
            self.episode_losses.append(np.mean(self.current_episode_losses))
        if self.current_episode_q_values:
            self.episode_q_values.append(np.mean(self.current_episode_q_values))

        # Salva contagem de activities do episódio
        self.episode_activity_counts.append(len(self.current_episode_activities))

        # Reset para próximo episódio
        self.current_episode_reward = 0
        self.current_episode_steps = 0
        self.current_episode_losses = []
        self.current_episode_q_values = []
        self.current_episode_activities = []

    def get_avg_episode_duration(self):
        """Retorna a duração média de um episódio em segundos."""
        if self.episode_durations:
            return np.mean(self.episode_durations)
        return 0

    def get_summary(self):
        """Retorna resumo das métricas."""
        training_time = datetime.now() - self.start_time
        summary = {
            "run_id": self.run_id,
            "total_episodes": self.total_episodes,
            "total_steps": self.total_steps,
            "training_time": str(training_time),
            "training_time_seconds": training_time.total_seconds(),
            "avg_episode_duration": self.get_avg_episode_duration(),
        }
        if self.episode_rewards:
            summary["avg_reward_last_10"] = float(np.mean(self.episode_rewards[-10:]))
            summary["max_reward"] = float(max(self.episode_rewards))
            summary["min_reward"] = float(min(self.episode_rewards))
        if self.recent_losses:
            summary["current_loss"] = float(np.mean(list(self.recent_losses)[-100:]))
        if self.episode_durations:
            summary["avg_episode_duration"] = float(np.mean(self.episode_durations))
            summary["total_episode_durations"] = self.episode_durations
        return summary

    def print_step(self, step, reward, q_value, loss, activity, epsilon):
        """Imprime log de step com cores."""
        reward_color = "green" if reward > 0 else "red" if reward < 0 else "white"
        loss_str = f"{loss:.4f}" if loss else "N/A"

        console.print(
            f"   [dim]Step {step:3d}[/dim] │ "
            f"R=[{reward_color}]{reward:+5.0f}[/{reward_color}] │ "
            f"Q=[cyan]{q_value:6.2f}[/cyan] │ "
            f"Loss=[yellow]{loss_str}[/yellow] │ "
            f"[dim]{activity[:25]}[/dim]"
        )

    def print_episode_start(self, episode, epsilon, total_steps):
        """Imprime início de episódio."""
        console.print(f"\n[bold blue]{'━' * 60}[/bold blue]")
        console.print(
            f"[bold blue]🎮 Episode {episode}[/bold blue] │ "
            f"ε=[magenta]{epsilon:.3f}[/magenta] │ "
            f"Total Steps: [cyan]{total_steps}[/cyan]"
        )
        console.print(f"[bold blue]{'━' * 60}[/bold blue]")

    def print_episode_end(self, episode, steps, reward, duration):
        """Imprime fim de episódio."""
        reward_color = "green" if reward > 0 else "red" if reward < 0 else "white"
        console.print(
            f"[bold]📍 Episode {episode} complete[/bold] │ "
            f"Steps: [cyan]{steps}[/cyan] │ "
            f"Reward: [{reward_color}]{reward:+.0f}[/{reward_color}] │ "
            f"Duration: [yellow]{duration:.1f}s[/yellow]"
        )

    def print_summary(self):
        """Imprime resumo formatado com Rich."""
        s = self.get_summary()

        # Cria tabela de resumo
        table = Table(title="📊 Training Summary", show_header=False, border_style="blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Episodes", str(s.get("total_episodes", 0)))
        table.add_row("Total Steps", str(s.get("total_steps", 0)))
        table.add_row("Training Time", s.get("training_time", "N/A"))

        if "avg_episode_duration" in s and s["avg_episode_duration"] > 0:
            table.add_row("Avg Episode Duration", f"{s['avg_episode_duration']:.1f}s")

        if "avg_reward_last_10" in s:
            table.add_row("Avg Reward (last 10)", f"{s['avg_reward_last_10']:.2f}")
            table.add_row("Max Reward", f"{s['max_reward']:.2f}")

        if "current_loss" in s:
            table.add_row("Current Loss", f"{s['current_loss']:.4f}")

        console.print()
        console.print(table)
        console.print()

    def save(self, filename=None):
        """Salva métricas em JSON."""
        if filename is None:
            filename = f"metrics_{self.run_id}.json"
        data = {
            "summary": self.get_summary(),
            "episode_rewards": self.episode_rewards,
            "episode_lengths": self.episode_lengths,
            "episode_losses": self.episode_losses,
            "episode_durations": self.episode_durations,
            "episode_q_values": self.episode_q_values,
            "epsilon_values": self.epsilon_values,
            "episode_activity_counts": self.episode_activity_counts,
        }
        filepath = self.save_path / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print("[green]✅ Metrics saved:[/green] %s", filepath)

    def plot_metrics(self, filename=None):
        """Gera gráficos das métricas de treinamento."""
        if len(self.episode_rewards) < 2:
            console.print("[yellow]Not enough data to plot[/yellow]")
            return

        if filename is None:
            filename = f"metrics_{self.run_id}.png"

        fig = plt.figure(figsize=(18, 14))
        gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)
        fig.suptitle(f"Training Metrics - {self.run_id}", fontsize=16, fontweight="bold")

        episodes = range(1, len(self.episode_rewards) + 1)

        # 1. Reward por episódio
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.plot(episodes, self.episode_rewards, "b-", alpha=0.3, label="Reward")
        if len(self.episode_rewards) >= 10:
            window = min(10, len(self.episode_rewards))
            moving_avg = np.convolve(self.episode_rewards, np.ones(window) / window, mode="valid")
            ax1.plot(
                range(window, len(self.episode_rewards) + 1),
                moving_avg,
                "r-",
                linewidth=2,
                label=f"Moving Avg ({window})",
            )
        ax1.set_xlabel("Episode")
        ax1.set_ylabel("Reward")
        ax1.set_title("Episode Rewards")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Loss por episódio
        ax2 = fig.add_subplot(gs[0, 1])
        if self.episode_losses:
            ax2.plot(
                range(1, len(self.episode_losses) + 1),
                self.episode_losses,
                "g-",
                alpha=0.7,
            )
            ax2.set_xlabel("Episode")
            ax2.set_ylabel("Loss")
            ax2.set_title("Training Loss")
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, "No loss data", ha="center", va="center")
            ax2.set_title("Training Loss")

        # 3. Q-Values por episódio
        ax3 = fig.add_subplot(gs[0, 2])
        if self.episode_q_values:
            q_episodes = range(1, len(self.episode_q_values) + 1)
            ax3.plot(q_episodes, self.episode_q_values, color="darkcyan", alpha=0.3, label="Q-Value")
            if len(self.episode_q_values) >= 10:
                window = min(10, len(self.episode_q_values))
                q_moving_avg = np.convolve(
                    self.episode_q_values, np.ones(window) / window, mode="valid"
                )
                ax3.plot(
                    range(window, len(self.episode_q_values) + 1),
                    q_moving_avg,
                    color="teal",
                    linewidth=2,
                    label=f"Moving Avg ({window})",
                )
            ax3.set_xlabel("Episode")
            ax3.set_ylabel("Mean Q-Value")
            ax3.set_title("Q-Values")
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, "No Q-value data", ha="center", va="center")
            ax3.set_title("Q-Values")

        # 4. Duração dos episódios
        ax4 = fig.add_subplot(gs[1, 0])
        if self.episode_durations:
            ax4.bar(
                range(1, len(self.episode_durations) + 1),
                self.episode_durations,
                color="orange",
                alpha=0.7,
            )
            ax4.axhline(
                np.mean(self.episode_durations),
                color="red",
                linestyle="--",
                label=f"Mean: {np.mean(self.episode_durations):.1f}s",
            )
            ax4.set_xlabel("Episode")
            ax4.set_ylabel("Duration (s)")
            ax4.set_title("Episode Duration")
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, "No duration data", ha="center", va="center")
            ax4.set_title("Episode Duration")

        # 5. Reward acumulado
        ax5 = fig.add_subplot(gs[1, 1])
        cumulative_reward = np.cumsum(self.episode_rewards)
        ax5.plot(episodes, cumulative_reward, "purple", linewidth=2)
        ax5.fill_between(episodes, cumulative_reward, alpha=0.3, color="purple")
        ax5.set_xlabel("Episode")
        ax5.set_ylabel("Cumulative Reward")
        ax5.set_title("Cumulative Reward")
        ax5.grid(True, alpha=0.3)

        # 6. Epsilon Decay
        ax6 = fig.add_subplot(gs[1, 2])
        if self.epsilon_values:
            steps = range(1, len(self.epsilon_values) + 1)
            ax6.plot(steps, self.epsilon_values, color="magenta", alpha=0.7, linewidth=1)
            ax6.set_xlabel("Step")
            ax6.set_ylabel("Epsilon")
            ax6.set_title("Epsilon Decay (Exploration Rate)")
            ax6.set_ylim(-0.05, 1.05)
            ax6.grid(True, alpha=0.3)
        else:
            ax6.text(0.5, 0.5, "No epsilon data", ha="center", va="center")
            ax6.set_title("Epsilon Decay (Exploration Rate)")

        # 7. Activity Coverage
        ax7 = fig.add_subplot(gs[2, 0:2])
        if self.episode_activity_counts:
            act_episodes = range(1, len(self.episode_activity_counts) + 1)
            ax7.bar(
                act_episodes,
                self.episode_activity_counts,
                color="mediumseagreen",
                alpha=0.7,
                label="Activities per Episode",
            )

            # Linha cumulativa de activities únicas (eixo secundário)
            ax7_twin = ax7.twinx()
            cumulative_activities = np.cumsum(self.episode_activity_counts)
            ax7_twin.plot(
                act_episodes,
                cumulative_activities,
                color="firebrick",
                linewidth=2,
                marker="o",
                markersize=4,
                label="Cumulative Activities",
            )
            ax7_twin.set_ylabel("Cumulative Activities", color="firebrick")
            ax7_twin.tick_params(axis="y", labelcolor="firebrick")

            ax7.set_xlabel("Episode")
            ax7.set_ylabel("Unique Activities", color="mediumseagreen")
            ax7.tick_params(axis="y", labelcolor="mediumseagreen")
            ax7.set_title("Activity Coverage")
            ax7.grid(True, alpha=0.3)

            # Legenda combinada
            lines1, labels1 = ax7.get_legend_handles_labels()
            lines2, labels2 = ax7_twin.get_legend_handles_labels()
            ax7.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
        else:
            ax7.text(0.5, 0.5, "No activity data", ha="center", va="center")
            ax7.set_title("Activity Coverage")

        # Ocultar subplot vazio (2, 2)
        ax_empty = fig.add_subplot(gs[2, 2])
        ax_empty.set_visible(False)

        # Salva o gráfico na pasta plots
        filepath = self.plots_path / filename
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()

        console.print(f"[green]📊 Metrics plot saved:[/green] {filepath}")


# =============================================================================
# MODEL CHECKPOINT
# =============================================================================


class ModelCheckpoint:
    """Gerenciador de checkpoints."""

    def __init__(self, save_dir: Path):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save(self, model, optimizer, metrics, episode, steps_done, filename=None):
        if filename is None:
            filename = f"checkpoint_ep{episode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"

        checkpoint = {
            "episode": episode,
            "steps_done": steps_done,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "metrics": {
                "episode_rewards": metrics.episode_rewards,
                "episode_lengths": metrics.episode_lengths,
            },
            "timestamp": datetime.now().isoformat(),
            "feature_size": getattr(model, "_feature_size", None),
        }

        filepath = self.save_dir / filename
        torch.save(checkpoint, filepath)
        print(f"✅ Checkpoint saved: {filepath.name}")
        return filepath

    def load(self, filepath, model, optimizer):
        checkpoint = torch.load(filepath, map_location=device)

        # Initialize lazy layers before loading state dict (for DuelingDQN)
        if hasattr(model, "_initialize_fc") and model.value_stream is None:
            feature_size = checkpoint.get("feature_size")
            # Fallback: infer feature_size from saved weights
            if feature_size is None:
                state_dict = checkpoint["model_state_dict"]
                if "value_stream.0.weight" in state_dict:
                    feature_size = state_dict["value_stream.0.weight"].shape[1]
            if feature_size is not None:
                model._feature_size = feature_size
                model._initialize_fc(feature_size)

        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        print(f"✅ Checkpoint loaded: {filepath}")
        return checkpoint["episode"], checkpoint["steps_done"]


# =============================================================================
# REPLAY MEMORY
# =============================================================================


class ReplayMemory:
    """Experience replay memory padrão."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, state, action, next_state, reward):
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = (state, action, next_state, reward)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


class PrioritizedReplayMemory:
    """Experience Replay com priorização baseada em TD-error."""

    def __init__(self, capacity, alpha=0.6, beta_start=0.4, beta_frames=100000):
        self.capacity = capacity
        self.alpha = alpha
        self.beta_start = beta_start
        self.beta_frames = beta_frames
        self.frame = 1
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0

    def push(self, state, action, next_state, reward):
        max_priority = self.priorities.max() if self.buffer else 1.0

        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, next_state, reward))
        else:
            self.buffer[self.position] = (state, action, next_state, reward)

        self.priorities[self.position] = max_priority
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        if len(self.buffer) == 0:
            return [], [], None

        priorities = self.priorities[: len(self.buffer)]
        probs = priorities**self.alpha
        probs /= probs.sum()

        beta = min(
            1.0,
            self.beta_start + self.frame * (1.0 - self.beta_start) / self.beta_frames,
        )
        self.frame += 1

        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        samples = [self.buffer[i] for i in indices]

        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights /= weights.max()
        weights = torch.tensor(weights, dtype=torch.float32, device=device)

        return samples, indices, weights

    def update_priorities(self, indices, td_errors):
        for idx, td_error in zip(indices, td_errors):
            self.priorities[idx] = abs(td_error) + 1e-6

    def __len__(self):
        return len(self.buffer)


# =============================================================================
# DQN MODELS
# =============================================================================


class OriginalDQN(nn.Module):
    """DQN original do projeto."""

    def __init__(self, num_actions=30):
        super(OriginalDQN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, num_actions)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = x.view(x.size(0), -1)
        return self.head(x)


class DuelingDQN(nn.Module):
    """Dueling DQN - separa Value e Advantage streams."""

    def __init__(self, num_actions=30):
        super(DuelingDQN, self).__init__()

        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ReLU(),
        )

        self._feature_size = None
        self.num_actions = num_actions
        self.value_stream = None
        self.advantage_stream = None

    def _initialize_fc(self, feature_size):
        self.value_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, 1)
        ).to(device)

        self.advantage_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, self.num_actions)
        ).to(device)

    def forward(self, x):
        features = self.features(x)
        features = features.view(features.size(0), -1)

        if self.value_stream is None:
            self._feature_size = features.size(1)
            self._initialize_fc(self._feature_size)

        value = self.value_stream(features)
        advantage = self.advantage_stream(features)
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        return q_values


# =============================================================================
# DQN AGENTS
# =============================================================================


class OriginalAgent:
    """Agente DQN original (compatibilidade com código legado)."""

    def __init__(self, num_actions=30):
        self.num_actions = num_actions
        self.model = OriginalDQN(num_actions).to(device)
        self.model.type(FloatTensor)

        self.memory = ReplayMemory(10000)
        self.optimizer = optim.RMSprop(self.model.parameters())

        self.batch_size = 256
        self.gamma = 0.999
        self.eps_start = 0.9
        self.eps_end = 0.05
        self.eps_decay = 500

        self.steps_done = 0

    def get_epsilon(self):
        return self.eps_end + (self.eps_start - self.eps_end) * math.exp(
            -1.0 * self.steps_done / self.eps_decay
        )

    def select_action(self, state, actions):
        epsilon = self.get_epsilon()
        self.steps_done += 1

        if random.random() > epsilon:
            with torch.no_grad():
                vals = self.model(state.type(FloatTensor)).data[0]
                max_idx = vals[: len(actions)].max(0)[1]
                return LongTensor([[max_idx]]), epsilon, vals.max().item()
        else:
            n = min(len(actions), 29)
            return LongTensor([[random.randrange(n)]]), epsilon, 0.0

    def optimize(self):
        if len(self.memory) < self.batch_size:
            return None

        transitions = self.memory.sample(self.batch_size)
        batch = list(zip(*transitions))

        non_final_mask = BoolTensor(tuple(map(lambda s: s is not None, batch[2])))
        non_final_next_states = torch.cat([s for s in batch[2] if s is not None]).type(FloatTensor)

        state_batch = torch.cat(batch[0]).type(FloatTensor)
        action_batch = torch.cat(batch[1])
        reward_batch = torch.cat(batch[3])

        if torch.cuda.is_available():
            state_batch = state_batch.cuda()
            action_batch = action_batch.cuda()

        state_action_values = self.model(state_batch).gather(1, action_batch)

        next_state_values = torch.zeros(self.batch_size).type(Tensor)
        next_state_values[non_final_mask] = self.model(non_final_next_states).max(1)[0]

        expected_state_action_values = (next_state_values * self.gamma) + reward_batch

        state_action_values = state_action_values.view(self.batch_size)
        loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)

        self.optimizer.zero_grad()
        loss.backward()
        for param in self.model.parameters():
            param.grad.data.clamp_(-1, 1)
        self.optimizer.step()

        return loss.item()


class ImprovedAgent:
    """Agente DQN melhorado com Double DQN, Target Network, Dueling e PER."""

    def __init__(self, num_actions=30, use_dueling=True, use_per=True):
        self.num_actions = num_actions
        self.use_per = use_per

        # Redes: policy e target
        ModelClass = DuelingDQN if use_dueling else OriginalDQN
        self.policy_net = ModelClass(num_actions).to(device)
        self.target_net = ModelClass(num_actions).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=1e-4)

        if use_per:
            self.memory = PrioritizedReplayMemory(50000)
        else:
            self.memory = ReplayMemory(50000)

        # Hiperparâmetros melhorados
        self.batch_size = 128
        self.gamma = 0.99
        self.eps_start = 1.0
        self.eps_end = 0.01
        self.eps_decay = 10000
        self.target_update = 1000

        self.steps_done = 0

    def get_epsilon(self):
        return self.eps_end + (self.eps_start - self.eps_end) * math.exp(
            -1.0 * self.steps_done / self.eps_decay
        )

    def select_action(self, state, actions):
        epsilon = self.get_epsilon()
        self.steps_done += 1

        if random.random() > epsilon:
            with torch.no_grad():
                state = state.to(device)
                q_values = self.policy_net(state)
                q_values = q_values[0, : len(actions)]
                action_idx = q_values.argmax().item()
                return LongTensor([[action_idx]]), epsilon, q_values.max().item()
        else:
            n = min(len(actions), self.num_actions - 1)
            return LongTensor([[random.randrange(n)]]), epsilon, 0.0

    def optimize(self):
        if len(self.memory) < self.batch_size:
            return None

        # Amostrar batch
        if self.use_per:
            samples, indices, weights = self.memory.sample(self.batch_size)
            if not samples:
                return None
        else:
            samples = self.memory.sample(self.batch_size)
            indices = None
            weights = torch.ones(self.batch_size, device=device)

        batch = list(zip(*samples))

        state_batch = torch.cat([s for s in batch[0] if s is not None]).to(device)
        action_batch = torch.cat(batch[1]).to(device)
        reward_batch = torch.cat(batch[3]).to(device)

        non_final_mask = torch.tensor(
            [s is not None for s in batch[2]], device=device, dtype=torch.bool
        )
        non_final_next_states = (
            torch.cat([s for s in batch[2] if s is not None]).to(device)
            if any(non_final_mask)
            else None
        )

        # Q(s, a) da policy network
        state_action_values = self.policy_net(state_batch).gather(1, action_batch)

        # Double DQN
        next_state_values = torch.zeros(self.batch_size, device=device)
        if non_final_next_states is not None:
            with torch.no_grad():
                next_actions = self.policy_net(non_final_next_states).argmax(1).unsqueeze(1)
                next_state_values[non_final_mask] = (
                    self.target_net(non_final_next_states).gather(1, next_actions).squeeze()
                )

        expected_state_action_values = reward_batch + (self.gamma * next_state_values)

        # TD-errors para PER
        td_errors = (
            (state_action_values.squeeze() - expected_state_action_values).detach().cpu().numpy()
        )

        # Weighted loss
        loss = (
            weights
            * F.smooth_l1_loss(
                state_action_values.squeeze(),
                expected_state_action_values,
                reduction="none",
            )
        ).mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10)
        self.optimizer.step()

        # Atualizar prioridades
        if self.use_per and indices is not None:
            self.memory.update_priorities(indices, td_errors)

        # Atualizar target network
        if self.steps_done % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()


# =============================================================================
# REWARD CALCULATION
# =============================================================================


def calculate_reward(
    current_action,
    previous_action,
    activity,
    previous_activity,
    activities,
    crash,
    req_enabled,
    env,
    actions,
):
    """Calcula a recompensa baseada na transição."""
    reward = 0

    # Penalidade por repetir ação
    if torch.equal(current_action, previous_action):
        reward = -2
    else:
        reward += 1

    # Verificar happy path ou ação
    if req_enabled:
        reward_path = env.get_happypath(actions[current_action[0][0]])
    else:
        reward_path = env.verify_action(actions[current_action[0][0]])

    # Adiciona reward do path (se houver)
    if reward_path != 0:
        reward += reward_path

    # Mudança de activity
    if activity != previous_activity:
        if activity not in {"home", "outapp"}:
            reward += 5
        else:
            reward -= 5

    # Nova activity descoberta
    if activity not in activities:
        reward += 10

    # Crash
    if crash:
        reward = -5

    return reward


# =============================================================================
# TRAINING LOOP
# =============================================================================


class TrainingProgress:
    """Gerenciador de progresso do treinamento com Rich."""

    def __init__(self, max_time: int | None = None, max_episodes: int | None = None):
        self.max_time = max_time
        self.max_episodes = max_episodes
        self.start_time = time.time()
        self.mode = "time" if max_time else "episodes"

        # Cria barra de progresso apropriada
        if self.mode == "time":
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("/"),
                TextColumn(f"[cyan]{self._format_time(max_time)}[/cyan]"),
                console=console,
            )
            self.task = None
        else:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                console=console,
            )
            self.task = None

    def _format_time(self, seconds):
        """Formata segundos para mm:ss ou hh:mm:ss."""
        if seconds < 3600:
            return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def start(self):
        """Inicia a barra de progresso."""
        self.progress.start()
        if self.mode == "time":
            self.task = self.progress.add_task("Training", total=self.max_time)
        else:
            self.task = self.progress.add_task("Training", total=self.max_episodes)

    def update(self, episode=None):
        """Atualiza o progresso."""
        if self.mode == "time":
            elapsed = time.time() - self.start_time
            self.progress.update(self.task, completed=min(elapsed, self.max_time))
        else:
            self.progress.update(self.task, completed=episode)

    def should_stop(self, episode):
        """Verifica se deve parar o treinamento."""
        if self.mode == "time":
            return (time.time() - self.start_time) >= self.max_time
        else:
            return episode >= self.max_episodes

    def stop(self):
        """Para a barra de progresso."""
        self.progress.stop()

    def get_elapsed(self):
        """Retorna tempo decorrido em segundos."""
        return time.time() - self.start_time


def run(
    mode="improved",
    max_time: int | None = None,
    max_episodes: int | None = None,
    max_steps: int = 100,
    checkpoint_path: Path | None = None,
    config: AppConfig | None = None,
):
    """
    Execute the RL agent training loop.

    Args:
        mode: "original" or "improved"
        max_time: Maximum training time in seconds (mutually exclusive with max_episodes)
        max_episodes: Maximum number of episodes (mutually exclusive with max_time)
        max_steps: Maximum steps per episode (default: 100). Limits how long each
            episode can run. Without this limit, episodes only end on crash,
            no actions, or total time limit - which can lead to very long episodes.
            A typical value of 100 steps ensures regular episode resets and
            better exploration.
        checkpoint_path: Path to checkpoint file to resume training from.
        config: AppConfig to use. If None, reads from settings.json.
    """
    # Use provided config or read from settings file
    if config is None:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        settings = config = settings_reader.read_setting()
    else:
        settings = config

    # Generate unique run ID (timestamp only, date is in folder structure)
    run_id = datetime.now().strftime("%H%M%S")

    # Create output paths: output/{apk_name}/{agent_type}/{year}/{month}/{day}/
    paths = OutputPaths(settings.package_name, agent_type=mode)
    paths.create_all()

    # Setup logging for this run
    run_logger, log_path = setup_logging(run_id, paths.logs)

    # Determine training limit
    if max_time is None and max_episodes is None:
        max_time = settings.time

    training_mode = "time" if max_time else "episodes"
    training_limit = max_time if max_time else max_episodes

    # Print header
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]RLMobTest Training[/bold cyan]\n[dim]Run ID: {run_id}[/dim]",
            border_style="blue",
        )
    )

    # Initialize environment
    console.print("\n[yellow]📱 Initializing Android environment...[/yellow]")
    env = AndroidEnv(
        settings.apk_name,
        settings.package_name,
        coverage_enabled=settings.is_coverage,
        max_same_activity=30,
        test_case_path=paths.test_cases,
        screenshots_path=paths.screenshots,
        crashes_path=paths.crashes,
        errors_path=paths.errors,
        coverage_path=paths.coverage,
    )
    env.install_app()
    console.print("[green]✓ Environment ready[/green]")

    # Initialize agent based on mode
    console.print()
    if mode == "original":
        agent = OriginalAgent(num_actions=30)
        agent_info = Table(show_header=False, box=None)
        agent_info.add_column("", style="cyan")
        agent_info.add_column("")
        agent_info.add_row("Agent", "Original DQN")
        agent_info.add_row("Memory", "ReplayMemory (10,000)")
        agent_info.add_row("Gamma", str(agent.gamma))
        agent_info.add_row("Epsilon Decay", str(agent.eps_decay))
    else:
        agent = ImprovedAgent(num_actions=30, use_dueling=True, use_per=True)
        agent_info = Table(show_header=False, box=None)
        agent_info.add_column("", style="cyan")
        agent_info.add_column("")
        agent_info.add_row("Agent", "Improved DQN (Double + Dueling)")
        agent_info.add_row("Memory", "PrioritizedReplayMemory (50,000)")
        agent_info.add_row("Gamma", str(agent.gamma))
        agent_info.add_row("Target Update", f"every {agent.target_update} steps")

    console.print(
        Panel(
            agent_info,
            title="[bold]🤖 Agent Configuration[/bold]",
            border_style="green",
        )
    )

    # Training configuration
    train_info = Table(show_header=False, box=None)
    train_info.add_column("", style="cyan")
    train_info.add_column("")
    train_info.add_row("Mode", training_mode.capitalize())
    if training_mode == "time":
        train_info.add_row("Duration", f"{training_limit} seconds ({training_limit // 60} min)")
    else:
        train_info.add_row("Episodes", str(training_limit))
    train_info.add_row("Max Steps/Episode", str(max_steps))
    train_info.add_row("App Package", settings.package_name)
    train_info.add_row("Requirements", "Enabled" if settings.is_req_analysis else "Disabled")
    train_info.add_row("Output Path", str(paths.run_path))

    console.print(
        Panel(
            train_info,
            title="[bold]⚙️ Training Configuration[/bold]",
            border_style="yellow",
        )
    )
    console.print()

    # Initialize metrics, checkpoints, and progress
    metrics = TrainingMetrics(save_path=paths.metrics, plots_path=paths.plots, run_id=run_id)
    checkpoint_mgr = ModelCheckpoint(save_dir=paths.checkpoints)
    progress = TrainingProgress(max_time=max_time, max_episodes=max_episodes)

    # Load checkpoint if provided
    start_episode = 0
    if checkpoint_path:
        console.print(f"\n[cyan]📂 Loading checkpoint: {checkpoint_path}[/cyan]")
        try:
            model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
            start_episode, agent.steps_done = checkpoint_mgr.load(
                checkpoint_path, model, agent.optimizer
            )
            console.print(
                f"[green]✓ Resumed from episode {start_episode}, step {agent.steps_done}[/green]"
            )
            run_logger.info(
                "Checkpoint loaded: episode=%d, steps=%d", start_episode, agent.steps_done
            )
        except Exception as e:
            console.print(f"[red]❌ Failed to load checkpoint: {e}[/red]")
            run_logger.error("Checkpoint load failed: %s", e)
            raise SystemExit(1)

    # Start progress bar
    progress.start()

    episode = start_episode

    try:
        for _ in count(1):
            episode += 1

            # Check if should stop
            if progress.should_stop(episode):
                break

            # Update progress
            progress.update(episode)

            epsilon = agent.get_epsilon()

            # Start episode timing
            metrics.start_episode()
            metrics.print_episode_start(episode, epsilon, agent.steps_done)

            # Log to file
            run_logger.info(
                "Episode %d started | epsilon=%.3f | steps=%d",
                episode,
                epsilon,
                agent.steps_done,
            )

            # Initialize episode
            previous_action = LongTensor([[0]])
            state, actions = env.reset()
            activity_actual = env.first_activity
            previous_activity = activity_actual
            activities = [activity_actual]
            metrics.log_activity(activity_actual)
            env.nametc = env._create_tcfile(activity_actual)
            episode_reward = 0

            if settings.is_req_analysis:
                env.get_requirements()

            for t in count():
                if len(actions) > 0:
                    # Handle landscape mode
                    if state.shape[3] > state.shape[2]:
                        state = state.permute(0, 1, 3, 2)

                    # Select action
                    action, epsilon, q_value = agent.select_action(state, actions)

                    # Calculate reward
                    reward = calculate_reward(
                        action,
                        previous_action,
                        activity_actual,
                        previous_activity,
                        activities,
                        False,
                        settings.is_req_analysis,
                        env,
                        actions,
                    )
                    previous_action = action
                    episode_reward += reward

                    # Execute action
                    next_state, actions, crash, activity = env.step(actions[action[0][0]])

                    if next_state is not None and next_state.shape[3] > next_state.shape[2]:
                        next_state = next_state.permute(0, 1, 3, 2)

                    run_logger.debug(
                        "Step %d | action=%d | reward=%d | activity=%s",
                        t,
                        action[0][0],
                        reward,
                        activity,
                    )

                    # Handle activity change
                    if activity_actual != activity:
                        previous_activity = activity_actual
                        activity_actual = activity
                        env.copy_coverage()

                        if activity in {"home", "outapp"}:
                            env.device.press("back")
                            env._get_foreground()
                            reward = -5

                        with open(
                            f"{paths.test_cases.as_posix()}/{env.nametc}",
                            mode="a",
                            encoding="utf-8",
                        ) as file:
                            file.write(f"\n\nGo to next activity: {activity}")
                        env.nametc = env._create_tcfile(activity)
                        env.tc_action = []

                    # New activity bonus
                    if activity not in activities:
                        reward += 10
                        activities.append(activity)
                        metrics.log_activity(activity)
                        console.print(f"   [green]✨ New activity discovered: {activity}[/green]")
                        run_logger.info("New activity: %s", activity)

                    # Crash handling
                    if crash:
                        reward = -5
                        next_state = None
                        run_logger.warning("Crash detected at step %d", t)

                    # Store transition
                    reward_tensor = Tensor([reward])
                    agent.memory.push(state, action, next_state, reward_tensor)

                    # Update state
                    state = next_state

                    # Optimize model
                    loss = agent.optimize()

                    # Log metrics
                    metrics.log_step(reward, loss, q_value, epsilon)

                    # Log step progress (every 10 steps)
                    if t % 10 == 0:
                        metrics.print_step(t, reward, q_value, loss, activity_actual, epsilon)
                        # Update progress bar (for time-based training)
                        progress.update(episode)

                    if crash:
                        console.print(
                            f"   [red]💥 Crash detected! "
                            f"Episode {episode} complete in {t + 1} steps[/red]"
                        )
                        run_logger.info("Episode %d complete in %d steps (crash)", episode, t + 1)
                        break

                    # Check step limit per episode
                    if t + 1 >= max_steps:
                        console.print(
                            f"   [cyan]🔄 Step limit reached ({max_steps})."
                            f"Starting new episode.[/cyan]"
                        )
                        run_logger.info(
                            "Episode {episode} complete - step limit (%d) reached",
                            max_steps,
                        )
                        break

                    # Check if should stop (for time-based training)
                    if progress.should_stop(episode):
                        break

                else:
                    console.print(
                        "   [yellow]⚠️ No actions available. Episode interrupted.[/yellow]"
                    )
                    run_logger.warning(f"Episode {episode} interrupted - no actions")
                    env.tc_action = []
                    break

            # End episode
            episode_duration = (datetime.now() - metrics.episode_start_time).total_seconds()
            metrics.end_episode()
            metrics.print_episode_end(episode, t + 1, episode_reward, episode_duration)

            # Update progress
            progress.update(episode)

            # Periodic checkpoint and summary (every 10 episodes)
            if episode % 10 == 0:
                model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
                checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
                metrics.print_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Training interrupted by user[/yellow]")
        run_logger.info("Training interrupted by user")

    finally:
        # Stop progress bar
        progress.stop()

        # Save final checkpoint and metrics
        console.print("\n[cyan]💾 Saving final checkpoint and metrics...[/cyan]")
        model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
        checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
        metrics.save()
        metrics.plot_metrics()

        # Print final summary
        metrics.print_summary()

        # Show episode duration info
        avg_duration = metrics.get_avg_episode_duration()
        if avg_duration > 0:
            console.print(
                Panel(
                    f"[bold]Average Episode Duration:[/bold] [cyan]{avg_duration:.1f}s[/cyan]\n"
                    f"[dim]Use this to estimate training time"
                    f"for a given number of episodes[/dim]",
                    title="📊 Episode Duration Info",
                    border_style="blue",
                )
            )

        # Execute transcription
        console.print("\n[cyan]📝 Starting transcription...[/cyan]")
        tm.the_world_is_our(input_folder=paths.test_cases, output_folder=paths.transcriptions)

        console.print(f"\n[green]✅ Training complete! Log saved to: {log_path}[/green]")


# =============================================================================
# MAIN
# =============================================================================


def run_all(
    configs: list[AppConfig],
    mode: str = "improved",
    max_steps: int = 100,
):
    """
    Run training for multiple APKs sequentially.

    Args:
        configs: List of AppConfig to train.
        mode: "original" or "improved"
        max_steps: Maximum steps per episode.
    """
    total = len(configs)
    console.print(
        Panel.fit(
            f"[bold cyan]Multi-APK Training[/bold cyan]\n"
            f"[dim]{total} app(s) to train[/dim]",
            border_style="cyan",
        )
    )

    for i, config in enumerate(configs, 1):
        console.print()
        console.print(
            f"[bold yellow]═══ App {i}/{total}: {config.package_name} ═══[/bold yellow]"
        )
        console.print()

        try:
            run(
                mode=mode,
                max_time=config.time,
                max_episodes=None,
                max_steps=max_steps,
                checkpoint_path=None,
                config=config,
            )
            console.print(f"\n[green]✓ Completed training for {config.package_name}[/green]")
        except KeyboardInterrupt:
            console.print(f"\n[yellow]⚠ Training interrupted for {config.package_name}[/yellow]")
            if i < total:
                console.print("[dim]Remaining apps will not be trained[/dim]")
            raise
        except Exception as e:
            console.print(f"\n[red]✗ Error training {config.package_name}: {e}[/red]")
            continue

    console.print()
    console.print(Panel.fit("[bold green]Multi-APK training complete[/bold green]", border_style="green"))


def main():
    """Main entry point - delegates to CLI."""
    from rlmobtest.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
