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
from datetime import datetime
from pathlib import Path

import pandas as pd
from langchain_ollama import ChatOllama
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from rlmobtest.constants.actions import normalize_action_type, normalize_id
from rlmobtest.constants.llm import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.utils.app_context import extract_xml_contents as _extract_xml_contents
from rlmobtest.utils.config_reader import ConfRead

console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_CODES_DIR = BASE_DIR / "inputs" / "source_codes"


def extract_apk_knowledge(archive_path: Path, package_name: str) -> list[dict]:
    """Extract Android component IDs from source code XML files (zip or tar.gz)."""
    console.print(f"\n[cyan]Extracting knowledge base:[/] [dim]{archive_path.name}[/]")
    components = []
    try:
        for _xml_name, content in _extract_xml_contents(archive_path):
            matches = re.finditer(r'<([\w.]+)[^>]+android:id="@\+id/([^"]+)"', content)
            for m in matches:
                view_type = m.group(1).split(".")[-1]
                id_name = m.group(2)
                components.append(
                    {
                        "field": view_type,
                        "full_id": f"{package_name}:id/{id_name}",
                        "short_id": id_name,
                    }
                )
    except Exception as e:
        console.print(f"  [red]Failed to read archive:[/] {e}")
    console.print(f"  [green]{len(components)}[/] component(s) extracted")
    return components


def process_test_case(file_path: Path, client: ChatOllama) -> dict | None:
    """Send test case text to Ollama and parse the JSON response."""
    prompt = (
        "Analyze the Android test log and extract the actions into pure JSON. "
        "You must use these fields: "
        "activity (full path), "
        "field (component type in lowercase, e.g.: edittext, button, textview), "
        "id_ref (mentioned resource id), action_type, value. "
        "Example action_type values: click, type, select. "
        'Return only the JSON object: {"actions": []}'
    )
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        msg = [{"role": "user", "content": prompt + f"\n\nTexto: {text}"}]

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
        console.print(f"    [red]Invalid JSON:[/] {e}")
        return None
    except Exception as e:
        console.print(f"    [red]LLM error:[/] {e}")
        return None


# Widget-type prefixes used in Android resource IDs (e.g., btn_login → login)
_WIDGET_PREFIXES = re.compile(
    r"^(et|til|btn|tv|iv|cb|rb|spinner|cv|lv|rv|action|view|tab|tabs|drawer|nav)_",
    re.IGNORECASE,
)


def _normalize_widget_id(id_str: str) -> str:
    """Remove widget-type prefix for semantic comparison of Android resource IDs."""
    return _WIDGET_PREFIXES.sub("", id_str).lower()


def resolve_best_id(
    mentioned_id: str | None, apk_base: list[dict], package_name: str
) -> tuple[str, str]:
    """Resolve a mentioned ID to the full resource ID from the APK base.

    Two-pass matching:
    1. Exact match — fast, no regression.
    2. Normalized prefix match — handles LLM prefix mismatches (btn_login vs login_btn).
    """
    if not mentioned_id:
        return "N/A", "view"
    cleaned = mentioned_id.replace("@+id/", "").replace("id/", "").lower()

    # Pass 1: exact match
    for item in apk_base:
        if cleaned == item["short_id"].lower():
            return item["full_id"], item["field"].lower()

    # Pass 2: normalized prefix match (strips widget-type prefix before comparing)
    norm_cleaned = _normalize_widget_id(cleaned)
    for item in apk_base:
        if norm_cleaned == _normalize_widget_id(item["short_id"]):
            return item["full_id"], item["field"].lower()

    return f"{package_name}:id/{cleaned}", "view"


def find_run_paths(package_name: str, all_dates: bool = False) -> list[Path]:
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


def _infer_activity_from_filename(tc_path: Path, package_name: str) -> str | None:
    """Infer the Activity class name from a test case filename.

    TC filenames follow the pattern: TC_.activity.path.ClassName_timestamp.txt
    Returns the full activity path (e.g. 'com.example.activity.MainActivity')
    or None if it cannot be inferred.
    """
    parts = tc_path.stem.split("_")
    if len(parts) < 2 or not parts[1]:
        return None
    raw = parts[1].lstrip(".")
    if not raw:
        return None
    # raw is like "activity.account.AccountsActivity"
    # Reconstruct full path: package_name + "." + raw
    return f"{package_name}.{raw}"


def _resolve_activity(llm_activity: str, filename_hint: str | None, package_name: str) -> str:
    """Choose the best activity name between LLM output and filename hint.

    If the LLM returned just the package name (no specific Activity class),
    prefer the filename hint which always contains the real Activity.
    """
    # Normalize: extract the last component (class name)
    llm_class = re.split(r"[./]", llm_activity.strip())[-1]

    # If LLM returned the package name itself or something too generic, use hint
    if (
        llm_activity.strip() == package_name
        or llm_class.lower() == package_name.split(".")[-1].lower()
        or llm_class == "UnknownActivity"
    ):
        return filename_hint or llm_activity

    return llm_activity


def process_app(config, client: ChatOllama, *, all_dates: bool = False) -> None:
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

    if not source_code:
        console.print("[yellow]No source_code configured, skipping.[/]")
        return

    source_path = SOURCE_CODES_DIR / source_code
    if not source_path.exists():
        console.print(f"[red]Source code not found:[/] {source_path}")
        return

    run_paths = find_run_paths(package_name, all_dates=all_dates)
    if not run_paths:
        console.print("[yellow]No test_cases in output. Run exploration first.[/]")
        return

    console.print(f"[green]{len(run_paths)}[/] run path(s) found")

    apk_base = extract_apk_knowledge(source_path, package_name)

    for run_path in run_paths:
        rel = run_path.relative_to(OUTPUT_BASE / package_name)
        console.print(f"\n[bold cyan]Run path:[/] {rel}")

        test_cases = sorted((run_path / "test_cases").glob("*.txt"))
        if not test_cases:
            console.print("  [yellow]No test_cases in this run path.[/]")
            continue

        dataset = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=len(test_cases))

            for tc_path in test_cases:
                progress.update(task, description=f"[cyan]{tc_path.name}[/]")

                # Infer activity from TC filename (TC_.activity.path.Name_timestamp)
                tc_activity_hint = _infer_activity_from_filename(tc_path, package_name)

                result = process_test_case(tc_path, client)

                if result and ("actions" in result or "acoes" in result):
                    actions = result.get("actions") or result["acoes"]
                    progress.console.print(
                        f"  [green]{tc_path.name}[/] -> [bold]{len(actions)}[/] action(s)"
                    )
                    for action in actions:
                        raw_action = action.get("action_type") or "click"
                        action_type = normalize_action_type(raw_action)
                        if action_type is None:
                            continue  # skip junk (error, warn, etc.)

                        real_id, real_type = resolve_best_id(
                            action.get("id_ref"), apk_base, package_name
                        )
                        real_id = normalize_id(real_id)

                        # Use LLM activity, but fall back to filename hint
                        # when LLM returns just the package name or nothing useful
                        raw_activity = (action.get("activity") or "UnknownActivity").replace(
                            "/.", "."
                        )
                        activity = _resolve_activity(raw_activity, tc_activity_hint, package_name)

                        dataset.append(
                            {
                                "activity": activity,
                                "field": (
                                    real_type
                                    if real_type != "view"
                                    else (action.get("field") or "view").lower()
                                ),
                                "id": real_id,
                                "action_type": action_type,
                                "value": action.get("value") or "",
                            }
                        )
                else:
                    progress.console.print(f"  [yellow]{tc_path.name}[/] -> no actions")

                progress.advance(task)

        if not dataset:
            console.print("  [red]No actions extracted in this run path.[/]")
            continue

        # Show summary table
        table = Table(title=f"Requirements ({len(dataset)} actions)", show_lines=True)
        table.add_column("Activity", style="dim")
        table.add_column("Field", style="cyan")
        table.add_column("ID", style="dim")
        table.add_column("Action", style="magenta")
        table.add_column("Value")
        for row in dataset[:20]:
            table.add_row(
                row["activity"],
                row["field"],
                row["id"],
                row["action_type"],
                row.get("value") or "",
            )
        if len(dataset) > 20:
            table.add_row("...", "...", "...", "...", "...")
        console.print(table)

        # Save requirements.csv in the run_path (deduplicated)
        csv_path = run_path / "requirements.csv"
        df = pd.DataFrame(dataset)[["activity", "field", "id", "action_type", "value"]]
        raw_count = len(df)
        df = df.drop_duplicates()
        df.to_csv(csv_path, index=False)

        console.print(f"\n[bold green]requirements.csv saved:[/] {csv_path}")
        console.print(
            f"[dim]{len(df)} action(s) exported ({raw_count - len(df)} duplicates removed)[/]"
        )


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
        default=DEFAULT_LLM_MODEL,
        help=f"Ollama model (default: {DEFAULT_LLM_MODEL})",
    )
    args = parser.parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]Generate Requirements[/bold cyan]\n"
            "[dim]Extract requirements from test_cases + source code via Ollama[/dim]",
            border_style="cyan",
        )
    )

    # Read settings
    reader = ConfRead(CONFIG_JSON_PATH.as_posix())
    configs = reader.read_all_settings()

    apps_with_source = [c for c in configs if c.source_code]
    console.print(f"\n[bold]{len(configs)}[/] app(s) in settings.json")
    console.print(f"[bold]{len(apps_with_source)}[/] app(s) with source_code configured")

    if not apps_with_source:
        console.print("[red]No apps with source_code. Configure in settings.json.[/]")
        return

    # Initialize Ollama client
    client = ChatOllama(model=args.llm_model, base_url=DEFAULT_OLLAMA_BASE_URL)
    console.print(f"[green]Ollama client ready[/] [dim]({args.llm_model})[/]\n")

    for i, config in enumerate(apps_with_source, 1):
        console.print(f"\n[bold yellow]{'=' * 60}[/]")
        console.print(f"[bold yellow]  App {i}/{len(apps_with_source)}[/]")
        console.print(f"[bold yellow]{'=' * 60}[/]")

        try:
            process_app(config, client, all_dates=args.all_dates)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/]")
            raise
        except Exception as e:
            console.print(f"[red]Error processing {config.package_name}:[/] {e}")
            continue

    console.print(
        Panel.fit("[bold green]Requirements generation complete[/]", border_style="green")
    )


if __name__ == "__main__":
    main()
