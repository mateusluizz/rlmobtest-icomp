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
    date: Annotated[
        str | None,
        typer.Option("--date", "-d", help="Specific date to generate report for (YYYY-MM-DD)"),
    ] = None,
):
    """
    Generate HTML report from existing output data (no transcription or training).

    Examples:
        rlmobtest report --all-dates -m original
        rlmobtest report --app com.blogspot.e_kanivets.moneytracker --all-dates
        rlmobtest report --date 2026-03-28
    """
    from rlmobtest.constants.paths import CONFIG_JSON_PATH
    from rlmobtest.training.report import generate_report
    from rlmobtest.transcription.crew_transcriber import find_all_days
    from rlmobtest.utils.config_reader import ConfRead

    # Build package→source_code lookup from settings
    source_code_map: dict[str, str] = {}
    try:
        all_configs = ConfRead(CONFIG_JSON_PATH.as_posix()).read_all_settings()
        source_code_map = {c.package_name: c.source_code for c in all_configs if c.source_code}
    except Exception:
        pass

    if not OUTPUT_BASE.exists():
        console.print("[red]Output directory does not exist.[/]")
        raise typer.Exit(code=1)

    if app_filter:
        packages = app_filter
    else:
        packages = [
            d.name
            for d in sorted(OUTPUT_BASE.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]

    if not packages:
        console.print("[yellow]No apps found in output directory.[/]")
        raise typer.Exit(code=1)

    from datetime import datetime as _dt

    if date and all_dates:
        console.print("[red]--date and --all-dates are mutually exclusive.[/]")
        raise typer.Exit(code=1)

    specific_day: tuple[str, str, str] | None = None
    if date:
        try:
            _parsed = _dt.strptime(date, "%Y-%m-%d")
            specific_day = (
                _parsed.strftime("%Y"),
                _parsed.strftime("%m"),
                _parsed.strftime("%d"),
            )
        except ValueError:
            console.print(f"[red]Invalid date format '{date}'. Use YYYY-MM-DD.[/]")
            raise typer.Exit(code=1)

    generated = 0

    for pkg in packages:
        if all_dates:
            days = find_all_days(pkg, mode.value, OUTPUT_BASE)
        elif specific_day:
            _tc = (
                OUTPUT_BASE
                / pkg
                / mode.value
                / specific_day[0]
                / specific_day[1]
                / specific_day[2]
                / "test_cases"
            )
            days = [specific_day] if _tc.is_dir() and any(_tc.iterdir()) else []
        else:
            _now = _dt.now()
            _today = (_now.strftime("%Y"), _now.strftime("%m"), _now.strftime("%d"))
            _today_tc = (
                OUTPUT_BASE / pkg / mode.value / _today[0] / _today[1] / _today[2] / "test_cases"
            )
            days = [_today] if _today_tc.is_dir() and any(_today_tc.iterdir()) else []

        if not days:
            console.print(f"[yellow]{pkg}:[/] no data found for mode={mode.value}")
            continue

        run_paths = [OUTPUT_BASE / pkg / mode.value / y / m / d for y, m, d in days]

        try:
            data = generate_report(
                run_paths,
                package_name=pkg,
                agent_type=mode.value,
                source_code=source_code_map.get(pkg),
            )
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
        console.print("\n[yellow]No reports generated. Check --mode, --date, or --all-dates flags.[/]")
