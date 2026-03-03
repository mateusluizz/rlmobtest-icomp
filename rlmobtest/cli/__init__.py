"""CLI module for RLMobTest using Typer."""

from enum import Enum

import typer
from rich.console import Console

from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.config_reader import AppConfig, ConfRead

console = Console()

OUTPUT_SUBFOLDERS = [
    "checkpoints",
    "crashes",
    "errors",
    "metrics",
    "old_transcriptions",
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


# Import commands to register them with the app
from rlmobtest.cli.clean import clean  # noqa: E402, F401
from rlmobtest.cli.info import info  # noqa: E402, F401
from rlmobtest.cli.pipeline import pipeline  # noqa: E402, F401
from rlmobtest.cli.report import report  # noqa: E402, F401
from rlmobtest.cli.train import train  # noqa: E402, F401


def main():
    """Entry point for the CLI."""
    app()
