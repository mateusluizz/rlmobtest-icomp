"""Info command for the RLMobTest CLI."""

import urllib.error
import urllib.request

from rich.panel import Panel

from rlmobtest.cli import app, console
from rlmobtest.constants.paths import CONFIG_JSON_PATH
from rlmobtest.utils.config_reader import ConfRead


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
