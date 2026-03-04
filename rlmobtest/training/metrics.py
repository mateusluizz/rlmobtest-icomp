"""Training metrics tracking, reporting and plotting."""

import json
from collections import deque
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


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
        self.episode_durations = []
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

        episode_duration = (datetime.now() - self.episode_start_time).total_seconds()
        self.episode_durations.append(episode_duration)

        self.episode_rewards.append(self.current_episode_reward)
        self.episode_lengths.append(self.current_episode_steps)

        if self.current_episode_losses:
            self.episode_losses.append(np.mean(self.current_episode_losses))
        if self.current_episode_q_values:
            self.episode_q_values.append(np.mean(self.current_episode_q_values))

        self.episode_activity_counts.append(len(self.current_episode_activities))

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
            f"[bold blue]Episode {episode}[/bold blue] │ "
            f"ε=[magenta]{epsilon:.3f}[/magenta] │ "
            f"Total Steps: [cyan]{total_steps}[/cyan]"
        )
        console.print(f"[bold blue]{'━' * 60}[/bold blue]")

    def print_episode_end(self, episode, steps, reward, duration):
        """Imprime fim de episódio."""
        reward_color = "green" if reward > 0 else "red" if reward < 0 else "white"
        console.print(
            f"[bold]Episode {episode} complete[/bold] │ "
            f"Steps: [cyan]{steps}[/cyan] │ "
            f"Reward: [{reward_color}]{reward:+.0f}[/{reward_color}] │ "
            f"Duration: [yellow]{duration:.1f}s[/yellow]"
        )

    def print_summary(self):
        """Imprime resumo formatado com Rich."""
        s = self.get_summary()

        table = Table(title="Training Summary", show_header=False, border_style="blue")
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
        console.print(f"[green]Metrics saved:[/green] {filepath}")

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
            ax3.plot(
                q_episodes, self.episode_q_values, color="darkcyan", alpha=0.3, label="Q-Value"
            )
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

            lines1, labels1 = ax7.get_legend_handles_labels()
            lines2, labels2 = ax7_twin.get_legend_handles_labels()
            ax7.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
        else:
            ax7.text(0.5, 0.5, "No activity data", ha="center", va="center")
            ax7.set_title("Activity Coverage")

        ax_empty = fig.add_subplot(gs[2, 2])
        ax_empty.set_visible(False)

        filepath = self.plots_path / filename
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()

        console.print(f"[green]Metrics plot saved:[/green] {filepath}")
