"""Pipeline command for the RLMobTest CLI."""

from typing import Annotated

import typer
from rich.panel import Panel

from rlmobtest.cli import DQNMode, app, console, print_device_info
from rlmobtest.constants.llm import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.config_reader import AppConfig, ConfRead
from rlmobtest.utils.ollama import check_ollama_model


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
    if not check_ollama_model(llm_model, DEFAULT_OLLAMA_BASE_URL):
        console.print(
            f"\n[bold red]⚠ Ollama indisponível ou modelo '{llm_model}' não instalado.[/bold red]\n"
            f"[dim]Verifique se o servidor está rodando: [bold]ollama serve[/bold]\n"
            f"E se o modelo está instalado: [bold]ollama pull {llm_model}[/bold][/dim]\n"
        )
        raise typer.Exit(code=1)

    import uuid as _uuid

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
        total_runs = max(1, config.runs)
        console.print(f"\n[bold yellow]{'=' * 60}[/]")
        console.print(
            f"[bold yellow]  App {i}/{len(configs)}: {pkg} "
            f"({total_runs} run(s))[/]"
        )
        console.print(f"[bold yellow]{'=' * 60}[/]")

        # --- Step 0: JaCoCo Setup (once per app, not per run) ---
        if config.is_coverage and config.source_code:
            console.print(Panel("[bold]Step 0/4:[/] JaCoCo Setup (Build Agent)", style="blue"))
            from rlmobtest.utils.build_agent import agent_setup

            setup_result = agent_setup(config)
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

        # --- Repeat steps 1–3 for each run ---
        run_ids: list[str] = []
        try:
            for run_num in range(1, total_runs + 1):
                current_run_id = str(_uuid.uuid4())
                run_ids.append(current_run_id)

                if total_runs > 1:
                    console.print(
                        f"\n[bold cyan]--- Run {run_num}/{total_runs} "
                        f"(id: {current_run_id[:8]}…) ---[/]"
                    )

                # --- Step 1: Exploration (is_req=false) ---
                if not skip_exploration and not only_transcribe:
                    exploration_time = config.time_exploration
                    console.print(
                        Panel(
                            f"[bold]Step 1/4:[/] Exploration (is_req=false, {exploration_time}s)",
                            style="blue",
                        )
                    )
                    exploration_config = AppConfig(
                        apk_name=config.apk_name,
                        package_name=config.package_name,
                        is_req=False,
                        is_coverage=config.is_coverage,
                        time_exploration=exploration_time,
                        time_guided=config.time_guided,
                        source_code=config.source_code,
                    )
                    try:
                        run(
                            mode=mode.value,
                            max_time=exploration_time,
                            max_steps=max_steps,
                            config=exploration_config,
                            run_id=current_run_id,
                        )
                    except KeyboardInterrupt:
                        console.print("[yellow]Interrupted.[/]")
                        raise typer.Exit(code=130) from None
                    except Exception as e:
                        console.print(f"[red]Exploration error: {e}[/]")
                        continue

                # --- Step 2: Generate requirements ---
                if not skip_requirements and not only_transcribe:
                    console.print(
                        Panel("[bold]Step 2/4:[/] Generate requirements.csv", style="blue")
                    )
                    if not config.source_code:
                        console.print("[yellow]No source_code configured, skipping.[/]")
                    else:
                        try:
                            from rlmobtest.training.generate_requirements import process_app

                            client = ChatOllama(model=llm_model, base_url=DEFAULT_OLLAMA_BASE_URL)
                            process_app(config, client, all_dates=all_dates)
                        except Exception as e:
                            console.print(f"[red]Requirements error: {e}[/]")

                # --- Step 3: Guided training (is_req=true) ---
                if not skip_guided and not only_transcribe:
                    guided_time = config.time_guided
                    console.print(
                        Panel(
                            f"[bold]Step 3/4:[/] Guided training (is_req=true, {guided_time}s)",
                            style="blue",
                        )
                    )
                    guided_config = AppConfig(
                        apk_name=config.apk_name,
                        package_name=config.package_name,
                        is_req=True,
                        is_coverage=config.is_coverage,
                        time_exploration=config.time_exploration,
                        time_guided=guided_time,
                        source_code=config.source_code,
                    )
                    try:
                        run(
                            mode=mode.value,
                            max_time=guided_time,
                            max_steps=max_steps,
                            config=guided_config,
                            run_id=current_run_id,
                        )
                    except KeyboardInterrupt:
                        console.print("[yellow]Interrupted.[/]")
                        raise typer.Exit(code=130) from None
                    except Exception as e:
                        console.print(f"[red]Guided training error: {e}[/]")
                        continue

            # --- Step 4: Transcription (all runs collected) ---
            console.print(Panel("[bold]Step 4/4:[/] Transcription (CrewAI)", style="blue"))
            if all_dates:
                runs_found = find_all_days(pkg, mode.value, OUTPUT_BASE)
            else:
                from datetime import datetime as _dt

                _now = _dt.now()
                _today = (_now.strftime("%Y"), _now.strftime("%m"), _now.strftime("%d"))
                _day_path = OUTPUT_BASE / pkg / mode.value / _today[0] / _today[1] / _today[2]
                runs_found = [
                    (_today[0], _today[1], _today[2], run_dir.name)
                    for run_dir in sorted(_day_path.iterdir())
                    if run_dir.is_dir() and (run_dir / "test_cases").exists()
                    and any((run_dir / "test_cases").iterdir())
                ] if _day_path.exists() else []

            if not runs_found:
                console.print("[yellow]No test_cases to transcribe.[/]")
            else:
                for year, month, day, rid in runs_found:
                    run_path = OUTPUT_BASE / pkg / mode.value / year / month / day / rid
                    tc_path = run_path / "test_cases"
                    tr_path = run_path / "transcriptions"

                    if not tc_path.exists() or not any(tc_path.iterdir()):
                        continue

                    console.print(f"  [dim]Transcribing {year}/{month}/{day}/{rid[:8]}…[/]")
                    try:
                        transcribe_folder(
                            input_folder=tc_path,
                            output_folder=tr_path,
                            model_name=f"ollama/{llm_model}",
                            screenshots_folder=run_path / "screenshots",
                            app_context=app_context,
                        )
                    except Exception as e:
                        console.print(f"  [red]Transcription error: {e}[/]")

                # --- Report ---
                from rlmobtest.training.report import generate_report

                run_paths = [
                    OUTPUT_BASE / pkg / mode.value / y / m / d / rid
                    for y, m, d, rid in runs_found
                ]
                try:
                    generate_report(
                        run_paths,
                        package_name=pkg,
                        agent_type=mode.value,
                        source_code=config.source_code or None,
                    )
                except Exception as e:
                    console.print(f"[red]Report error: {e}[/]")

        finally:
            if run_ids:
                from rich.table import Table as _Table
                tbl = _Table(title=f"Run IDs — {pkg}", show_lines=True)
                tbl.add_column("#", style="dim", justify="right")
                tbl.add_column("UUID", style="cyan")
                for idx, rid in enumerate(run_ids, 1):
                    tbl.add_row(str(idx), rid)
                console.print(tbl)

    console.print(Panel.fit("[bold green]Pipeline complete[/]", border_style="green"))
