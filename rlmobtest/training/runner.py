import re
import time
from datetime import datetime
from itertools import count
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from rlmobtest.android import AndroidEnv
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OutputPaths
from rlmobtest.training.agents import ImprovedAgent, OriginalAgent
from rlmobtest.training.checkpoint import ModelCheckpoint
from rlmobtest.training.constants import LongTensor, Tensor
from rlmobtest.training.metrics import TrainingMetrics, console, setup_logging
from rlmobtest.training.progress import TrainingProgress
from rlmobtest.training.reward import calculate_functional_reward, calculate_reward
from rlmobtest.transcription import transcriber as tm
from rlmobtest.utils.config_reader import AppConfig, ConfRead


def _extract_resource_ids(xml_content: str) -> list:
    """Extract non-empty resource-id values from a uiautomator XML dump string."""
    if not xml_content:
        return []
    return [m.group(1) for m in re.finditer(r'resource-id="([^"]+)"', xml_content) if m.group(1)]


# ─────────────────────────────────────────────────────────────────────────────
# Rich UI helpers for multi-phase pipeline
# ─────────────────────────────────────────────────────────────────────────────

_PHASE_META = {
    "0a": ("📋", "APK Manifest Parser", "blue"),
    "0b": ("🕷️ ", "Semantic Crawling", "cyan"),
    "0c": ("🔥", "Replay Memory Warmup", "magenta"),
    "1":  ("🤖", "RL Training", "green"),
    "2":  ("📝", "Enriched Transcription", "yellow"),
}
_ALL_PHASES = ["0a", "0b", "0c", "1", "2"]


def _phase_header(phase_id: str, skip_phases: list) -> float:
    """Print a rich Rule header for the phase and return the start timestamp."""
    icon, name, color = _PHASE_META.get(phase_id, ("▶", phase_id, "white"))
    step = _ALL_PHASES.index(phase_id) + 1
    total = len(_ALL_PHASES)

    # Pipeline breadcrumb: dim past, bold+color current, dim future
    # Use \[ \] to produce literal brackets in Rich output (avoids tag parsing).
    crumbs = []
    for pid in _ALL_PHASES:
        skipped = pid in skip_phases
        if pid == phase_id:
            # Current phase: bold + color, literal brackets around id
            crumbs.append(f"[bold {color}]\\[{pid}\\][/bold {color}]")
        elif _ALL_PHASES.index(pid) < _ALL_PHASES.index(phase_id):
            # Past phases: dim with parentheses
            crumbs.append(f"[dim]–{pid}–[/dim]" if skipped else f"[dim]({pid})[/dim]")
        else:
            # Future phases: plain dim
            crumbs.append(f"[dim]{pid}[/dim]")
    breadcrumb = " → ".join(crumbs)

    console.print()
    console.rule(
        f"[bold {color}]{icon}  Phase {phase_id} · {name}[/bold {color}]"
        f"  [dim]{step}/{total}[/dim]",
        style=color,
    )
    console.print(f"  {breadcrumb}")
    console.print()
    return time.time()


def _phase_ok(phase_id: str, t0: float, details: str) -> None:
    """Print a compact success line after a phase completes."""
    elapsed = time.time() - t0
    _, name, color = _PHASE_META.get(phase_id, ("▶", phase_id, "white"))
    console.print(
        f"  [bold {color}]✓[/bold {color}] Phase {phase_id} complete  "
        f"[dim]{elapsed:.1f}s[/dim]  │  {details}"
    )


def _phase_skip(phase_id: str, reason: str = "") -> None:
    """Print a dim skip line for a phase that was not executed."""
    label = f"Phase {phase_id} skipped"
    if reason:
        label += f" ({reason})"
    console.print(f"  [dim]⊘  {label}[/dim]")


def _phase_fail(phase_id: str, t0: float, exc: Exception) -> None:
    """Print a warning line for a non-fatal phase failure."""
    elapsed = time.time() - t0
    console.print(
        f"  [bold yellow]⚠[/bold yellow]  Phase {phase_id} failed "
        f"[dim]{elapsed:.1f}s[/dim]  │  [yellow]{exc}[/yellow]"
    )


def _pipeline_summary(statuses: dict) -> None:
    """Print a final pipeline status table."""
    table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
    table.add_column("Phase", style="bold")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("Key Output")

    for pid in _ALL_PHASES:
        icon, name, _ = _PHASE_META[pid]
        s = statuses.get(pid, {})
        status_str = s.get("status", "skipped")
        duration = s.get("duration", "")
        detail = s.get("detail", "—")

        if status_str == "ok":
            badge = "[bold green]✓ completed[/bold green]"
        elif status_str == "failed":
            badge = "[bold yellow]⚠ failed[/bold yellow]"
        else:
            badge = "[dim]⊘ skipped[/dim]"

        table.add_row(f"{icon} {pid}", name, badge, duration, detail)

    console.print()
    console.rule("[bold]Pipeline Summary[/bold]", style="dim")
    console.print(table)
    console.print()


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

    for i, config in enumerate(configs, 1):
        console.print()
        console.print(f"[bold yellow]═══ App {i}/{total}: {config.package_name} ═══[/bold yellow]")
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
    console.print(
        Panel.fit("[bold green]Multi-APK training complete[/bold green]", border_style="green")
    )


def run_with_phases(
    mode: str = "improved",
    max_time: int | None = None,
    max_episodes: int | None = None,
    max_steps: int = 100,
    config: AppConfig | None = None,
    skip_phases: list | None = None,
    llm_model: str = "ollama/gemma3:8b",
    llm_base_url: str = "http://localhost:11434",
) -> Path | None:
    """
    Execute the multi-phase RL testing pipeline with observability and coverage metrics.

    Phases:
        0a - APK manifest parsing (discovers all declared activities)
        0b - Semantic crawling + LLM annotation (skip with skip_phases=['0b'])
        0c - Replay memory warmup from crawl (skip with skip_phases=['0c'])
        1  - RL training with live coverage tracking
        2  - Enriched test-case transcription with semantic context

    Returns:
        Path to the generated HTML report, or None if report generation failed.
    """
    if skip_phases is None:
        skip_phases = []

    # ── Config ────────────────────────────────────────────────────────────────
    if config is None:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        settings = config = settings_reader.read_setting()
    else:
        settings = config

    run_id = datetime.now().strftime("%H%M%S")

    # Use a distinct agent_type folder so phases runs don't mix with plain runs
    paths = OutputPaths(settings.package_name, agent_type=f"{mode}_phases")
    paths.create_all()

    run_logger, log_path = setup_logging(run_id, paths.logs)

    if max_time is None and max_episodes is None:
        max_time = settings.time

    _statuses: dict = {}
    skip_label = ", ".join(skip_phases) if skip_phases else "none"
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]RLMobTest — Multi-Phase Pipeline[/bold cyan]\n"
            f"[dim]Run ID: [bold]{run_id}[/bold]  │  App: {settings.package_name}"
            f"  │  Mode: {mode}  │  Skip: {skip_label}[/dim]",
            border_style="blue",
            padding=(0, 2),
        )
    )

    # ── Observability + Coverage ───────────────────────────────────────────────
    from rlmobtest.metrics.coverage_tracker import CoverageTracker
    from rlmobtest.metrics.phase_observer import PhaseObserver

    observer = PhaseObserver(run_id, paths.phase_reports)

    # ── Environment ───────────────────────────────────────────────────────────
    console.print()
    console.rule("[dim]Setup[/dim]", style="dim")
    console.print("[yellow]📱 Initializing Android environment...[/yellow]")
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
    console.print()

    # ── Agent ─────────────────────────────────────────────────────────────────
    if mode == "original":
        agent = OriginalAgent(num_actions=30)
    else:
        agent = ImprovedAgent(num_actions=30, use_dueling=True, use_per=True)

    # ── Phase 0a: Manifest Parsing ─────────────────────────────────────────────
    manifest = None
    if "0a" not in skip_phases:
        _t0 = _phase_header("0a", skip_phases)
        observer.begin_phase("0a", "APK Manifest Parsing", {"apk": settings.apk_name})
        try:
            from rlmobtest.phases.phase_0a_manifest import parse_manifest

            manifest = parse_manifest(
                Path(settings.apk_name), observer, package_name=settings.package_name
            )
            observer.end_phase(
                "0a",
                {
                    "activities": len(manifest.activities),
                    "launcher": manifest.launcher_activity,
                    "package": manifest.package,
                },
            )
            _detail = (
                f"{len(manifest.activities)} activities  │  "
                f"{len(manifest.exported_activities)} navigable  │  "
                f"launcher: [bold]{manifest.launcher_activity or '?'}[/bold]"
            )
            _phase_ok("0a", _t0, _detail)
            _statuses["0a"] = {
                "status": "ok",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": (
                    f"{len(manifest.activities)} activities, "
                    f"{len(manifest.exported_activities)} navigable"
                ),
            }
        except Exception as exc:
            observer.fail_phase("0a", exc)
            _phase_fail("0a", _t0, exc)
            run_logger.warning("Phase 0a failed: %s", exc)
            _statuses["0a"] = {
                "status": "failed",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": str(exc),
            }
    else:
        _phase_skip("0a")
        _statuses["0a"] = {"status": "skipped", "duration": "—", "detail": "—"}

    coverage_tracker = CoverageTracker(manifest=manifest)

    # ── Phase 0b: Semantic Crawling ────────────────────────────────────────────
    crawl_result = None
    if "0b" not in skip_phases:
        _t0 = _phase_header("0b", skip_phases)
        observer.begin_phase(
            "0b",
            "Semantic Crawling",
            {
                "activities": len(manifest.activities) if manifest else 0,
                "llm_model": llm_model,
            },
        )
        try:
            from rlmobtest.phases.phase_0b_crawl import run_semantic_crawl

            crawl_result = run_semantic_crawl(
                env=env,
                manifest=manifest,
                paths=paths,
                observer=observer,
                llm_model=llm_model,
                llm_base_url=llm_base_url,
            )
            observer.end_phase(
                "0b",
                {
                    "reached": len(crawl_result.activities_reached),
                    "failed": len(crawl_result.activities_failed),
                    "snapshots": len(crawl_result.snapshots),
                },
            )
            coverage_tracker = CoverageTracker(manifest=manifest, crawl_result=crawl_result)
            total_elements = sum(
                len(s.elements_found) for s in crawl_result.snapshots.values()
            )
            req_count = 0
            if crawl_result.requirements_csv_path and crawl_result.requirements_csv_path.exists():
                import csv as _csv

                with open(crawl_result.requirements_csv_path, newline="", encoding="utf-8") as _f:
                    req_count = max(0, sum(1 for _ in _csv.reader(_f)) - 1)
                coverage_tracker.set_total_requirements(req_count)
                run_logger.info("Total requirements loaded: %d", req_count)
                if req_count > 0 and not settings.is_req_analysis:
                    settings = settings.model_copy(update={"is_req_analysis": True})
                    console.print(
                        f"  [cyan]ℹ  Requirements auto-enabled ({req_count} entries)[/cyan]"
                    )
            _detail = (
                f"{len(crawl_result.activities_reached)} crawled  │  "
                f"{total_elements} elements  │  "
                f"{req_count} requirements"
            )
            _phase_ok("0b", _t0, _detail)
            _statuses["0b"] = {
                "status": "ok",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": _detail,
            }
        except Exception as exc:
            observer.fail_phase("0b", exc)
            _phase_fail("0b", _t0, exc)
            run_logger.warning("Phase 0b failed: %s", exc)
            _statuses["0b"] = {
                "status": "failed",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": str(exc),
            }
    else:
        _phase_skip("0b")
        _statuses["0b"] = {"status": "skipped", "duration": "—", "detail": "—"}

    # ── Phase 0c: Replay Memory Warmup ────────────────────────────────────────
    if "0c" not in skip_phases and crawl_result is not None:
        _t0 = _phase_header("0c", skip_phases)
        observer.begin_phase(
            "0c",
            "Replay Memory Warmup",
            {"activities_crawled": len(crawl_result.snapshots)},
        )
        try:
            from rlmobtest.phases.phase_0c_warmup import warmup_replay_memory

            warmup_result = warmup_replay_memory(
                env=env,
                agent=agent,
                crawl_result=crawl_result,
                observer=observer,
            )
            observer.end_phase(
                "0c",
                {
                    "transitions_pushed": warmup_result.transitions_pushed,
                    "activities_covered": len(warmup_result.activities_covered),
                },
            )
            _detail = (
                f"{warmup_result.transitions_pushed} transitions  │  "
                f"{len(warmup_result.activities_covered)} activities covered"
            )
            _phase_ok("0c", _t0, _detail)
            _statuses["0c"] = {
                "status": "ok",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": _detail,
            }
        except Exception as exc:
            observer.fail_phase("0c", exc)
            _phase_fail("0c", _t0, exc)
            run_logger.warning("Phase 0c failed: %s", exc)
            _statuses["0c"] = {
                "status": "failed",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": str(exc),
            }
    elif "0c" in skip_phases:
        _phase_skip("0c")
        _statuses["0c"] = {"status": "skipped", "duration": "—", "detail": "—"}
    else:
        _phase_skip("0c", "no crawl result")
        _statuses["0c"] = {"status": "skipped", "duration": "—", "detail": "no crawl result"}

    # ── Phase 1: RL Training with Coverage Tracking ───────────────────────────
    _t0_phase1 = _phase_header("1", skip_phases)
    observer.begin_phase(
        "1",
        "RL Training",
        {
            "mode": mode,
            "max_time": max_time,
            "max_episodes": max_episodes,
            "max_steps": max_steps,
        },
    )

    metrics = TrainingMetrics(save_path=paths.metrics, plots_path=paths.plots, run_id=run_id)
    checkpoint_mgr = ModelCheckpoint(save_dir=paths.checkpoints)
    progress = TrainingProgress(max_time=max_time, max_episodes=max_episodes)

    progress.start()
    episode = 0

    try:
        for _ in count(1):
            episode += 1
            if progress.should_stop(episode):
                break

            progress.update(episode)
            epsilon = agent.get_epsilon()

            metrics.start_episode()
            coverage_tracker.start_episode()
            metrics.print_episode_start(episode, epsilon, agent.steps_done)
            run_logger.info("Episode %d started | epsilon=%.3f", episode, epsilon)

            previous_action = LongTensor([[0]])
            state, actions = env.reset()
            activity_actual = env.first_activity
            previous_activity = activity_actual
            activities = [activity_actual]
            metrics.log_activity(activity_actual)
            coverage_tracker.record_activity(activity_actual)
            env.nametc = env._create_tcfile(activity_actual)
            episode_reward = 0

            if settings.is_req_analysis:
                env.get_requirements()

            for t in count():
                if len(actions) > 0:
                    if state.shape[3] > state.shape[2]:
                        state = state.permute(0, 1, 3, 2)

                    action, epsilon, q_value = agent.select_action(state, actions)

                    # Base reward
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

                    # Functional coverage reward (+15 new element, +20 new input class)
                    taken_action = actions[action[0][0]]
                    last_xml = getattr(env, "_last_xml", None)
                    elements_on_screen = _extract_resource_ids(last_xml)
                    reward += calculate_functional_reward(
                        taken_action, coverage_tracker, elements_on_screen
                    )

                    # Track requirement hits for coverage metrics
                    if settings.is_req_analysis:
                        rid = getattr(taken_action, "resourceid", None)
                        req_buttons = getattr(env, "buttons", [])
                        run_logger.debug(
                            "REQ_CHECK | rid=%s | req_buttons_count=%d | match=%s",
                            rid,
                            len(req_buttons),
                            rid in req_buttons if rid else False,
                        )
                        if rid and rid in req_buttons:
                            run_logger.info("REQ_HIT | %s", rid)
                            coverage_tracker.record_requirement_hit(rid)

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

                    # Activity change handling
                    if activity_actual != activity:
                        previous_activity = activity_actual
                        activity_actual = activity
                        env.copy_coverage()
                        coverage_tracker.record_activity(activity_actual)

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
                            f"   [red]💥 Crash! Episode {episode} complete in {t + 1} steps[/red]"
                        )
                        run_logger.info("Episode %d ended (crash) after %d steps", episode, t + 1)
                        break

                    if t + 1 >= max_steps:
                        console.print(
                            f"   [cyan]🔄 Step limit ({max_steps}) reached. New episode.[/cyan]"
                        )
                        run_logger.info(
                            "Episode %d ended (step limit) after %d steps", episode, t + 1
                        )
                        break

                    if progress.should_stop(episode):
                        break

                else:
                    console.print(
                        "   [yellow]⚠️ No actions available. Episode interrupted.[/yellow]"
                    )
                    run_logger.warning("Episode %d interrupted — no actions", episode)
                    env.tc_action = []
                    break

            # Episode-end penalty: -10 per element in total_elements not touched this episode
            ep_untouched = coverage_tracker.total_elements - coverage_tracker._current_episode_elements
            if ep_untouched:
                ep_penalty = float(len(ep_untouched)) * -10.0
                episode_reward += ep_penalty
                # Push penalty as a terminal transition (only when state is valid)
                if state is not None:
                    agent.memory.push(state, previous_action, None, Tensor([ep_penalty]))
                    metrics.log_step(ep_penalty, None, None, None)
                run_logger.info(
                    "Episode %d: untouched penalty %.0f (%d elements)",
                    episode,
                    ep_penalty,
                    len(ep_untouched),
                )

            episode_duration = (datetime.now() - metrics.episode_start_time).total_seconds()
            metrics.end_episode()
            coverage_tracker.end_episode()
            metrics.print_episode_end(episode, t + 1, episode_reward, episode_duration)
            run_logger.info(
                "Episode %d | req_hits=%d/%d | req_buttons_pool=%d | req_coverage=%.1f%%",
                episode,
                len(coverage_tracker.requirements_hit),
                coverage_tracker.total_requirements,
                len(getattr(env, "buttons", [])),
                coverage_tracker._requirement_ratio() * 100,
            )
            progress.update(episode)

            if episode % 10 == 0:
                coverage_tracker.take_snapshot(episode, agent.steps_done)
                model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
                checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
                metrics.print_summary()
                observer.record_event(
                    "1",
                    "episode_batch",
                    {
                        "episode": episode,
                        "epsilon": float(epsilon),
                        "steps": agent.steps_done,
                        "coverage": coverage_tracker.get_current_coverage(),
                    },
                )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Training interrupted by user[/yellow]")
        run_logger.info("Training interrupted by user")

    finally:
        progress.stop()

        console.print("\n[dim]💾 Saving checkpoint and metrics...[/dim]")
        model = agent.policy_net if hasattr(agent, "policy_net") else agent.model
        checkpoint_mgr.save(model, agent.optimizer, metrics, episode, agent.steps_done)
        metrics.save()
        metrics.plot_metrics()
        metrics.print_summary()

        coverage_tracker.take_snapshot(episode, agent.steps_done)
        observer.end_phase(
            "1",
            {
                "episodes": metrics.total_episodes,
                "total_steps": agent.steps_done,
                "activities_covered": len(coverage_tracker.activities_seen),
            },
        )
        cov = coverage_tracker.get_current_coverage()
        _detail_p1 = (
            f"{metrics.total_episodes} episodes  │  "
            f"{agent.steps_done} steps  │  "
            f"activity cov {cov['activity_coverage']:.0%}"
        )
        _phase_ok("1", _t0_phase1, _detail_p1)
        _statuses["1"] = {
            "status": "ok",
            "duration": f"{time.time() - _t0_phase1:.1f}s",
            "detail": _detail_p1,
        }

    # ── Phase 2: Enriched Transcription ───────────────────────────────────────
    if "2" not in skip_phases:
        _t0 = _phase_header("2", skip_phases)
        observer.begin_phase(
            "2",
            "Enriched Transcription",
            {"test_cases_dir": str(paths.test_cases)},
        )
        try:
            from rlmobtest.phases.phase_2_transcription import run_enriched_transcription

            trans_result = run_enriched_transcription(
                paths=paths,
                crawl_result=crawl_result,
                observer=observer,
            )
            observer.end_phase(
                "2",
                {
                    "files_transcribed": trans_result.files_transcribed,
                    "files_skipped": trans_result.files_skipped,
                },
            )
            _detail = (
                f"{trans_result.files_transcribed} transcribed  │  "
                f"{trans_result.files_skipped} skipped"
            )
            _phase_ok("2", _t0, _detail)
            _statuses["2"] = {
                "status": "ok",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": _detail,
            }
        except Exception as exc:
            observer.fail_phase("2", exc)
            _phase_fail("2", _t0, exc)
            run_logger.warning("Phase 2 failed: %s", exc)
            _statuses["2"] = {
                "status": "failed",
                "duration": f"{time.time() - _t0:.1f}s",
                "detail": str(exc),
            }
    else:
        _phase_skip("2")
        _statuses["2"] = {"status": "skipped", "duration": "—", "detail": "—"}

    # ── Final: Coverage Metrics + HTML Report ─────────────────────────────────
    console.print()
    console.rule("[dim]Finalizing[/dim]", style="dim")
    console.print("[dim]📊 Calculating coverage metrics...[/dim]")
    final_metrics = coverage_tracker.calculate_final_metrics(metrics)
    run_logger.info("Final coverage: %s", final_metrics)

    coverage_tracker.plot_coverage(paths.plots, run_id)
    observer.save()

    console.print("[dim]📄 Generating HTML report...[/dim]")
    report_path: Path | None = None
    try:
        from rlmobtest.report.html_reporter import HTMLReporter

        reporter = HTMLReporter(
            observer=observer,
            coverage_tracker=coverage_tracker,
            training_metrics=metrics,
            paths=paths,
            run_id=run_id,
            manifest=manifest,
        )
        report_path = reporter.generate()
    except Exception as exc:
        console.print(f"[yellow]⚠ HTML report failed: {exc}[/yellow]")
        run_logger.warning("HTML report generation failed: %s", exc)

    # ── Pipeline Summary ───────────────────────────────────────────────────────
    _pipeline_summary(_statuses)

    cov = coverage_tracker.get_current_coverage()
    console.print(
        Panel.fit(
            f"[bold green]✅ Pipeline complete[/bold green]  │  Run ID: [bold]{run_id}[/bold]\n"
            f"[dim]Activity: {cov['activity_coverage']:.0%}  │  "
            f"Element: {cov['element_coverage']:.0%}  │  "
            f"Requirement: {cov['requirement_coverage']:.0%}[/dim]\n"
            + (f"[dim]Report: {report_path}[/dim]" if report_path else "")
            + f"\n[dim]Log: {log_path}[/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )
    return report_path


def main():
    """Main entry point - delegates to CLI."""
    from rlmobtest.cli import main as cli_main

    cli_main()
