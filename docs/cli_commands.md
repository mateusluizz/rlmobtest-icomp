# Referencia de Comandos CLI — RLMobTest

## Visao Geral

O RLMobTest oferece dois tipos de interface de linha de comando:

1. **Comandos Typer** (`rlmobtest <comando>`) — interface principal instalada via `pip install -e .`
2. **Scripts standalone** (`python <script>`) — scripts avulsos com argparse

---

## Comandos Typer

### `rlmobtest check` — Pre-validacao do ambiente

Verifica se os prerequisitos (Java, Gradle, Android SDK, asdf) estao corretamente configurados.

```bash
rlmobtest check
```

Sem opcoes. Verifica:
- Java instalada e versao
- Gradle instalado e versao
- Android SDK (`$ANDROID_HOME`) e componentes
- asdf (para gerenciamento de versoes Java/Gradle)
- sdkmanager (requer Java 17+)
- Licencas do SDK aceitas

---

### `rlmobtest setup` — Build e setup do JaCoCo

Compila APKs instrumentados com JaCoCo, copia classfiles e baixa jacococli.jar.

```bash
rlmobtest setup [OPCOES]
```

| Opcao | Curto | Tipo | Padrao | Descricao |
|-------|-------|------|--------|-----------|
| `--app` | `-a` | str (multiplo) | todos | Package name(s) do(s) app(s) |
| `--force` | `-f` | flag | `False` | Forcar rebuild mesmo se APK ja existe |
| `--agent` | — | flag | `True` | Usar build agent autonomo |
| `--no-agent` | — | flag | — | Desativar build agent (Gradle direto) |

O setup executa:
1. Resolve o source code (extrai ZIP/tar.gz se necessario)
2. Injeta JaCoCo (`testCoverageEnabled true`) no build.gradle
3. Adiciona CoverageReceiver ao app
4. Compila via `./gradlew assembleDebug`
5. Copia APK para `inputs/apks/{apk_name}`
6. Copia classfiles para `inputs/classfiles/{package_name}/`
7. Baixa `jacococli.jar` para `inputs/tools/`

Com `--agent` (padrao), o build agent autonomo tenta resolver erros de compilacao automaticamente (repositorios Maven, versoes Java/Gradle, SDK faltante).

**Exemplos:**

```bash
# Setup completo para todos os apps com build agent
rlmobtest setup

# Setup sem build agent
rlmobtest setup --no-agent

# App especifico, forcar rebuild
rlmobtest setup --app com.blogspot.e_kanivets.moneytracker --force
```

---

### `rlmobtest pipeline` — Pipeline completo

Executa o fluxo completo: exploracao → requirements → treino guiado → transcricao.

```bash
rlmobtest pipeline [OPCOES]
```

| Opcao | Curto | Tipo | Padrao | Descricao |
|-------|-------|------|--------|-----------|
| `--mode` | `-m` | `original` \| `improved` | `improved` | Modo do DQN |
| `--max-steps` | `-s` | int | `100` | Maximo de passos por episodio |
| `--app` | `-a` | str (multiplo) | todos | Package name(s) do(s) app(s). Pode repetir |
| `--llm-model` | `-l` | str | `gemma3:12b` | Modelo Ollama para requirements e transcricao |
| `--all-dates` | — | flag | `False` | Processar test_cases de todas as datas |
| `--skip-exploration` | — | flag | `False` | Pular etapa 1 (exploracao) |
| `--skip-requirements` | — | flag | `False` | Pular etapa 2 (requirements) |
| `--skip-guided` | — | flag | `False` | Pular etapa 3 (treino guiado) |
| `--only-transcribe` | — | flag | `False` | Executar somente etapa 4 (transcricao) |

**Etapas do pipeline:**
0. **Setup** — Build APK + JaCoCo (automatico se `is_coverage` e `source_code`)
1. **Exploracao** (`is_req=false`) — DQN aprende via heuristicas
2. **Requirements** — Extrai requisitos dos test_cases + source code via Ollama
3. **Treino guiado** (`is_req=true`) — DQN usa happy path dos requirements
4. **Transcricao** — CrewAI gera casos de teste no formato ISO 29119-3

**Exemplos:**

```bash
# Pipeline completo para todos os apps
rlmobtest pipeline

# Somente transcricao, todas as datas, modo original
rlmobtest pipeline --only-transcribe --all-dates -m original

# App especifico, pular exploracao
rlmobtest pipeline --app com.blogspot.e_kanivets.moneytracker --skip-exploration

# Modelo diferente, mais passos por episodio
rlmobtest pipeline -l mistral -s 150
```

---

### `rlmobtest train` — Treinar o agente RL

Treina o agente DQN em aplicacao(oes) Android configuradas em `settings.json`.

```bash
rlmobtest train [OPCOES]
```

| Opcao | Curto | Tipo | Padrao | Descricao |
|-------|-------|------|--------|-----------|
| `--mode` | `-m` | `original` \| `improved` | `improved` | Modo do DQN |
| `--app` | `-a` | str (multiplo) | todos | Package name(s) do(s) app(s) |
| `--time` | `-t` | int | config | Limite de tempo em segundos (sobrescreve config) |
| `--episodes` | `-e` | int | config | Numero de episodios (sobrescreve config) |
| `--checkpoint` | `-c` | Path | `None` | Caminho para checkpoint (retomar treino) |
| `--max-steps` | `-s` | int | `100` | Maximo de passos por episodio |

**Restricoes:**
- `--time` e `--episodes` sao mutuamente exclusivos
- `--checkpoint` so pode ser usado com um unico app (via `--app`)

**Exemplos:**

```bash
# Treinar todos os apps do config
rlmobtest train

# Treinar app especifico por 10 minutos
rlmobtest train --app com.example.app --time 600

# Retomar de checkpoint
rlmobtest train --app com.example.app -c output/.../checkpoints/model.pt

# Modo original, 50 episodios
rlmobtest train -m original --episodes 50
```

---

### `rlmobtest report` — Gerar relatorio HTML

Gera relatorio HTML a partir dos dados de output ja existentes.

```bash
rlmobtest report [OPCOES]
```

| Opcao | Curto | Tipo | Padrao | Descricao |
|-------|-------|------|--------|-----------|
| `--app` | `-a` | str (multiplo) | todos | Package name(s) do(s) app(s) |
| `--mode` | `-m` | `original` \| `improved` | `improved` | Tipo de agente |
| `--all-dates` | — | flag | `False` | Incluir todas as datas |

O relatorio e salvo na pasta do dia: `output/{pkg}/{mode}/{Y}/{M}/{D}/report.html`

**Exemplos:**

```bash
# Relatorio de hoje para todos os apps
rlmobtest report

# Relatorio de todas as datas, modo original
rlmobtest report --all-dates -m original

# Relatorio de app especifico
rlmobtest report --app com.blogspot.e_kanivets.moneytracker --all-dates
```

---

### `rlmobtest clean` — Limpar pastas de output

Remove arquivos de output com filtros por app, agente e subpasta.

```bash
rlmobtest clean [SUBFOLDER] [OPCOES]
```

| Argumento | Tipo | Descricao |
|-----------|------|-----------|
| `SUBFOLDER` | str (opcional) | Subpasta para limpar. Se omitido, limpa todas |

**Subpastas validas:**
`checkpoints`, `crashes`, `errors`, `metrics`, `old_transcriptions`,
`screenshots`, `test_cases`, `transcriptions`

| Opcao | Curto | Tipo | Padrao | Descricao |
|-------|-------|------|--------|-----------|
| `--app` | `-a` | str | `None` | Limpar somente app especifico |
| `--agent` | — | str | `None` | Limpar somente agente especifico |
| `--dry-run` | `-n` | flag | `False` | Mostrar o que seria deletado sem deletar |
| `--force` | `-f` | flag | `False` | Pular confirmacao |

**Exemplos:**

```bash
# Ver o que seria deletado (dry run)
rlmobtest clean --dry-run

# Limpar screenshots de app especifico
rlmobtest clean screenshots --app protect.budgetwatch

# Limpar tudo do agente original sem confirmacao
rlmobtest clean --agent original -f

# Limpar transcricoes
rlmobtest clean transcriptions -f
```

---

### `rlmobtest info` — Informacoes do ambiente

Exibe informacoes de configuracao e ambiente.

```bash
rlmobtest info
```

Sem opcoes. Exibe:
- Dispositivo (GPU/CPU)
- Versao CUDA
- Caminho do config e configuracoes
- Status do servidor Ollama

---

## Scripts Standalone

### `python -m rlmobtest.transcription.crew_transcriber` — Transcricao avulsa

Executa a transcricao CrewAI de forma independente do pipeline.

```bash
python -m rlmobtest.transcription.crew_transcriber [OPCOES]
```

| Opcao | Obrigatorio | Tipo | Padrao | Descricao |
|-------|-------------|------|--------|-----------|
| `--app` | Sim | str | — | Package name do app |
| `--agent` | Nao | str | `improved` | Tipo de agente: `original` ou `improved` |
| `--date` | Nao | str | todos | Data especifica (formato `YYYY-MM-DD`) |
| `--model` | Nao | str | `ollama/gemma3:12b` | Modelo LLM |
| `--base-url` | Nao | str | `http://localhost:11434` | URL do servidor Ollama |
| `--source-code` | Nao | str | `None` | Arquivo do source code em `inputs/source_codes/` |
| `--package` | Nao | str | `None` | Package name (obrigatorio com `--source-code`) |

**Exemplos:**

```bash
# Transcrever todos os dias de um app
python -m rlmobtest.transcription.crew_transcriber \
  --app protect.budgetwatch --agent original

# Transcrever data especifica
python -m rlmobtest.transcription.crew_transcriber \
  --app protect.budgetwatch --date 2026-03-01

# Com contexto do source code
python -m rlmobtest.transcription.crew_transcriber \
  --app com.blogspot.e_kanivets.moneytracker \
  --source-code open_money_tracker-dev.zip \
  --package com.blogspot.e_kanivets.moneytracker

# Modelo diferente
python -m rlmobtest.transcription.crew_transcriber \
  --app protect.budgetwatch --model ollama/mistral
```

---

### `python -m rlmobtest.training.generate_requirements` — Gerar requirements

Gera `requirements.csv` a partir dos test_cases e source code via Ollama.

```bash
python -m rlmobtest.training.generate_requirements [OPCOES]
```

| Opcao | Tipo | Padrao | Descricao |
|-------|------|--------|-----------|
| `--all-dates` | flag | `False` | Processar test_cases de todas as datas |
| `--llm-model` | str | `gemma3:12b` | Modelo Ollama |

**Requisitos:**
- Apps devem ter `source_code` configurado em `settings.json`
- Servidor Ollama rodando em `localhost:11434`
- Test_cases ja gerados pela exploracao

**Exemplos:**

```bash
# Gerar para hoje
python -m rlmobtest.training.generate_requirements

# Gerar para todas as datas
python -m rlmobtest.training.generate_requirements --all-dates

# Modelo diferente
python -m rlmobtest.training.generate_requirements --llm-model neural-chat
```

---

## Tabela Resumo

| Comando | Funcao |
|---------|--------|
| `rlmobtest check` | Pre-validacao do ambiente |
| `rlmobtest setup` | Build APK + JaCoCo setup |
| `rlmobtest pipeline` | Pipeline completo (5 etapas) |
| `rlmobtest train` | Treinar agente DQN |
| `rlmobtest report` | Gerar relatorio HTML |
| `rlmobtest clean` | Limpar pastas de output |
| `rlmobtest info` | Info do ambiente |
| `python run_pipeline.py` | Pipeline (script avulso) |
| `python -m rlmobtest.transcription.crew_transcriber` | Transcricao CrewAI avulsa |
| `python -m rlmobtest.training.generate_requirements` | Gerar requirements.csv |

---

## Configuracao

### `rlmobtest/config/settings.json`

Arquivo JSON com array de objetos, cada um representando um app:

```json
[
  {
    "apk_name": "moneytracker.apk",
    "package_name": "com.blogspot.e_kanivets.moneytracker",
    "source_code": "open_money_tracker-dev.zip",
    "is_coverage": true,
    "is_req": false,
    "time": 3600,
    "time_exploration": 3600,
    "time_guided": 3600,
    "episodes": 20
  }
]
```

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `apk_name` | str | Nome do arquivo APK em `inputs/apks/` |
| `package_name` | str | Package name do Android |
| `source_code` | str | Arquivo do source code em `inputs/source_codes/` (vazio se nao disponivel) |
| `is_coverage` | bool | Ativar analise de cobertura JaCoCo |
| `is_req` | bool | Ativar treino guiado por requirements |
| `time` | int | Tempo limite de treinamento em segundos (padrao para ambas as fases) |
| `time_exploration` | int | Tempo da fase de exploracao (sobrescreve `time`) |
| `time_guided` | int | Tempo da fase guiada (sobrescreve `time`) |
| `episodes` | int | Numero maximo de episodios |

### Estrutura de Diretorios

```
rlmobtest-icomp/
├── inputs/
│   ├── apks/                          # APKs instrumentados
│   ├── classfiles/                    # Classes compiladas por package
│   │   └── {package_name}/            # .class files para JaCoCo
│   ├── source_codes/                  # Arquivos zip/tar.gz do source code
│   └── tools/                         # Ferramentas externas
│       ├── jacococli.jar              # JaCoCo CLI (0.8.12)
│       ├── jacoco-legacy-0.7.4.jar    # JaCoCo legacy (formato 0x1006)
│       └── JacocoLegacyReport.class   # Report tool para projetos antigos
├── output/
│   └── {package_name}/
│       └── {original|improved}/
│           └── {YYYY}/{MM}/{DD}/
│               ├── test_cases/        # Logs brutos de interacao
│               ├── transcriptions/    # Casos de teste ISO 29119-3
│               ├── old_transcriptions/# Transcricoes anteriores
│               ├── screenshots/       # Screenshots PNG
│               ├── errors/            # Logs de erro
│               ├── crashes/           # Logs de crash
│               ├── coverage/          # Dados JaCoCo (.ec + HTML)
│               ├── metrics/           # Metricas JSON do treinamento
│               ├── checkpoints/       # Checkpoints do modelo DQN
│               ├── requirements.csv   # Requisitos extraidos
│               └── report.html        # Relatorio HTML consolidado
└── rlmobtest/
    └── config/
        └── settings.json              # Configuracao dos apps
```
