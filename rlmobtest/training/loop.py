"""Main training loop: run() and run_all() entry points."""

import logging
from datetime import datetime
from itertools import count
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rlmobtest.android import AndroidEnv
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OutputPaths
from rlmobtest.training.agents import ImprovedAgent, OriginalAgent
from rlmobtest.training.checkpoint import ModelCheckpoint
from rlmobtest.training.device import LongTensor, Tensor
from rlmobtest.training.metrics import TrainingMetrics
from rlmobtest.training.progress import TrainingProgress
from rlmobtest.training.reward import calculate_reward, coverage_reward
from rlmobtest.transcription import transcriber as tm
from rlmobtest.utils.config_reader import AppConfig, ConfRead

console = Console()

# Intervalo (em steps) entre verificações de cobertura JaCoCo.
# Menor = sinal de recompensa mais frequente, maior overhead por verificação.
COVERAGE_CHECK_INTERVAL = 5


def _get_step_coverage(coverage_path: Path, package_name: str) -> dict:
    """Retorna métricas de cobertura JaCoCo atuais sem lançar exceção.

    Retorna {} se não houver arquivos .ec ou se ocorrer erro (ex: jacococli ausente).
    """
    if not coverage_path.exists() or not any(coverage_path.glob("*.ec")):
        return {}
    try:
        from rlmobtest.utils.jacoco import process_coverage

        return process_coverage(coverage_path, package_name, html_report=False) or {}
    except Exception:
        return {}


def setup_logging(run_id: str, logs_path: Path):
    """Setup logging for this specific run."""
    run_log_path = logs_path / f"run_{run_id}.log"

    logger = logging.getLogger(f"rlmobtest_{run_id}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    file_handler = logging.FileHandler(run_log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s", "%H:%M:%S")
    )

    logger.addHandler(file_handler)

    console.print(f"[dim]Log file: {run_log_path}[/dim]")
    return logger, run_log_path


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
        max_steps: Maximum steps per episode (default: 100).
        checkpoint_path: Path to checkpoint file to resume training from.
        config: AppConfig to use. If None, reads from settings.json.
    """
    if config is None:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        settings = config = settings_reader.read_setting()
    else:
        settings = config

    run_id = datetime.now().strftime("%H%M%S")

    paths = OutputPaths(settings.package_name, agent_type=mode)
    paths.create_all()

    run_logger, log_path = setup_logging(run_id, paths.logs)

    if max_time is None and max_episodes is None:
        max_time = settings.time_exploration

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
    console.print("\n[yellow]Initializing Android environment...[/yellow]")
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
    console.print("[green]Environment ready[/green]")

    # Initialize agent
    console.print()
    if mode == "original":
        agent = OriginalAgent(num_actions=30)
        agent_info = Table(show_header=False, box=None)
        agent_info.add_column("", style="cyan")
        agent_info.add_column("")
        agent_info.add_row("Agent", "Original DQN")
        agent_info.add_row("Memory", "ReplayMemory (50,000)")
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
            title="[bold]Agent Configuration[/bold]",
            border_style="green",
        )
    )

    # Training configuration display
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
            title="[bold]Training Configuration[/bold]",
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
        console.print(f"\n[cyan]Loading checkpoint: {checkpoint_path}[/cyan]")
        try:
            model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
            start_episode, agent.steps_done = checkpoint_mgr.load(
                checkpoint_path, model, agent.optimizer
            )
            console.print(
                f"[green]Resumed from episode {start_episode}, step {agent.steps_done}[/green]"
            )
            run_logger.info(
                "Checkpoint loaded: episode=%d, steps=%d", start_episode, agent.steps_done
            )
        except Exception as e:
            console.print(f"[red]Failed to load checkpoint: {e}[/red]")
            run_logger.error("Checkpoint load failed: %s", e)
            raise SystemExit(1)

    progress.start()

    episode = start_episode
    # Cobertura acumulada: persiste entre episódios pois os .ec acumulam na mesma run.
    prev_coverage: dict = {}

    try:
        for _ in count(1):
            episode += 1

            if progress.should_stop(episode):
                break

            progress.update(episode)

            epsilon = agent.get_epsilon()

            metrics.start_episode()
            metrics.print_episode_start(episode, epsilon, agent.steps_done)

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
                req_path = paths.run_path / "requirements.csv"
                env.get_requirements(str(req_path))

            for t in count():
                if len(actions) > 0:
                    if state.shape[3] > state.shape[2]:
                        state = state.permute(0, 1, 3, 2)

                    action, epsilon, q_value = agent.select_action(state, actions)

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

                    if activity not in activities:
                        reward += 10
                        activities.append(activity)
                        metrics.log_activity(activity)
                        console.print(f"   [green]New activity discovered: {activity}[/green]")
                        run_logger.info("New activity: %s", activity)

                    if crash:
                        reward = -5
                        next_state = None
                        run_logger.warning("Crash detected at step %d", t)

                    # Recompensa JaCoCo: bônus por cobertura nova a cada N steps
                    if settings.is_coverage and (t + 1) % COVERAGE_CHECK_INTERVAL == 0:
                        curr_coverage = _get_step_coverage(paths.coverage, settings.package_name)
                        if curr_coverage:
                            cov_r = coverage_reward(prev_coverage, curr_coverage)
                            if cov_r > 0:
                                reward += cov_r
                                episode_reward += cov_r
                                run_logger.debug(
                                    "Coverage reward: +%.2f (Δlines=%.1f%%, Δbranches=%.1f%%)",
                                    cov_r,
                                    curr_coverage.get("line_pct", 0) - prev_coverage.get("line_pct", 0),
                                    curr_coverage.get("branch_pct", 0) - prev_coverage.get("branch_pct", 0),
                                )
                            prev_coverage = curr_coverage

                    reward_tensor = Tensor([reward])
                    agent.memory.push(state, action, next_state, reward_tensor)

                    state = next_state

                    loss = agent.optimize()

                    metrics.log_step(reward, loss, q_value, epsilon)

                    if t % 10 == 0:
                        metrics.print_step(t, reward, q_value, loss, activity_actual, epsilon)
                        progress.update(episode)

                    if crash:
                        console.print(
                            f"   [red]Crash detected! "
                            f"Episode {episode} complete in {t + 1} steps[/red]"
                        )
                        run_logger.info("Episode %d complete in %d steps (crash)", episode, t + 1)
                        break

                    if t + 1 >= max_steps:
                        console.print(
                            f"   [cyan]Step limit reached ({max_steps}). "
                            f"Starting new episode.[/cyan]"
                        )
                        run_logger.info(
                            "Episode %d complete - step limit (%d) reached",
                            episode,
                            max_steps,
                        )
                        break

                    if progress.should_stop(episode):
                        break

                else:
                    console.print("   [yellow]No actions available. Episode interrupted.[/yellow]")
                    run_logger.warning("Episode %d interrupted - no actions", episode)
                    env.tc_action = []
                    break

            # End episode
            episode_duration = (datetime.now() - metrics.episode_start_time).total_seconds()
            metrics.end_episode()
            metrics.print_episode_end(episode, t + 1, episode_reward, episode_duration)

            progress.update(episode)

            if episode % 10 == 0:
                model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
                checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
                metrics.print_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]Training interrupted by user[/yellow]")
        run_logger.info("Training interrupted by user")

    finally:
        progress.stop()

        console.print("\n[cyan]Saving final checkpoint and metrics...[/cyan]")
        model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
        checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
        metrics.save()
        metrics.plot_metrics()

        metrics.print_summary()

        avg_duration = metrics.get_avg_episode_duration()
        if avg_duration > 0:
            console.print(
                Panel(
                    f"[bold]Average Episode Duration:[/bold] [cyan]{avg_duration:.1f}s[/cyan]\n"
                    f"[dim]Use this to estimate training time "
                    f"for a given number of episodes[/dim]",
                    title="Episode Duration Info",
                    border_style="blue",
                )
            )

        if settings.is_req_analysis:
            console.print("\n[cyan]Starting transcription...[/cyan]")
            tm.the_world_is_our(input_folder=paths.test_cases, output_folder=paths.old_transcriptions)

        console.print(f"\n[green]Training complete! Log saved to: {log_path}[/green]")


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
            f"[bold cyan]Multi-APK Training[/bold cyan]\n[dim]{total} app(s) to train[/dim]",
            border_style="cyan",
        )
    )

    for i, cfg in enumerate(configs, 1):
        console.print()
        console.print(f"[bold yellow]=== App {i}/{total}: {cfg.package_name} ===[/bold yellow]")
        console.print()

        try:
            run(
                mode=mode,
                max_time=cfg.time_exploration,
                max_episodes=None,
                max_steps=max_steps,
                checkpoint_path=None,
                config=cfg,
            )
            console.print(f"\n[green]Completed training for {cfg.package_name}[/green]")
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Training interrupted for {cfg.package_name}[/yellow]")
            if i < total:
                console.print("[dim]Remaining apps will not be trained[/dim]")
            raise
        except Exception as e:
            console.print(f"\n[red]Error training {cfg.package_name}: {e}[/red]")
            continue

    console.print()
    console.print(
        Panel.fit("[bold green]Multi-APK training complete[/bold green]", border_style="green")
    )
