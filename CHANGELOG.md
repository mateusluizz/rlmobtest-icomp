# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato e baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Added
- Separação de outputs por tipo de agente (original/improved)
- Documentos de discussão para decisões arquiteturais
- Correção de carregamento de checkpoints para DuelingDQN

### Changed
- Estrutura de output: `{apk}/{agent_type}/{year}/{month}/{day}/`

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

[Unreleased]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seu-usuario/rlmobtest-icomp/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/seu-usuario/rlmobtest-icomp/releases/tag/v0.0.1
