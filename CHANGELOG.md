# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato e baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.1.18] - 2026-03-31

### Added
- `entrypoint.sh`: script de inicialização que corrige permissões dos volumes montados (`inputs/`, `output/`, `config/`) e arquivos `gradlew` como root, depois dropa para o usuário `rlmob` via `gosu`
- Usuário não-root `rlmob` no container com Oh My Zsh, zsh-autosuggestions e zsh-completions; acesso root via `su -` com senha configurada por `ROOT_PASSWORD` no `.env`
- `asdf` v0.18.0 instalado em `/opt/asdf` (acessível a todos os usuários); `uv` instalado em `/usr/local/bin`
- `platform-tools` (adb) instalado via `sdkmanager` durante o build da imagem
- `docker-compose.yml`: `network_mode: host` no serviço `rlmobtest` para acesso ao ADB do host via `127.0.0.1:5037`; `ROOT_PASSWORD` passado como build arg
- Flag `--date`/`-d` no comando `rlmobtest report` para gerar relatório de um dia específico no formato `YYYY-MM-DD` (mutuamente exclusiva com `--all-dates`)

### Changed
- Container `rlmobtest-app` agora inicia como usuário `rlmob` em vez de root
- `OLLAMA_BASE_URL` alterado para `http://localhost:11434` (acesso via rede do host)
- `openjdk-17-jdk-headless` instalado via apt durante o build para viabilizar o `sdkmanager`

---

## [0.1.17] - 2026-03-28

### Added
- `Dockerfile`: imagem Ubuntu 24.04 com uv, asdf v0.18.0 (plugins Java e Gradle), Android SDK cmdline-tools, Oh My Zsh com zsh-autosuggestions e zsh-completions, e projeto instalado via `uv sync --frozen`
- `docker-compose.yml`: orquestração com dois serviços (`ollama` e `rlmobtest`) na mesma rede bridge, volumes para `inputs/`, `output/` e `rlmobtest/config/`, e `command: zsh` para abrir terminal interativo
- Seção "Instalação via Docker" no `README.md` com tutorial completo de uso via containers
- `OLLAMA_BASE_URL` lida de variável de ambiente em `rlmobtest/constants/llm.py` (fallback: `http://localhost:11434`), permitindo apontar para o container Ollama sem alterar código

---

## [0.1.16] - 2026-03-22

### Added
- Verificação do servidor Ollama no comando `rlmobtest setup`: se o servidor estiver offline, exibe aviso e aguarda o usuário iniciá-lo antes de prosseguir (`rlmobtest/cli/setup.py`)

### Changed
- Refatoração de estilo em toda a pasta `rlmobtest/`: ajuste de comprimento de linha, formatação consistente de listas, f-strings e chamadas de função (`cli/`, `training/`, `utils/`, `constants/`)

---

## [0.1.15] - 2026-03-22

### Added
- `OutputPaths.cumulative_coverage`: diretório compartilhado por todos os runs do mesmo app+agente (`output/{apk}/{agent_type}/cumulative_coverage/`)
- `_accumulate_coverage()` em `loop.py`: copia arquivos `.ec` de cada run para `cumulative_coverage/` ao final do treinamento
- `extra_state` no sistema de checkpoint (`checkpoint.py`): salva e restaura estado adicional (ex: `visited_activities`) entre runs
- `all_visited_activities`: set de activities vistas em todas as runs anteriores, persistido via checkpoint
- Recompensa de descoberta de activity dobrada (+20 em vez de +10) para activities nunca vistas em runs anteriores — incentiva o agente a explorar territórios novos ao retomar de checkpoint

### Changed
- `ModelCheckpoint.save()`: aceita parâmetro `extra_state=None` — armazenado no checkpoint sem quebrar compatibilidade com checkpoints antigos
- `ModelCheckpoint.load()`: retorna `(episode, steps_done, extra_state)` — `extra_state` é `{}` para checkpoints antigos
- `loop.py`: atualizado para a nova assinatura do `load()` e para passar `extra_state` em todos os `save()` calls

---

## [0.1.14] - 2026-03-22

### Changed
- **OriginalAgent** (`rlmobtest/training/agents.py`) — hiperparâmetros ajustados para maior exploração e melhor aprendizado:

  | Parâmetro    | Antes  | Depois | Justificativa |
  |-------------|--------|--------|---------------|
  | `memory`    | 10 000 | 50 000 | Mais diversidade de experiências no replay buffer |
  | `batch_size`| 256    | 128    | Atualizações mais frequentes com gradientes menos ruidosos |
  | `gamma`     | 0.999  | 0.99   | Foco mais imediato, reduz ruído de recompensas distantes |
  | `eps_decay` | 500    | 2000   | Explora por mais tempo antes de exploitar |

---

## [0.1.13] - 2026-03-22

### Added
- `SMART_INPUTS` dict em `rlmobtest/android/android_env.py`: valores de fronteira e edge cases por categoria (email, password, number, text, date, phone, currency)
- `_FIELD_TYPE_KEYWORDS` dict: mapeamento de palavras-chave para detecção de tipo de campo
- `_detect_field_type(elem_str)`: detecta o tipo semântico do campo a partir do resource-id/content-desc
- 5 novos action subtypes em `Action._execute_type()`: `smart_empty`, `smart_space`, `smart_large`, `smart_special`, `smart_boundary`
- `smart_boundary`: seleciona valor de fronteira baseado no tipo detectado do campo (email, password, etc.)

### Changed
- `_add_default_text_actions()`: inclui os 5 novos smart subtypes (~40% dos inputs agora são inteligentes, 60% aleatórios). Sem remoção dos subtypes existentes

---

## [0.1.12] - 2026-03-22

### Added
- `_fuzzy_match_id()` em `rlmobtest/training/report.py`: compara IDs de recursos normalizando o prefixo de package e usando `SequenceMatcher` com threshold 0.8
- Fuzzy matching integrado ao cálculo de cobertura de requisitos: requisitos com IDs que diferem apenas por variações de prefixo/package agora são reconhecidos como cobertos

### Changed
- `_compute_requirements_coverage()`: match exato continua sendo tentado primeiro; fuzzy matching é usado como fallback para recuperar requisitos "quase cobertos"

---

## [0.1.11] - 2026-03-22

### Added
- `coverage_reward()` em `rlmobtest/training/reward.py`: bônus incremental por novas linhas (+5/%) e branches (+10/%) cobertas
- `_get_step_coverage()` em `rlmobtest/training/loop.py`: obtém métricas JaCoCo sem lançar exceção
- Constante `COVERAGE_CHECK_INTERVAL = 5` (verificação de cobertura a cada 5 steps)
- JaCoCo integrado ao loop de treinamento: quando `is_coverage=true`, o agente recebe bônus de recompensa proporcional ao aumento de cobertura de linhas e branches a cada 5 steps

### Changed
- Loop de treinamento (`loop.py`) agora inicializa `prev_coverage` antes dos episódios e calcula `coverage_reward` a cada `COVERAGE_CHECK_INTERVAL` steps

---

## [0.1.10] - 2026-03-16

### Added
- Tutorial DQN em linguagem acessível (`docs/dqn_tutorial.md`)
- `docs/coverage_improvement_suggestions.md`: diagnóstico e sugestões concretas de melhoria de cobertura (requisitos e JaCoCo)
- Diagramas de fluxo de transcrição (`docs/drawio/transcription_flow.drawio`, `transcription_flow_model2.drawio`)
- Constantes `ACTION_TYPE_ALIASES` e `INVALID_ID_RE` em `rlmobtest/constants/actions.py` para normalização de IDs de requisitos

### Changed
- `report.py`: matching de requisitos agora normaliza `action_type` via `ACTION_TYPE_ALIASES` e ignora IDs inválidos via `INVALID_ID_RE`
- `generate_requirements.py`: melhorias no parsing e extração de requisitos via Ollama
- `config_reader.py`: campo `source_code` adicionado ao `AppConfig`
- `cli/pipeline.py` e `cli/train.py`: ajustes de argumentos e exibição
- `docs/architecture.drawio` movido para `docs/drawio/architecture.drawio`
- README atualizado com tutorial e referências ao novo doc de cobertura

---

## [0.1.9] - 2026-03-10

### Added
- Agente de build autônomo (`rlmobtest/utils/build_agent.py`): rule-based fallback para construção de APKs com JaCoCo em projetos AGP 1.x–8.x
- Slash command `/setup-build` (`/.claude/commands/setup-build.md`) para acionar o agente via Claude Code
- Comando `rlmobtest check`: valida pré-requisitos de Java, Gradle e Android SDK antes do setup
- Suporte a JaCoCo legado 0.7.4 (`jacoco.py`): fallback automático para `IncompatibleExecDataVersionException` (exec data 0x1006)
- Tabela de compatibilidade AGP × Gradle × Java em `build_agent.py`
- `CLAUDE.md`: instruções do projeto para o agente Claude Code
- `docs/coverage_metrics.md`: documentação de métricas de cobertura JaCoCo
- Diagrama de arquitetura (`docs/architecture.drawio`) e fluxo de transcrição (`docs/transcription_flow.drawio`)
- Constantes de `ACTION_TYPE_ALIASES` em `rlmobtest/constants/actions.py`

### Changed
- `jacoco_setup.py`: suporte a classfiles de AGP legado (`intermediates/classes/debug/`) além do caminho moderno (`intermediates/javac/debug/classes/`)
- `jacoco_setup.py`: correção de `google()` shorthand para Gradle < 4.0 (usa `maven { url 'https://maven.google.com' }`)
- `generate_requirements.py`: refatoração do parsing de requisitos e extração de XML
- `settings.json`: correção de typo no package name (`org.secusco` → `org.secuso`)
- `cli/pipeline.py` e `cli/setup.py`: integração do agente de build e do comando check

### Removed
- Scripts legados `script_iartes*.py` (substituídos pelo CLI Typer)
- `inputs/tools/.gitignore`: `jacococli.jar` removido da lista de ignorados (baixado automaticamente pelo setup)

---

## [0.1.8] - 2026-03-03

### Added
- Comando `rlmobtest setup` (`rlmobtest/cli/setup.py`): automatiza build do APK, cópia de classfiles e download do `jacococli.jar`
- `rlmobtest/utils/jacoco.py`: biblioteca para merge de `.ec`, geração de CSV/HTML e parsing de cobertura
- `rlmobtest/utils/jacoco_setup.py`: instrumentação do APK com JaCoCo e configuração do `CoverageReceiver`
- `rlmobtest/android/android_env.py`: broadcast `DUMP_COVERAGE` via `adb` a cada step quando `is_coverage=true`
- Geração de relatório HTML JaCoCo com link no `report.html` (coluna JaCoCo)
- `docs/jacoco_setup.md`: guia completo de setup e integração JaCoCo
- Constantes de paths `TOOLS_DIR`, `CLASSFILES_DIR`, `SOURCE_CODES_DIR`, `APKS_DIR` em `constants/paths.py`

### Changed
- `pipeline.py`: Step 0 executa `jacoco_setup` automaticamente quando `is_coverage=true` e `source_code` está configurado
- `report.py`: inclui métricas JaCoCo (line_pct, branch_pct, method_pct) e link para relatório HTML
- Backend matplotlib alterado para `Agg` em `android_env.py` para evitar crash de threading com Tkinter
- `constants/llm.py`: ajustes menores nas constantes de LLM

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

[Unreleased]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.15...HEAD
[0.1.15]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.14...v0.1.15
[0.1.14]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.3...v0.1.6
[0.1.3]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/seu-usuario/rlmobtest-icomp/releases/tag/v0.0.1
