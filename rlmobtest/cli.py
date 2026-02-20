#!/usr/bin/env python3
"""
CLI module for RLMobTest using Typer.
"""

import contextlib
import urllib.error
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.config_reader import ConfRead

console = Console()

# Valid output subfolders
OUTPUT_SUBFOLDERS = [
    "checkpoints",
    "crashes",
    "errors",
    "metrics",
    "screenshots",
    "test_cases",
    "transcriptions",
]
app = typer.Typer(
    name="rlmobtest",
    help="RLMobTest - RL-based Android Testing",
    add_completion=False,
    rich_markup_mode="rich",
)


class DQNMode(str, Enum):
    """DQN training mode options."""

    original = "original"
    improved = "improved"


def print_device_info():
    """Print device information with Rich."""
    import torch

    console.print()
    if torch.cuda.is_available():
        console.print(f"[green]🖥️  GPU:[/green] {torch.cuda.get_device_name(0)}")
        console.print(f"[dim]   CUDA Version: {torch.version.cuda}[/dim]")
    else:
        console.print("[yellow]🖥️  Running on CPU[/yellow]")


@app.command()
def train(
    mode: Annotated[
        DQNMode,
        typer.Option(
            "--mode",
            "-m",
            help="DQN mode: 'original' or 'improved'",
        ),
    ] = DQNMode.improved,
    app_filter: Annotated[
        list[str] | None,
        typer.Option(
            "--app",
            "-a",
            help="Train specific app(s) by package name. Can be used multiple times.",
        ),
    ] = None,
    time: Annotated[
        int | None,
        typer.Option(
            "--time",
            "-t",
            help="Training time limit in seconds (overrides config for all apps)",
        ),
    ] = None,
    episodes: Annotated[
        int | None,
        typer.Option(
            "--episodes",
            "-e",
            help="Number of episodes to train (overrides config for all apps)",
        ),
    ] = None,
    checkpoint: Annotated[
        Path | None,
        typer.Option(
            "--checkpoint",
            "-c",
            help="Path to checkpoint file to resume training (single app only)",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    max_steps: Annotated[
        int,
        typer.Option(
            "--max-steps",
            "-s",
            help="Maximum steps per episode (default: 100)",
        ),
    ] = 100,
):
    """
    Train the RL agent on Android application(s).

    Reads app configurations from config/settings.json. Without --app, trains all
    apps sequentially. Each app uses its own time/coverage settings from config.

    Examples:
        rlmobtest train                          # Train all apps from config
        rlmobtest train --app com.example.app    # Train specific app
        rlmobtest train -a app1 -a app2          # Train multiple specific apps
        rlmobtest train --time 600               # Override time for all apps
        rlmobtest train --mode original          # Use original DQN
    """
    # Validate mutually exclusive arguments
    if time is not None and episodes is not None:
        console.print("[red]❌ Error: --time and --episodes are mutually exclusive[/red]")
        console.print("[dim]Use one or the other, not both.[/dim]")
        raise typer.Exit(code=1)

    if checkpoint and app_filter and len(app_filter) > 1:
        console.print("[red]❌ Error: --checkpoint can only be used with a single app[/red]")
        raise typer.Exit(code=1)

    # Load all configs from settings.json
    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        all_configs = settings_reader.read_all_settings()
    except Exception as e:
        console.print(f"[red]❌ Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    if not all_configs:
        console.print("[red]❌ No app configurations found in settings.json[/red]")
        raise typer.Exit(code=1)

    # Filter configs if --app specified
    if app_filter:
        configs = [c for c in all_configs if c.package_name in app_filter]
        not_found = set(app_filter) - {c.package_name for c in configs}
        if not_found:
            console.print(f"[red]❌ App(s) not found in config: {', '.join(not_found)}[/red]")
            console.print("[dim]Available apps:[/dim]")
            for c in all_configs:
                console.print(f"  - {c.package_name}")
            raise typer.Exit(code=1)
    else:
        configs = all_configs

    # Override time/episodes if specified via CLI
    if time is not None or episodes is not None:
        for config in configs:
            if time is not None:
                config.time = time

    # Print header
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]RLMobTest[/bold cyan]\n"
            "[dim]Reinforcement Learning Mobile App Testing[/dim]",
            border_style="cyan",
        )
    )

    print_device_info()

    # Import here to avoid circular imports and speed up CLI help
    from rlmobtest.training.runner import run, run_all

    # Single app training
    if len(configs) == 1:
        config = configs[0]
        console.print(f"\n[dim]Training app: {config.package_name}[/dim]")

        if checkpoint:
            console.print(f"[dim]Resuming from checkpoint: {checkpoint}[/dim]")

        run(
            mode=mode.value,
            max_time=config.time if episodes is None else None,
            max_episodes=episodes,
            max_steps=max_steps,
            checkpoint_path=checkpoint,
            config=config,
        )
    else:
        # Multi-app sequential training
        if checkpoint:
            console.print("[yellow]⚠ --checkpoint ignored for multi-app training[/yellow]")

        run_all(
            configs=configs,
            mode=mode.value,
            max_steps=max_steps,
        )


@app.command(name="train-phases")
def train_phases(
    mode: Annotated[
        DQNMode,
        typer.Option("--mode", "-m", help="DQN mode: 'original' or 'improved'"),
    ] = DQNMode.improved,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            "-a",
            help="App package name to train. Defaults to first entry in settings.json.",
        ),
    ] = None,
    time: Annotated[
        int | None,
        typer.Option("--time", "-t", help="Training time limit in seconds."),
    ] = None,
    episodes: Annotated[
        int | None,
        typer.Option("--episodes", "-e", help="Number of training episodes."),
    ] = None,
    max_steps: Annotated[
        int,
        typer.Option("--max-steps", "-s", help="Maximum steps per episode (default: 100)."),
    ] = 100,
    llm_model: Annotated[
        str,
        typer.Option("--llm-model", help="LLM model for semantic crawling annotations."),
    ] = "ollama/gemma3:4b",
    llm_base_url: Annotated[
        str,
        typer.Option("--llm-base-url", help="LLM API base URL."),
    ] = "http://localhost:11434",
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip",
            help="Skip a phase by ID. Can repeat: --skip 0b --skip 0c. "
            "Valid values: 0a, 0b, 0c, 1, 2.",
        ),
    ] = None,
):
    """
    Train with the full multi-phase pipeline (manifest → crawl → warmup → train → transcribe).

    Outputs per run: JSON phase report, 4 coverage plots, HTML report.

    Examples:
        rlmobtest train-phases                      # Full pipeline, improved DQN
        rlmobtest train-phases --episodes 50        # 50 episodes
        rlmobtest train-phases --skip 0b --skip 0c  # Skip crawling + warmup
        rlmobtest train-phases --mode original      # Use original DQN
        rlmobtest train-phases --llm-model ollama/gemma3:4b
    """
    if time is not None and episodes is not None:
        console.print("[red]❌ Error: --time and --episodes are mutually exclusive[/red]")
        raise typer.Exit(code=1)

    valid_phases = {"0a", "0b", "0c", "1", "2"}
    skip_phases = skip or []
    bad = [p for p in skip_phases if p not in valid_phases]
    if bad:
        console.print(f"[red]❌ Invalid phase(s) to skip: {', '.join(bad)}[/red]")
        console.print(f"[dim]Valid: {', '.join(sorted(valid_phases))}[/dim]")
        raise typer.Exit(code=1)

    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        all_configs = settings_reader.read_all_settings()
    except Exception as e:
        console.print(f"[red]❌ Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    if not all_configs:
        console.print("[red]❌ No app configurations found in settings.json[/red]")
        raise typer.Exit(code=1)

    if app_name:
        configs = [c for c in all_configs if c.package_name == app_name]
        if not configs:
            console.print(f"[red]❌ App '{app_name}' not found in config[/red]")
            for c in all_configs:
                console.print(f"  - {c.package_name}")
            raise typer.Exit(code=1)
        config = configs[0]
    else:
        config = all_configs[0]

    if time is not None:
        config.time = time

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]RLMobTest[/bold cyan]\n"
            "[dim]Reinforcement Learning Mobile App Testing — Multi-Phase[/dim]",
            border_style="cyan",
        )
    )
    print_device_info()

    from rlmobtest.training.runner import run_with_phases

    run_with_phases(
        mode=mode.value,
        max_time=config.time if episodes is None else None,
        max_episodes=episodes,
        max_steps=max_steps,
        config=config,
        skip_phases=skip_phases,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
    )


@app.command()
def transcribe(
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            "-d",
            help="Path to an existing run directory (e.g. output/app/improved/2026/02/20).",
            exists=True,
            file_okay=False,
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            "-a",
            help="App package name. Uses the latest run for that app if --run-dir not given.",
        ),
    ] = None,
    llm_model: Annotated[
        str,
        typer.Option("--llm-model", help="LLM model for transcription."),
    ] = "ollama/gemma3:4b",
    llm_base_url: Annotated[
        str,
        typer.Option("--llm-base-url", help="LLM API base URL."),
    ] = "http://localhost:11434",
):
    """
    Run Phase 2 (enriched transcription) on an existing run's test cases.

    Can point to a specific run directory, or auto-detect the latest run for an app.

    Examples:
        rlmobtest transcribe --run-dir output/protect.budgetwatch/improved_phases/2026/02/20
        rlmobtest transcribe --app protect.budgetwatch
        rlmobtest transcribe --app protect.budgetwatch --llm-model ollama/gemma3:4b
    """
    import types

    # ── resolve run directory ──────────────────────────────────────────────────
    if run_dir is None:
        # Auto-detect: find latest run for the given app (or any app)
        if app_name is None:
            # Try first app in config
            try:
                settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
                cfg = settings_reader.read_setting()
                app_name = cfg.package_name
            except Exception:
                console.print("[red]❌ Cannot determine app name. Use --app or --run-dir.[/red]")
                raise typer.Exit(code=1)

        app_dir = OUTPUT_BASE / app_name
        if not app_dir.exists():
            console.print(f"[red]❌ No output found for app '{app_name}' in {OUTPUT_BASE}[/red]")
            raise typer.Exit(code=1)

        # Walk agent_type/year/month/day to find directories containing test_cases/
        candidates = sorted(
            (d for d in app_dir.rglob("test_cases") if d.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            console.print(f"[red]❌ No test_cases directory found under {app_dir}[/red]")
            raise typer.Exit(code=1)

        run_dir = candidates[0].parent
        console.print(f"[dim]Auto-detected run directory: {run_dir}[/dim]")

    # ── build a minimal paths namespace ───────────────────────────────────────
    paths = types.SimpleNamespace(
        run_path=run_dir,
        test_cases=run_dir / "test_cases",
        transcriptions=run_dir / "transcriptions",
        screenshots=run_dir / "screenshots",
    )
    (run_dir / "transcriptions").mkdir(parents=True, exist_ok=True)

    tc_count = len(list(paths.test_cases.glob("*.md")))
    if tc_count == 0:
        console.print(f"[yellow]⚠ No .md test case files found in {paths.test_cases}[/yellow]")
        raise typer.Exit(code=0)

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]RLMobTest — Phase 2: Transcription[/bold cyan]\n"
            f"[dim]{run_dir}[/dim]",
            border_style="cyan",
        )
    )
    console.print(f"\n[dim]Found {tc_count} test case file(s) to transcribe.[/dim]")

    from rlmobtest.metrics.phase_observer import PhaseObserver
    from rlmobtest.phases.phase_2_transcription import run_enriched_transcription

    observer = PhaseObserver(
        run_id=run_dir.name,
        output_path=run_dir / "phase_reports",
    )
    (run_dir / "phase_reports").mkdir(parents=True, exist_ok=True)
    observer.begin_phase("2", "Enriched Transcription", {"test_cases_dir": str(paths.test_cases)})

    try:
        result = run_enriched_transcription(
            paths=paths,
            crawl_result=None,
            observer=observer,
            model_name=llm_model,
            base_url=llm_base_url,
        )
        observer.end_phase("2", {"files_transcribed": result.files_transcribed})
        console.print(
            f"\n[green]✅ Transcription complete:[/green] "
            f"{result.files_transcribed} transcribed, {result.files_skipped} skipped"
        )
        console.print(f"[dim]Output: {paths.transcriptions}[/dim]")
    except Exception as exc:
        observer.fail_phase("2", exc)
        console.print(f"\n[red]❌ Transcription failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def info():
    """Show configuration and environment information."""
    import torch

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]RLMobTest Info[/bold cyan]",
            border_style="cyan",
        )
    )

    # Device info
    console.print("\n[bold]Device:[/bold]")
    if torch.cuda.is_available():
        console.print(f"  GPU: {torch.cuda.get_device_name(0)}")
        console.print(f"  CUDA: {torch.version.cuda}")
    else:
        console.print("  CPU only")

    # Config info
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Config path: {CONFIG_JSON_PATH}")

    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        settings = settings_reader.read_setting()
        console.print(f"  APK: {settings.apk_name}")
        console.print(f"  Package: {settings.package_name}")
        console.print(f"  Time limit: {settings.time}s")
    except Exception as e:
        console.print(f"  [red]Error loading config: {e}[/red]")

    # Ollama server check
    console.print("\n[bold]Ollama Server:[/bold]")
    try:
        req = urllib.request.Request("http://localhost:11434", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                console.print("  [green]✓ Ollama is running[/green]")
            else:
                console.print(f"  [yellow]⚠ Unexpected status: {response.status}[/yellow]")
    except urllib.error.URLError:
        console.print("  [red]✗ Ollama is not running[/red]")
        console.print("  [dim]Start with: ollama serve[/dim]")
    except Exception as e:
        console.print(f"  [red]✗ Error checking Ollama: {e}[/red]")


@app.command()
def clean(
    folder: Annotated[
        str | None,
        typer.Argument(
            help="Subfolder to clean (e.g., screenshots). If omitted, cleans all.",
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            "-a",
            help="Clean only specific app (e.g., protect.budgetwatch)",
        ),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            help="Clean only specific agent type (original/improved)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be deleted without deleting",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """
    Clean output folders.

    Output structure: output/{app}/{agent_type}/{year}/{month}/{day}/{subfolder}/

    Examples:
        rlmobtest clean                              # Clean all (with confirmation)
        rlmobtest clean screenshots                  # Clean only screenshots
        rlmobtest clean --app protect.budgetwatch   # Clean specific app
        rlmobtest clean --agent original            # Clean only original agent outputs
        rlmobtest clean --dry-run                   # Show what would be deleted
        rlmobtest clean -f                          # Clean all without confirmation
    """
    import shutil

    # Validate folder name if provided
    if folder and folder not in OUTPUT_SUBFOLDERS:
        console.print(f"[red]Error: '{folder}' is not a valid subfolder[/red]")
        console.print(f"[dim]Valid options: {', '.join(OUTPUT_SUBFOLDERS)}[/dim]")
        raise typer.Exit(code=1)

    # Validate agent type if provided
    if agent and agent not in ["original", "improved"]:
        console.print(f"[red]Error: '{agent}' is not a valid agent type[/red]")
        console.print("[dim]Valid options: original, improved[/dim]")
        raise typer.Exit(code=1)

    if not OUTPUT_BASE.exists():
        console.print("[dim]Nothing to clean - output folder doesn't exist[/dim]")
        return

    if dry_run:
        console.print("[yellow][DRY-RUN] No files will be deleted[/yellow]\n")

    folders_to_clean = [folder] if folder else OUTPUT_SUBFOLDERS

    # Find all matching paths based on filters
    # Structure: output/{app}/{agent_type}/{year}/{month}/{day}/{subfolder}/
    files_to_delete = []
    dirs_to_delete = []

    for app_dir in OUTPUT_BASE.iterdir():
        if not app_dir.is_dir():
            continue
        if app_name and app_dir.name != app_name:
            continue

        for agent_dir in app_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            if agent and agent_dir.name != agent:
                continue

            # Traverse year/month/day structure
            for year_dir in agent_dir.iterdir():
                if not year_dir.is_dir():
                    continue
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue

                        # Find target subfolders
                        for subfolder in folders_to_clean:
                            subfolder_path = day_dir / subfolder
                            if subfolder_path.exists():
                                for item in subfolder_path.rglob("*"):
                                    if item.is_file():
                                        files_to_delete.append(item)
                                dirs_to_delete.append(subfolder_path)

    if not files_to_delete:
        console.print("[dim]Nothing to clean - no matching files found[/dim]")
        return

    # Show filter info
    filter_info = []
    if app_name:
        filter_info.append(f"app={app_name}")
    if agent:
        filter_info.append(f"agent={agent}")
    if folder:
        filter_info.append(f"folder={folder}")
    if filter_info:
        console.print(f"[dim]Filters: {', '.join(filter_info)}[/dim]\n")

    # Confirmation prompt
    if not dry_run and not force:
        confirm = typer.confirm(f"Delete {len(files_to_delete)} files?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(code=0)

    # Delete files
    deleted = 0
    for item in files_to_delete:
        if dry_run:
            # Show relative path for readability
            rel_path = item.relative_to(OUTPUT_BASE)
            console.print(f"  [dim]Would delete: {rel_path}[/dim]")
        else:
            item.unlink()
        deleted += 1

    # Remove empty directories
    if not dry_run:
        for dir_path in sorted(set(dirs_to_delete), reverse=True):
            if dir_path.exists():
                # Remove directory and empty parents
                with contextlib.suppress(OSError):
                    shutil.rmtree(dir_path)

        # Clean up empty date/agent/app directories
        for app_dir in OUTPUT_BASE.iterdir():
            if app_dir.is_dir():
                _remove_empty_dirs(app_dir)

    action = "Would delete" if dry_run else "Deleted"
    console.print(f"\n[bold]{action} {deleted} files[/bold]")


def _remove_empty_dirs(path: Path):
    """Recursively remove empty directories."""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def main():
    """Entry point for the CLI."""
    app()
