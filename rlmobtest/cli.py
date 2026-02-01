#!/usr/bin/env python3
"""
CLI module for RLMobTest using Typer.
"""

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


def load_config_defaults() -> tuple[int | None, DQNMode]:
    """
    Load default values from config file.

    Returns:
        Tuple of (time, mode) from config or defaults.
    """
    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        settings = settings_reader.read_setting()
        return settings.time, DQNMode.improved
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not load config: {e}[/yellow]")
        console.print("[dim]Using default values.[/dim]")
        return None, DQNMode.improved


@app.command()
def train(
    mode: Annotated[
        DQNMode,
        typer.Option(
            "--mode",
            "-m",
            help="DQN mode: 'original' or 'improved'",
        ),
    ] = None,
    time: Annotated[
        int | None,
        typer.Option(
            "--time",
            "-t",
            help="Training time limit in seconds (e.g., 300 for 5 min)",
        ),
    ] = None,
    episodes: Annotated[
        int | None,
        typer.Option(
            "--episodes",
            "-e",
            help="Number of episodes to train (e.g., 50)",
        ),
    ] = None,
    checkpoint: Annotated[
        Path | None,
        typer.Option(
            "--checkpoint",
            "-c",
            help="Path to checkpoint file to resume training",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    max_steps: Annotated[
        int,
        typer.Option(
            "--max-steps",
            "-s",
            help=(
                "Maximum steps per episode (default: 100). "
                "Limits episode length to ensure regular resets and better exploration."
            ),
        ),
    ] = 100,
):
    """
    Train the RL agent on an Android application.

    If no arguments are provided, reads configuration from config/settings.json.

    Examples:
        rlmobtest train                     # Use config file settings
        rlmobtest train --time 600          # Train for 10 minutes
        rlmobtest train --episodes 50       # Train for 50 episodes
        rlmobtest train --mode original     # Use original DQN
        rlmobtest train --max-steps 200     # 200 steps per episode
    """
    # Validate mutually exclusive arguments
    if time is not None and episodes is not None:
        console.print(
            "[red]❌ Error: --time and --episodes are mutually exclusive[/red]"
        )
        console.print("[dim]Use one or the other, not both.[/dim]")
        raise typer.Exit(code=1)

    # Load defaults from config if no arguments provided
    config_time, config_mode = load_config_defaults()

    # Apply config defaults if not specified via CLI
    if mode is None:
        mode = config_mode

    if time is None and episodes is None:
        time = config_time
        if time:
            console.print(f"[dim]Using time limit from config: {time}s[/dim]")

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
    from rlmobtest.__main__ import run

    # Run training
    if checkpoint:
        console.print(f"[dim]Resuming from checkpoint: {checkpoint}[/dim]")

    run(
        mode=mode.value,
        max_time=time,
        max_episodes=episodes,
        max_steps=max_steps,
        checkpoint_path=checkpoint,
    )


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
        console.print(f"  Resolution: {settings.resolution}")
        console.print(f"  Time limit: {settings.time}s")
    except Exception as e:
        console.print(f"  [red]Error loading config: {e}[/red]")


@app.command()
def clean(
    folder: Annotated[
        str | None,
        typer.Argument(
            help="Subfolder to clean (e.g., screenshots). If omitted, cleans all.",
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

    Examples:
        rlmobtest clean                    # Clean all (with confirmation)
        rlmobtest clean screenshots        # Clean only screenshots
        rlmobtest clean --dry-run          # Show what would be deleted
        rlmobtest clean -f                 # Clean all without confirmation
    """
    # Validate folder name if provided
    if folder and folder not in OUTPUT_SUBFOLDERS:
        console.print(f"[red]Error: '{folder}' is not a valid subfolder[/red]")
        console.print(f"[dim]Valid options: {', '.join(OUTPUT_SUBFOLDERS)}[/dim]")
        raise typer.Exit(code=1)

    folders_to_clean = [folder] if folder else OUTPUT_SUBFOLDERS

    if dry_run:
        console.print("[yellow][DRY-RUN] No files will be deleted[/yellow]\n")

    # Count files first
    total_files = 0
    for subfolder in folders_to_clean:
        folder_path = OUTPUT_BASE / subfolder
        if folder_path.exists():
            total_files += sum(1 for _ in folder_path.rglob("*") if _.is_file())

    if total_files == 0:
        console.print("[dim]Nothing to clean - folders are empty[/dim]")
        return

    # Confirmation prompt
    if not dry_run and not force:
        confirm = typer.confirm(
            f"Delete {total_files} files from {len(folders_to_clean)} folder(s)?"
        )
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(code=0)

    # Clean folders
    deleted = 0
    for subfolder in folders_to_clean:
        folder_path = OUTPUT_BASE / subfolder
        if not folder_path.exists():
            continue

        count = 0
        for item in folder_path.rglob("*"):
            if item.is_file():
                if dry_run:
                    console.print(f"  [dim]Would delete: {item.name}[/dim]")
                else:
                    item.unlink()
                count += 1

        # Remove empty subdirectories
        if not dry_run:
            for subdir in sorted(folder_path.rglob("*"), reverse=True):
                if subdir.is_dir() and not any(subdir.iterdir()):
                    subdir.rmdir()

        if count > 0:
            action = "Would delete" if dry_run else "Deleted"
            console.print(f"[green][{subfolder}][/green] {action} {count} files")
        deleted += count

    console.print(f"\n[bold]Total: {deleted} files[/bold]")


def main():
    """Entry point for the CLI."""
    app()
