"""Train command for the RLMobTest CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from rlmobtest.cli import DQNMode, app, console, print_device_info
from rlmobtest.constants.paths import CONFIG_JSON_PATH
from rlmobtest.utils.config_reader import ConfRead


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

    # Apply mode default
    if mode is None:
        mode = DQNMode.improved

    # Override time/episodes if specified via CLI
    if time is not None or episodes is not None:
        for config in configs:
            if time is not None:
                config.time_exploration = time

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
    from rlmobtest.training import run, run_all

    # Single app training
    if len(configs) == 1:
        config = configs[0]
        console.print(f"\n[dim]Training app: {config.package_name}[/dim]")

        if checkpoint:
            console.print(f"[dim]Resuming from checkpoint: {checkpoint}[/dim]")

        run(
            mode=mode.value,
            max_time=config.time_exploration if episodes is None else None,
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
