"""Report command for the RLMobTest CLI."""

from typing import Annotated

import typer

from rlmobtest.cli import DQNMode, app, console
from rlmobtest.constants.paths import OUTPUT_BASE


@app.command()
def report(
    app_filter: Annotated[
        list[str] | None,
        typer.Option("--app", "-a", help="Package name(s) to generate report for"),
    ] = None,
    mode: Annotated[
        DQNMode,
        typer.Option("--mode", "-m", help="Agent type"),
    ] = DQNMode.improved,
    all_dates: Annotated[
        bool,
        typer.Option("--all-dates", help="Include all dates (default: today only)"),
    ] = False,
):
    """
    Generate HTML report from existing output data (no transcription or training).

    Examples:
        rlmobtest report --all-dates -m original
        rlmobtest report --app com.blogspot.e_kanivets.moneytracker --all-dates
    """
    from rlmobtest.training.report import generate_report
    from rlmobtest.transcription.crew_transcriber import find_all_days

    if not OUTPUT_BASE.exists():
        console.print("[red]Output directory does not exist.[/]")
        raise typer.Exit(code=1)

    if app_filter:
        packages = app_filter
    else:
        packages = [
            d.name for d in sorted(OUTPUT_BASE.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]

    if not packages:
        console.print("[yellow]No apps found in output directory.[/]")
        raise typer.Exit(code=1)

    generated = 0

    for pkg in packages:
        if all_dates:
            days = find_all_days(pkg, mode.value, OUTPUT_BASE)
        else:
            from datetime import datetime as _dt

            _now = _dt.now()
            _today = (_now.strftime("%Y"), _now.strftime("%m"), _now.strftime("%d"))
            _today_tc = (
                OUTPUT_BASE / pkg / mode.value
                / _today[0] / _today[1] / _today[2] / "test_cases"
            )
            days = [_today] if _today_tc.is_dir() and any(_today_tc.iterdir()) else []

        if not days:
            console.print(f"[yellow]{pkg}:[/] no data found for mode={mode.value}")
            continue

        run_paths = [
            OUTPUT_BASE / pkg / mode.value / y / m / d for y, m, d in days
        ]

        try:
            data = generate_report(run_paths, package_name=pkg, agent_type=mode.value)
            generated += 1
            console.print(
                f"  [dim]{len(days)} run path(s), "
                f"{data['test_cases_generated']} test cases, "
                f"{data['transcriptions']} transcriptions[/]"
            )
        except Exception as e:
            console.print(f"[red]Error generating report for {pkg}: {e}[/]")

    if generated:
        console.print(f"\n[green]{generated} report(s) generated.[/]")
    else:
        console.print(
            "\n[yellow]No reports generated. Check --mode and --all-dates flags.[/]"
        )
