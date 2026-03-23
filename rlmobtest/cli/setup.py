"""Setup command for the RLMobTest CLI."""

import urllib.error
import urllib.request
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from rlmobtest.cli import app, console
from rlmobtest.constants.paths import CONFIG_JSON_PATH
from rlmobtest.utils.config_reader import ConfRead


def _check_ollama() -> bool:
    """Return True if Ollama server is reachable."""
    try:
        with urllib.request.urlopen("http://localhost:11434", timeout=3):
            return True
    except Exception:
        return False


@app.command()
def setup(
    app_filter: Annotated[
        list[str] | None,
        typer.Option("--app", "-a", help="Setup specific app(s) by package name"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-build/re-download even if artifacts exist"),
    ] = False,
    agent: Annotated[
        bool,
        typer.Option("--agent", help="Use autonomous build agent with auto-fix and retry"),
    ] = True,
):
    """
    Setup JaCoCo prerequisites: build APK, copy classfiles, download jacococli.jar.

    Uses the autonomous build agent by default, which auto-detects AGP/Gradle/Java
    versions, fixes repositories, installs SDK components, and retries on failure.

    Examples:
        rlmobtest setup                              # Setup with build agent
        rlmobtest setup --no-agent                   # Setup without auto-fix
        rlmobtest setup --app com.example.app         # Setup specific app
        rlmobtest setup --force                       # Force rebuild
    """
    while not _check_ollama():
        console.print(
            "\n[bold red]⚠ Servidor Ollama está offline.[/bold red]\n"
            "[dim]Inicie o servidor com: [bold]ollama serve[/bold][/dim]\n"
        )
        typer.confirm("Pressione Enter após subir o servidor para continuar...", default=True)

    if agent:
        from rlmobtest.utils.build_agent import agent_setup as run_setup
    else:
        from rlmobtest.utils.jacoco_setup import run_setup

    try:
        settings_reader = ConfRead(CONFIG_JSON_PATH.as_posix())
        all_configs = settings_reader.read_all_settings()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(code=1) from None

    # Filter apps with coverage enabled
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
            f"[bold cyan]JaCoCo Setup[/bold cyan]\n"
            f"[dim]{len(configs)} app(s) | force={force}[/dim]",
            border_style="cyan",
        )
    )

    results_table = Table(title="Setup Results")
    results_table.add_column("App", style="cyan")
    results_table.add_column("APK", justify="center")
    results_table.add_column("Classfiles", justify="center")
    results_table.add_column("jacococli", justify="center")

    for config in configs:
        console.print(f"\n[bold]{config.package_name}[/]")
        result = run_setup(config, force=force)

        def _icon(ok: bool) -> str:
            return "[green]OK[/]" if ok else "[yellow]--[/]"

        results_table.add_row(
            config.package_name,
            _icon(result["apk_built"]),
            _icon(result["classfiles_copied"]),
            _icon(result["jacococli_downloaded"]),
        )

    console.print()
    console.print(results_table)
