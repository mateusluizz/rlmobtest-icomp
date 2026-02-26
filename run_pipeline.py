"""
Pipeline completo: exploração → requisitos → treino guiado → test cases.

Executa o fluxo inteiro para cada app configurado em settings.json:
    1. Exploração com is_req=false (DQN aprende via heurísticas)
    2. Geração de requirements.csv (Ollama + source code)
    3. Treino guiado com is_req=true (DQN usa happy path)
    4. Transcrição dos test cases (CrewAI)

Uso:
    python run_pipeline.py                          # fluxo completo
    python run_pipeline.py --skip-exploration       # pula etapa 1
    python run_pipeline.py --skip-requirements      # pula etapa 2
    python run_pipeline.py --only-transcribe        # só etapa 4
    python run_pipeline.py --mode original          # usa DQN original
"""

import argparse

from langchain_ollama import ChatOllama
from rich.console import Console
from rich.panel import Panel

from rlmobtest.constants.paths import CONFIG_JSON_PATH, OUTPUT_BASE
from rlmobtest.training import run
from rlmobtest.training.generate_requirements import processar_app
from rlmobtest.transcription.crew_transcriber import find_all_days, transcribe_folder
from rlmobtest.utils.config_reader import AppConfig, ConfRead

console = Console()


def make_config(base: AppConfig, is_req: bool) -> AppConfig:
    """Create a copy of the config with is_req_analysis toggled."""
    return AppConfig(
        apk_name=base.apk_name,
        package_name=base.package_name,
        is_req=is_req,
        is_coverage=base.is_coverage,
        time=base.time,
        source_code=base.source_code,
    )


def run_pipeline(
    mode: str = "improved",
    max_steps: int = 100,
    llm_model: str = "gemma3:4b",
    all_dates: bool = False,
    skip_exploration: bool = False,
    skip_requirements: bool = False,
    skip_guided: bool = False,
    only_transcribe: bool = False,
):
    reader = ConfRead(CONFIG_JSON_PATH.as_posix())
    configs = reader.read_all_settings()

    console.print(
        Panel.fit(
            f"[bold cyan]RLMobTest Pipeline[/bold cyan]\n"
            f"[dim]{len(configs)} app(s) | mode={mode} | max_steps={max_steps}[/dim]",
            border_style="cyan",
        )
    )

    for i, config in enumerate(configs, 1):
        pkg = config.package_name
        console.print(f"\n[bold yellow]{'=' * 60}[/]")
        console.print(f"[bold yellow]  App {i}/{len(configs)}: {pkg}[/]")
        console.print(f"[bold yellow]{'=' * 60}[/]")

        # --- Etapa 1: Exploração (is_req=false) ---
        if not skip_exploration and not only_transcribe:
            console.print(Panel("[bold]Etapa 1/4:[/] Exploracao (is_req=false)", style="blue"))
            exploration_config = make_config(config, is_req=False)
            try:
                run(
                    mode=mode,
                    max_time=config.time,
                    max_steps=max_steps,
                    config=exploration_config,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Interrompido pelo usuario.[/]")
                return
            except Exception as e:
                console.print(f"[red]Erro na exploracao: {e}[/]")
                continue

        # --- Etapa 2: Gerar requirements ---
        if not skip_requirements and not only_transcribe:
            console.print(Panel("[bold]Etapa 2/4:[/] Gerando requirements.csv", style="blue"))
            if not config.source_code:
                console.print("[yellow]Sem source_code, pulando requirements.[/]")
            else:
                try:
                    client = ChatOllama(model=llm_model, base_url="http://localhost:11434")
                    processar_app(config, client, all_dates=all_dates)
                except Exception as e:
                    console.print(f"[red]Erro ao gerar requirements: {e}[/]")

        # --- Etapa 3: Treino guiado (is_req=true) ---
        if not skip_guided and not only_transcribe:
            console.print(Panel("[bold]Etapa 3/4:[/] Treino guiado (is_req=true)", style="blue"))
            guided_config = make_config(config, is_req=True)
            try:
                run(
                    mode=mode,
                    max_time=config.time,
                    max_steps=max_steps,
                    config=guided_config,
                )
            except KeyboardInterrupt:
                console.print("[yellow]Interrompido pelo usuario.[/]")
                return
            except Exception as e:
                console.print(f"[red]Erro no treino guiado: {e}[/]")
                continue

        # --- Etapa 4: Transcrição ---
        console.print(Panel("[bold]Etapa 4/4:[/] Transcricao (CrewAI)", style="blue"))
        if all_dates:
            days = find_all_days(pkg, mode, OUTPUT_BASE)
        else:
            from datetime import datetime as _dt

            _now = _dt.now()
            _today = (_now.strftime("%Y"), _now.strftime("%m"), _now.strftime("%d"))
            _today_tc = OUTPUT_BASE / pkg / mode / _today[0] / _today[1] / _today[2] / "test_cases"
            days = [_today] if _today_tc.is_dir() and any(_today_tc.iterdir()) else []

        if not days:
            console.print("[yellow]Sem test_cases para transcrever.[/]")
            continue

        for year, month, day in days:
            day_path = OUTPUT_BASE / pkg / mode / year / month / day
            tc_path = day_path / "test_cases"
            tr_path = day_path / "transcriptions"

            if not tc_path.exists() or not any(tc_path.iterdir()):
                continue

            console.print(f"  [dim]Transcrevendo {year}/{month}/{day}...[/]")
            try:
                transcribe_folder(
                    input_folder=tc_path,
                    output_folder=tr_path,
                    model_name=f"ollama/{llm_model}",
                )
            except Exception as e:
                console.print(f"  [red]Erro na transcricao: {e}[/]")

        # --- Relatório ---
        if days:
            from rlmobtest.training.report import generate_report

            run_paths = [OUTPUT_BASE / pkg / mode / y / m / d for y, m, d in days]
            try:
                generate_report(run_paths, package_name=pkg, agent_type=mode)
            except Exception as e:
                console.print(f"[red]Erro no relatorio: {e}[/]")

    console.print(Panel.fit("[bold green]Pipeline completo[/]", border_style="green"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RLMobTest - Pipeline completo")
    parser.add_argument("--mode", default="improved", choices=["original", "improved"])
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument(
        "--llm-model",
        default="gemma3:4b",
        help="Model for requirements and transcription",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Process test_cases from all dates (default: today only)",
    )
    parser.add_argument("--skip-exploration", action="store_true")
    parser.add_argument("--skip-requirements", action="store_true")
    parser.add_argument("--skip-guided", action="store_true")
    parser.add_argument("--only-transcribe", action="store_true")

    args = parser.parse_args()
    run_pipeline(
        mode=args.mode,
        max_steps=args.max_steps,
        llm_model=args.llm_model,
        all_dates=args.all_dates,
        skip_exploration=args.skip_exploration,
        skip_requirements=args.skip_requirements,
        skip_guided=args.skip_guided,
        only_transcribe=args.only_transcribe,
    )
