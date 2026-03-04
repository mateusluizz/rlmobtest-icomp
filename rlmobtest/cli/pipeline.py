"""Pipeline command for the RLMobTest CLI."""

from typing import Annotated

import typer
from rich.panel import Panel

from rlmobtest.cli import DQNMode, app, console, print_device_info
from rlmobtest.constants.llm import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.config_reader import AppConfig, ConfRead


@app.command()
def pipeline(
    mode: Annotated[
        DQNMode,
        typer.Option("--mode", "-m", help="DQN mode"),
    ] = DQNMode.improved,
    max_steps: Annotated[
        int,
        typer.Option("--max-steps", "-s", help="Max steps per episode"),
    ] = 100,
    app_filter: Annotated[
        list[str] | None,
        typer.Option("--app", "-a", help="Run pipeline for specific app(s)"),
    ] = None,
    skip_exploration: Annotated[
        bool,
        typer.Option("--skip-exploration", help="Skip exploration phase (step 1)"),
    ] = False,
    skip_requirements: Annotated[
        bool,
        typer.Option("--skip-requirements", help="Skip requirements generation (step 2)"),
    ] = False,
    skip_guided: Annotated[
        bool,
        typer.Option("--skip-guided", help="Skip guided training (step 3)"),
    ] = False,
    only_transcribe: Annotated[
        bool,
        typer.Option("--only-transcribe", help="Only run transcription (step 4)"),
    ] = False,
    llm_model: Annotated[
        str,
        typer.Option("--llm-model", "-l", help="Ollama model for requirements and transcription"),
    ] = DEFAULT_LLM_MODEL,
    all_dates: Annotated[
        bool,
        typer.Option("--all-dates", help="Process test_cases from all dates (default: today only)"),
    ] = False,
):
    """
    Run the full pipeline: exploration → requirements → guided training → transcription.

    Steps:
        1. Exploration with is_req=false (DQN learns via heuristics)
        2. Generate requirements.csv (Ollama + source code)
        3. Guided training with is_req=true (DQN uses happy path)
        4. Transcribe test cases (CrewAI)

    Examples:
        rlmobtest pipeline                          # Full pipeline
        rlmobtest pipeline --skip-exploration       # Skip step 1
        rlmobtest pipeline --only-transcribe        # Only step 4
        rlmobtest pipeline --app protect.budgetwatch  # Single app
    """
    from langchain_ollama import ChatOllama

    from rlmobtest.training import run
    from rlmobtest.transcription.crew_transcriber import find_all_days, transcribe_folder

    # Load configs
    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        all_configs = settings_reader.read_all_settings()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    # Filter if --app specified
    if app_filter:
        configs = [c for c in all_configs if c.package_name in app_filter]
        not_found = set(app_filter) - {c.package_name for c in configs}
        if not_found:
            console.print(f"[red]App(s) not found: {', '.join(not_found)}[/red]")
            raise typer.Exit(code=1)
    else:
        configs = all_configs

    console.print(
        Panel.fit(
            f"[bold cyan]RLMobTest Pipeline[/bold cyan]\n"
            f"[dim]{len(configs)} app(s) | mode={mode.value} | "
            f"max_steps={max_steps}[/dim]",
            border_style="cyan",
        )
    )

    print_device_info()

    for i, config in enumerate(configs, 1):
        pkg = config.package_name
        console.print(f"\n[bold yellow]{'=' * 60}[/]")
        console.print(f"[bold yellow]  App {i}/{len(configs)}: {pkg}[/]")
        console.print(f"[bold yellow]{'=' * 60}[/]")

        # --- Step 0: JaCoCo Setup (if coverage enabled) ---
        if config.is_coverage and config.source_code:
            console.print(Panel("[bold]Step 0/4:[/] JaCoCo Setup", style="blue"))
            from rlmobtest.utils.jacoco_setup import run_setup

            setup_result = run_setup(config)
            for key, ok in setup_result.items():
                status = "[green]OK[/]" if ok else "[yellow]skipped[/]"
                console.print(f"  {key}: {status}")

        # Build app context once per app (used in transcription step)
        app_context = None
        if config.source_code:
            from rlmobtest.utils.app_context import build_app_context

            app_context = build_app_context(config.source_code, pkg)
            if app_context:
                console.print(f"  [green]App context extracted ({len(app_context)} chars)[/]")

        # --- Step 1: Exploration (is_req=false) ---
        if not skip_exploration and not only_transcribe:
            console.print(Panel("[bold]Step 1/4:[/] Exploration (is_req=false)", style="blue"))
            exploration_config = AppConfig(
                apk_name=config.apk_name,
                package_name=config.package_name,
                is_req=False,
                is_coverage=config.is_coverage,
                time=config.time,
                source_code=config.source_code,
            )
            try:
                run(
                    mode=mode.value,
                    max_time=config.time,
                    max_steps=max_steps,
                    config=exploration_config,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Interrupted.[/]")
                raise typer.Exit(code=130) from None
            except Exception as e:
                console.print(f"[red]Exploration error: {e}[/]")
                continue

        # --- Step 2: Generate requirements ---
        if not skip_requirements and not only_transcribe:
            console.print(Panel("[bold]Step 2/4:[/] Generate requirements.csv", style="blue"))
            if not config.source_code:
                console.print("[yellow]No source_code configured, skipping.[/]")
            else:
                try:
                    from rlmobtest.training.generate_requirements import processar_app

                    client = ChatOllama(model=llm_model, base_url=DEFAULT_OLLAMA_BASE_URL)
                    processar_app(config, client, all_dates=all_dates)
                except Exception as e:
                    console.print(f"[red]Requirements error: {e}[/]")

        # --- Step 3: Guided training (is_req=true) ---
        if not skip_guided and not only_transcribe:
            console.print(Panel("[bold]Step 3/4:[/] Guided training (is_req=true)", style="blue"))
            guided_config = AppConfig(
                apk_name=config.apk_name,
                package_name=config.package_name,
                is_req=True,
                is_coverage=config.is_coverage,
                time=config.time,
                source_code=config.source_code,
            )
            try:
                run(
                    mode=mode.value,
                    max_time=config.time,
                    max_steps=max_steps,
                    config=guided_config,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Interrupted.[/]")
                raise typer.Exit(code=130) from None
            except Exception as e:
                console.print(f"[red]Guided training error: {e}[/]")
                continue

        # --- Step 4: Transcription ---
        console.print(Panel("[bold]Step 4/4:[/] Transcription (CrewAI)", style="blue"))
        if all_dates:
            days = find_all_days(pkg, mode.value, OUTPUT_BASE)
        else:
            from datetime import datetime as _dt

            _now = _dt.now()
            _today = (_now.strftime("%Y"), _now.strftime("%m"), _now.strftime("%d"))
            _today_tc = OUTPUT_BASE / pkg / mode.value / _today[0] / _today[1] / _today[2] / "test_cases"
            days = [_today] if _today_tc.is_dir() and any(_today_tc.iterdir()) else []

        if not days:
            console.print("[yellow]No test_cases to transcribe.[/]")
            continue

        for year, month, day in days:
            day_path = OUTPUT_BASE / pkg / mode.value / year / month / day
            tc_path = day_path / "test_cases"
            tr_path = day_path / "transcriptions"

            if not tc_path.exists() or not any(tc_path.iterdir()):
                continue

            console.print(f"  [dim]Transcribing {year}/{month}/{day}...[/]")
            try:
                transcribe_folder(
                    input_folder=tc_path,
                    output_folder=tr_path,
                    model_name=f"ollama/{llm_model}",
                    screenshots_folder=day_path / "screenshots",
                    app_context=app_context,
                )
            except Exception as e:
                console.print(f"  [red]Transcription error: {e}[/]")

        # --- Report ---
        if days:
            from rlmobtest.training.report import generate_report

            run_paths = [
                OUTPUT_BASE / pkg / mode.value / y / m / d for y, m, d in days
            ]
            try:
                generate_report(
                    run_paths, package_name=pkg, agent_type=mode.value,
                    source_code=config.source_code or None,
                )
            except Exception as e:
                console.print(f"[red]Report error: {e}[/]")

    console.print(Panel.fit("[bold green]Pipeline complete[/]", border_style="green"))
