# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato e baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.1.11] - 2026-03-22

### Added
- `coverage_reward()` em `rlmobtest/training/reward.py`: bônus incremental por novas linhas (+5/%) e branches (+10/%) cobertas
- `_get_step_coverage()` em `rlmobtest/training/loop.py`: obtém métricas JaCoCo sem lançar exceção
- Constante `COVERAGE_CHECK_INTERVAL = 5` (verificação de cobertura a cada 5 steps)
- JaCoCo integrado ao loop de treinamento: quando `is_coverage=true`, o agente recebe bônus de recompensa proporcional ao aumento de cobertura de linhas e branches a cada 5 steps

### Changed
- Loop de treinamento (`loop.py`) agora inicializa `prev_coverage` antes dos episódios e calcula `coverage_reward` a cada `COVERAGE_CHECK_INTERVAL` steps

---

## [0.1.7] - 2026-03-02

### Added
- Modulo `rlmobtest/utils/app_context.py` para extrair contexto do app (AndroidManifest, layouts, strings.xml) de arquivos source code
- Contexto do app injetado nos prompts do CrewAI e LangChain para transcricoes mais precisas
- Arquivo centralizado de configuracao LLM (`rlmobtest/constants/llm.py`)
- Documentacao: `docs/contexto_llm_transcricao.md` (contexto LLM na transcricao)
- Documentacao: `docs/cli_commands.md` (referencia completa de comandos CLI)
- Argumentos `--source-code` e `--package` no CLI do crew_transcriber
- Cabecalhos de coluna no `requirements.csv` (`activity,field,id,action_type,value`)

### Changed
- Modelo LLM padrao alterado de `gemma3:4b` para `gemma3:12b`
- Funcao `extract_xml_contents()` movida de `generate_requirements.py` para modulo compartilhado `app_context.py`
- Todas as constantes de modelo LLM e URL agora centralizadas em `constants/llm.py`
- `report.py` detecta automaticamente cabecalhos no CSV (compativel com arquivos antigos)

### Fixed
- Compatibilidade retroativa na leitura de `requirements.csv` sem cabecalho

---

## [0.1.6] - 2026-02-28

### Added
- Pipeline completo com 4 etapas (exploracao, requirements, treino guiado, transcricao)
- Comando `rlmobtest pipeline` com opcoes de skip por etapa
- Comando `rlmobtest report` para geracao de relatorio HTML
- Comando `rlmobtest clean` para limpeza de output com filtros
- Comando `rlmobtest info` com status do Ollama
- Geracao de `requirements.csv` via Ollama + source code
- Relatorio HTML com cobertura de requirements e metricas de treinamento

### Changed
- CLI modularizado em subcomandos Typer separados
- Estrutura do pipeline refatorada para suportar multiplos apps sequencialmente

---

## [0.1.3] - 2026-02-05

### Added
- Separação de outputs por tipo de agente (original/improved)
- Documentos de discussão para decisões arquiteturais
- Correção de carregamento de checkpoints para DuelingDQN
- Suporte para treinar múltiplos apps via flag `--app` (pode ser usado múltiplas vezes)
- Função `run_all()` para treinamento sequencial de múltiplos APKs
- Verificação do status do servidor Ollama no comando `info`
- CLI do transcriber com filtro por data (`--date`) e processamento de múltiplos dias
- Dependência `litellm` para suporte a múltiplos LLMs

### Changed
- Estrutura de output: `{apk}/{agent_type}/{year}/{month}/{day}/`
- Modelo padrão do transcriber alterado para `gemma3:4b`
- Removido campo `resolution` do config (não utilizado)

### Fixed
- Correção de paths dos test_cases no android_env para usar diretório correto
- Criação automática de diretórios de test_case antes de escrever arquivos

---

## [0.1.2] - 2026-02-01

### Added
- Estrutura de output baseada em data: `{apk}/{year}/{month}/{day}/`
- Sistema de checkpoint com resume de treinamento
- Flag `--checkpoint` para retomar treinamentos
- Salvamento automático de `feature_size` no checkpoint

### Fixed
- Carregamento de checkpoints DuelingDQN com lazy initialization

---

## [0.1.1] - 2026-01-15

### Added
- CLI com Typer para comandos estruturados
- Comando `train` com opções --time, --episodes, --mode
- Transcrição automática de test cases com CrewAI
- Agente CrewAI para transcrição de casos de teste

### Changed
- Reorganização do projeto em pacote `rlmobtest`
- Migração de `main.py` para `rlmobtest/__main__.py`

---

## [0.1.0] - 2025-12-01

### Added
- Sistema de logs de progresso em tempo real
- Sistema Anti-Stuck para escapar de telas problemáticas
- Detecção automática de dialogs (DatePicker, TimePicker, etc.)
- Timeout em acoes UI (30s) para evitar travamentos
- Barra de progresso visual com Rich
- Escolha entre treinamento por tempo ou episódios
- Logging por execução (arquivos separados)
- Tracking de duração de episodio
- Interface visual melhorada com Rich (cores e formatação)

### Changed
- Tempo de treinamento padrão: 30s -> 300s (5 min)

### Fixed
- Tratamento robusto de UiObjectNotFoundError
- Verificação de existência de elementos antes de acoes

---

## [0.0.1] - 2025-11-01

### Added
- Implementação inicial do RL Mobile Test
- Agente DQN para exploração de apps Android
- Integração com uiautomator2
- Geração de test cases em formato texto
- Suporte a analise de cobertura

---

[Unreleased]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.11...HEAD
[0.1.11]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.7...v0.1.11
[0.1.7]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.3...v0.1.6
[0.1.3]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/seu-usuario/rlmobtest-icomp/releases/tag/v0.0.1
