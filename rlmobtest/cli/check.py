"""Check command for the RLMobTest CLI — pre-validate build prerequisites."""

from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from rlmobtest.cli import app, console
from rlmobtest.constants.paths import CONFIG_JSON_PATH
from rlmobtest.utils.config_reader import ConfRead


def _icon(ok: bool | None) -> str:
    if ok is None:
        return "[dim]--[/]"
    return "[green]OK[/]" if ok else "[red]FAIL[/]"


@app.command()
def check(
    app_filter: Annotated[
        list[str] | None,
        typer.Option("--app", "-a", help="Check specific app(s) by package name"),
    ] = None,
):
    """
    Pre-validate prerequisites before running setup or pipeline.

    Checks Java version, Gradle compatibility, Android SDK, and existing artifacts
    for each app with is_coverage=true.

    Examples:
        rlmobtest check                              # Check all coverage apps
        rlmobtest check --app io.github.silinote      # Check specific app
    """
    from rlmobtest.utils.jacoco_setup import (
        check_prerequisites,
        find_gradle_project,
        resolve_source_dir,
    )

    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        all_configs = settings_reader.read_all_settings()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    configs = [c for c in all_configs if c.is_coverage]

    if app_filter:
        configs = [c for c in configs if c.package_name in app_filter]
        not_found = set(app_filter) - {c.package_name for c in configs}
        if not_found:
            console.print(
                f"[red]App(s) not found or coverage disabled: {', '.join(not_found)}[/red]"
            )
            raise typer.Exit(code=1)

    if not configs:
        console.print("[yellow]No apps with is_coverage=true found in settings.json[/yellow]")
        raise typer.Exit(code=0)

    console.print(
        Panel.fit(
            f"[bold cyan]Pre-flight Check[/bold cyan]\n[dim]{len(configs)} app(s) to check[/dim]",
            border_style="cyan",
        )
    )

    all_ok = True

    for config in configs:
        console.print(f"\n[bold]{config.package_name}[/]")

        # Resolve source and project dirs
        project_dir = None
        if config.source_code:
            source_dir = resolve_source_dir(config.source_code)
            if source_dir:
                project_dir = find_gradle_project(source_dir)

        info = check_prerequisites(
            project_dir=project_dir,
            package_name=config.package_name,
        )

        # Build results table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Check", style="dim", min_width=25)
        table.add_column("Status")
        table.add_column("Details")

        # Java
        java_ver = info["java_version"]
        table.add_row(
            "Java",
            _icon(java_ver is not None),
            f"version {java_ver}" if java_ver else "not found",
        )

        # AGP
        agp_ver = info.get("agp_version")
        rec_gradle = info.get("recommended_gradle")
        rec_java_agp = info.get("recommended_java_for_agp")
        if agp_ver:
            agp_detail = f"version {agp_ver}"
            if rec_gradle:
                agp_detail += f" → Gradle {rec_gradle}, Java {rec_java_agp}"
            table.add_row("AGP", _icon(True), agp_detail)
        elif project_dir:
            table.add_row(
                "AGP",
                _icon(False),
                "not detected in build.gradle",
            )

        # Gradle
        gradle_ver = info["gradle_version"]
        if gradle_ver:
            gradle_detail = f"version {gradle_ver}"
            if not (project_dir / "gradlew").exists() if project_dir else False:
                gradle_detail += " [dim](wrapper will be generated)[/]"
        else:
            gradle_detail = "not found" if project_dir else "no source_code"
            if rec_gradle:
                gradle_detail += f" [cyan](setup will generate Gradle {rec_gradle} wrapper)[/]"
        table.add_row(
            "Gradle (wrapper)",
            _icon(gradle_ver is not None or rec_gradle is not None),
            gradle_detail,
        )

        # Compatibility
        target_java = rec_java_agp or (info["recommended_java"] if gradle_ver else None)
        if gradle_ver and java_ver:
            compat = info["java_compatible"]
            rec = info["recommended_java"]
            if compat:
                detail = f"Java {java_ver} + Gradle {gradle_ver}"
            else:
                detail = (
                    f"[red]Java {java_ver} too new for Gradle {gradle_ver} "
                    f"(max Java {rec})[/]\n"
                    f"                             "
                    f"Fix: [cyan]asdf install java temurin-{rec}.0.25+9 && "
                    f"asdf set -p java temurin-{rec}.0.25+9[/]"
                )
                all_ok = False
            table.add_row("Java/Gradle compat", _icon(compat), detail)
        elif target_java and java_ver:
            ok = java_ver <= target_java
            if ok:
                detail = f"Java {java_ver} (needs {target_java})"
            else:
                detail = (
                    f"[red]Java {java_ver} (needs {target_java})[/]\n"
                    f"                             "
                    f"Fix: [cyan]asdf install java temurin-{target_java}.0.25+9 && "
                    f"asdf set -p java temurin-{target_java}.0.25+9[/]"
                )
                all_ok = False
            table.add_row("Java/Gradle compat", _icon(ok), detail)

        # Android SDK
        table.add_row(
            "Android SDK",
            _icon(info["android_home"] is not None),
            str(info["android_home"]) if info["android_home"] else "not found",
        )

        # adb
        table.add_row("adb", _icon(info["has_adb"]), "")

        # Existing artifacts
        table.add_row(
            "classfiles",
            _icon(info["has_classfiles"]) if info["has_classfiles"] is not None else "[dim]--[/]",
            "exists" if info["has_classfiles"] else "will be generated by setup",
        )
        table.add_row(
            "jacococli.jar",
            _icon(info["has_jacococli"]),
            "exists" if info["has_jacococli"] else "will be downloaded by setup",
        )

        # Source code
        table.add_row(
            "source_code",
            _icon(project_dir is not None),
            str(config.source_code) if config.source_code else "not configured",
        )

        console.print(table)

        if not info.get("java_compatible", True):
            all_ok = False
        if not info["android_home"]:
            all_ok = False
        if java_ver is None:
            all_ok = False

    console.print()
    if all_ok:
        console.print("[bold green]All checks passed. Ready to run setup.[/]")
    else:
        console.print("[bold red]Some checks failed. Fix the issues above before running setup.[/]")
        raise typer.Exit(code=1)
