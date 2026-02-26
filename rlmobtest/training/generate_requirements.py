"""
Generate requirements.csv for each app based on exploration test_cases and source code.

Flow:
    1. Read apps from settings.json
    2. For each app, find source code in inputs/source_codes/{source_code}
    3. Find test_cases from previous exploration run in output/{package_name}/
    4. Extract Android component IDs from source code XML files
    5. Process test_cases with Ollama LLM to extract actions
    6. Save requirements.csv to output/{package_name}/requirements.csv
"""

import argparse
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from langchain_ollama import ChatOllama
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.config_reader import ConfRead

console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_CODES_DIR = BASE_DIR / "inputs" / "source_codes"


def extrair_base_conhecimento_apk(caminho_zip: Path, package_name: str) -> list[dict]:
    """Extract Android component IDs from source code XML files."""
    console.print(f"\n[cyan]Extraindo base de conhecimento:[/] [dim]{caminho_zip.name}[/]")
    componentes = []
    try:
        with zipfile.ZipFile(caminho_zip, "r") as z:
            for xml in [f for f in z.namelist() if f.endswith(".xml")]:
                with z.open(xml) as f:
                    conteudo = f.read().decode("utf-8", errors="ignore")
                    matches = re.finditer(r'<([\w.]+)[^>]+android:id="@\+id/([^"]+)"', conteudo)
                    for m in matches:
                        tipo_view = m.group(1).split(".")[-1]
                        id_nome = m.group(2)
                        componentes.append(
                            {
                                "field": tipo_view,
                                "id_completo": f"{package_name}:id/{id_nome}",
                                "id_curto": id_nome,
                            }
                        )
    except Exception as e:
        console.print(f"  [red]Falha ao ler ZIP:[/] {e}")
    console.print(f"  [green]{len(componentes)}[/] componente(s) extraido(s)")
    return componentes


def processar_texto_qa(caminho_arquivo: Path, client: ChatOllama) -> dict | None:
    """Send test case text to Ollama and parse the JSON response."""
    prompt = (
        "Analise o log de teste Android e extraia as acoes para um JSON puro. "
        "Use obrigatoriamente estes campos: "
        "activity (caminho completo), "
        "field (tipo do componente em lowercase, ex: edittext, button, textview), "
        "id_ref (id mencionado), action_type, value. "
        "Exemplo de action_type: click, type, select. "
        'Retorne apenas o objeto JSON: {"acoes": []}'
    )
    try:
        with open(caminho_arquivo, encoding="utf-8", errors="ignore") as f:
            texto = f.read()
        msg = [{"role": "user", "content": prompt + f"\n\nTexto: {texto}"}]

        res = client.invoke(msg)
        raw = res.content
        if isinstance(raw, str):
            content = raw
        elif isinstance(raw, list):
            first = raw[0]
            content = first["text"] if isinstance(first, dict) else str(first)
        else:
            content = str(raw)
        return json.loads(content.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError as e:
        console.print(f"    [red]JSON invalido:[/] {e}")
        return None
    except Exception as e:
        console.print(f"    [red]Erro LLM:[/] {e}")
        return None


def encontrar_melhor_id(
    id_mencionado: str | None, base_apk: list[dict], package_name: str
) -> tuple[str, str]:
    """Resolve a mentioned ID to the full resource ID from the APK base."""
    if not id_mencionado:
        return "N/A", "view"
    limpo = id_mencionado.replace("@+id/", "").replace("id/", "").lower()
    for item in base_apk:
        if limpo == item["id_curto"].lower():
            return item["id_completo"], item["field"].lower()
    return f"{package_name}:id/{limpo}", "view"


def encontrar_run_paths(package_name: str, all_dates: bool = False) -> list[Path]:
    """Find run_path dirs that contain test_cases.

    Args:
        package_name: The app package name.
        all_dates: If False (default), only look for today's test_cases.
                   If True, search all dates.
    """
    app_output = OUTPUT_BASE / package_name
    if not app_output.exists():
        return []

    run_paths = set()

    if all_dates:
        for tc_dir in app_output.rglob("test_cases"):
            if tc_dir.is_dir() and any(tc_dir.glob("*.txt")):
                run_paths.add(tc_dir.parent)
    else:
        now = datetime.now()
        year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
        for agent_dir in app_output.iterdir():
            if not agent_dir.is_dir():
                continue
            today_path = agent_dir / year / month / day
            tc_dir = today_path / "test_cases"
            if tc_dir.is_dir() and any(tc_dir.glob("*.txt")):
                run_paths.add(today_path)

    return sorted(run_paths)


def processar_app(config, client: ChatOllama, *, all_dates: bool = False) -> None:
    """Process a single app: extract knowledge + generate requirements."""
    package_name = config.package_name
    source_code = config.source_code

    console.print(
        Panel(
            f"[bold]{package_name}[/bold]\n"
            f"[dim]APK: {config.apk_name}  |  Source: {source_code or 'N/A'}[/dim]",
            title="App",
            border_style="blue",
        )
    )

    # Check source code
    if not source_code:
        console.print("[yellow]Sem source_code configurado, pulando.[/]")
        return

    source_path = SOURCE_CODES_DIR / source_code
    if not source_path.exists():
        console.print(f"[red]Source code nao encontrado:[/] {source_path}")
        return

    # Find run_paths from exploration
    run_paths = encontrar_run_paths(package_name, all_dates=all_dates)
    if not run_paths:
        console.print("[yellow]Nenhum test_case no output. Execute a exploracao primeiro.[/]")
        return

    console.print(f"[green]{len(run_paths)}[/] run path(s) encontrado(s)")

    # Extract component base from source code
    base_apk = extrair_base_conhecimento_apk(source_path, package_name)

    # Process each run_path
    for run_path in run_paths:
        rel = run_path.relative_to(OUTPUT_BASE / package_name)
        console.print(f"\n[bold cyan]Run path:[/] {rel}")

        test_cases = sorted((run_path / "test_cases").glob("*.txt"))
        if not test_cases:
            console.print("  [yellow]Sem test_cases neste run path.[/]")
            continue

        dataset_final = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processando...", total=len(test_cases))

            for tc_path in test_cases:
                progress.update(task, description=f"[cyan]{tc_path.name}[/]")

                resultado = processar_texto_qa(tc_path, client)

                if resultado and "acoes" in resultado:
                    acoes = resultado["acoes"]
                    progress.console.print(
                        f"  [green]{tc_path.name}[/] -> [bold]{len(acoes)}[/] acao(es)"
                    )
                    for acao in acoes:
                        id_real, tipo_real = encontrar_melhor_id(
                            acao.get("id_ref"), base_apk, package_name
                        )
                        dataset_final.append(
                            {
                                "activity": (acao.get("activity") or "UnknownActivity").replace(
                                    "/.", "."
                                ),
                                "field": (
                                    tipo_real
                                    if tipo_real != "view"
                                    else (acao.get("field") or "view").lower()
                                ),
                                "id": id_real,
                                "action_type": acao.get("action_type") or "click",
                                "value": acao.get("value") or "",
                            }
                        )
                else:
                    progress.console.print(f"  [yellow]{tc_path.name}[/] -> sem acoes")

                progress.advance(task)

        if not dataset_final:
            console.print("  [red]Nenhuma acao extraida neste run path.[/]")
            continue

        # Show summary table
        tabela = Table(title=f"Requirements ({len(dataset_final)} acoes)", show_lines=True)
        tabela.add_column("Activity", style="dim")
        tabela.add_column("Field", style="cyan")
        tabela.add_column("ID", style="dim")
        tabela.add_column("Action", style="magenta")
        tabela.add_column("Value")
        for row in dataset_final[:20]:
            tabela.add_row(
                row["activity"],
                row["field"],
                row["id"],
                row["action_type"],
                row.get("value") or "",
            )
        if len(dataset_final) > 20:
            tabela.add_row("...", "...", "...", "...", "...")
        console.print(tabela)

        # Save requirements.csv in the run_path (deduplicated)
        csv_path = run_path / "requirements.csv"
        df = pd.DataFrame(dataset_final)[["activity", "field", "id", "action_type", "value"]]
        raw_count = len(df)
        df = df.drop_duplicates()
        df.to_csv(csv_path, index=False, header=False)

        console.print(f"\n[bold green]requirements.csv salvo:[/] {csv_path}")
        console.print(f"[dim]{len(df)} acao(es) exportadas ({raw_count - len(df)} duplicatas removidas)[/]")


def main():
    """Main entry point: process all apps from settings.json."""
    parser = argparse.ArgumentParser(description="Generate requirements.csv from test_cases")
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Process test_cases from all dates (default: today only)",
    )
    parser.add_argument(
        "--llm-model",
        default="gemma3:4b",
        help="Ollama model (default: gemma3:4b)",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]Generate Requirements[/bold cyan]\n"
            "[dim]Extrai requisitos dos test_cases + source code via Ollama[/dim]",
            border_style="cyan",
        )
    )

    # Read settings
    reader = ConfRead(CONFIG_JSON_PATH.as_posix())
    configs = reader.read_all_settings()

    # Filter apps with source_code configured
    apps_with_source = [c for c in configs if c.source_code]
    console.print(f"\n[bold]{len(configs)}[/] app(s) no settings.json")
    console.print(f"[bold]{len(apps_with_source)}[/] app(s) com source_code configurado")

    if not apps_with_source:
        console.print("[red]Nenhum app com source_code. Configure no settings.json.[/]")
        return

    # Initialize Ollama client
    client = ChatOllama(model=args.llm_model, base_url="http://localhost:11434")
    console.print(f"[green]Ollama client pronto[/] [dim]({args.llm_model})[/]\n")

    # Process each app
    for i, config in enumerate(apps_with_source, 1):
        console.print(f"\n[bold yellow]{'=' * 60}[/]")
        console.print(f"[bold yellow]  App {i}/{len(apps_with_source)}[/]")
        console.print(f"[bold yellow]{'=' * 60}[/]")

        try:
            processar_app(config, client, all_dates=args.all_dates)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrompido pelo usuario.[/]")
            raise
        except Exception as e:
            console.print(f"[red]Erro ao processar {config.package_name}:[/] {e}")
            continue

    console.print(
        Panel.fit("[bold green]Geracao de requirements concluida[/]", border_style="green")
    )


if __name__ == "__main__":
    main()
