# Como o `report.html` e Gerado

## Visao Geral

O `report.html` e gerado pela funcao `generate_report()` em
`rlmobtest/training/report.py`. Ele agrega dados de multiplas pastas
dentro de um **run_path** e produz um arquivo HTML autocontido.

Um **run_path** e um diretorio de nivel de data, por exemplo:

```
output/<package_name>/<agent_type>/<year>/<month>/<day>/
```

Exemplo real:

```
output/com.blogspot.e_kanivets.moneytracker/original/2026/03/01/
```

O report final e salvo um nivel acima, no nivel do **agent_type**:

```
output/com.blogspot.e_kanivets.moneytracker/original/report.html
```

---

## Estrutura de Diretorios Lida pelo Report

```
output/<package_name>/<agent_type>/<year>/<month>/<day>/
├── metrics/                  # [LIDO] Arquivos JSON de metricas de treino
│   ├── metrics_155548.json
│   └── metrics_165552.json
├── test_cases/               # [LIDO] Logs brutos de interacao (*.txt)
│   ├── TC_.activity.AboutActivity_20260301-213319.txt
│   └── TC_.activity.account.AccountsActivity_20260301-160351.txt
├── transcriptions/           # [CONTADO] Saida da transcricao CrewAI (*.txt)
│   └── TC_.activity.AboutActivity_20260301-213319.txt
├── old_transcriptions/       # [CONTADO] Saida da transcricao LangChain (*.txt)
│   └── TC_.activity.AboutActivity_20260301-213319.txt
├── requirements.csv          # [LIDO] Requisitos gerados a partir do codigo fonte
├── screenshots/              # [NAO LIDO] Screenshots (ignorado pelo report)
├── checkpoints/              # [NAO LIDO] Checkpoints do modelo DQN (ignorado)
├── coverage/                 # [LIDO] Arquivos .ec processados via jacococli.jar
├── crashes/                  # [NAO LIDO] Logs de crash (ignorado)
├── errors/                   # [NAO LIDO] Logs de erro (ignorado)
├── logs/                     # [NAO LIDO] Logs de treino (ignorado)
└── plots/                    # [NAO LIDO] Graficos de treino (ignorado)
```

---

## Passo a Passo: O Que o Report Le

### Passo 1: Coletar Metricas (`metrics/`)

**Arquivos lidos:** `metrics/metrics_*.json`

Cada arquivo JSON contem dados de treino de uma sessao. O report extrai:

| Campo | Caminho no JSON |
|-------|-----------------|
| Total de episodios | `summary.total_episodes` |
| Total de passos | `summary.total_steps` |
| Tempo de treino | `summary.training_time_seconds` |
| Recompensas por episodio | `episode_rewards[]` |
| Contagem de activities | `episode_activity_counts[]` |
| Duracao dos episodios | `episode_durations[]` |

Esses dados sao agregados de todos os run_paths para calcular:
- **Training Overview**: total de episodios, total de passos, tempo de treino, duracao media por episodio
- **Rewards**: recompensa media, maxima e minima

### Passo 2: Carregar Requirements (`requirements.csv`)

**Arquivo lido:** `requirements.csv`

Este CSV nao possui cabecalho. As colunas sao:

```
activity, field, id, action_type, value
```

Exemplo:
```
com.blogspot.e_kanivets.moneytracker.activity.AboutActivity,imagebutton,N/A,click,
```

Usado para calcular:
- **Contagem de requirements** (total de linhas)
- **Activities requeridas** (valores unicos de `activity`)

### Passo 3: Fazer Parse dos Test Cases (`test_cases/`)

**Arquivos lidos:** `test_cases/*.txt` (os **logs brutos de interacao**, NAO as transcricoes)

Para cada arquivo de test case, o report faz duas coisas:

#### 3a. Extrair Nome da Activity do Nome do Arquivo

Padrao do nome: `TC_.<NomeDaActivity>_<timestamp>.txt`

Exemplo: `TC_.activity.account.AccountsActivity_20260301-160351.txt`
extrai `activity.account.AccountsActivity`

Isso constroi o conjunto de **activities descobertas**.

#### 3b. Fazer Parse das Acoes para Cobertura de Requisitos

Cada linha e testada contra esta regex:
```
^(Clicked|Long click|Checked|Scroll \w+|Rotate \w+|Home activity|Go to next activity)
```

Para cada match, extrai:
- **action_type**: mapeado do prefixo da linha (ex: `Clicked` -> `click`, `Scroll` -> `scroll`)
- **resource_id**: extraido pelo padrao `package:id/name` da mesma linha

Esses pares `(action_type, resource_id)` sao comparados com o `requirements.csv`
para calcular a **Cobertura de Requisitos**.

### Passo 4: Contar Transcricoes (`transcriptions/` e `old_transcriptions/`)

**Apenas contagem de arquivos** — o report NAO le o conteudo de nenhuma transcricao.

| Pasta | Label no Report |
|-------|-----------------|
| `transcriptions/` | Transcriptions (CrewAI) |
| `old_transcriptions/` | Transcriptions (LangChain) |

**Cobertura de Transcricao** = `count(transcriptions/) / count(test_cases/) * 100%`

Nota: apenas a pasta `transcriptions/` (CrewAI) e usada no calculo de cobertura.

---

## Secoes do Report e Suas Fontes de Dados

| Secao do Report | Fonte de Dados | O Que Mostra |
|---|---|---|
| **Training Overview** | `metrics/*.json` | Episodios, passos, tempo, duracao media |
| **Rewards** | `metrics/*.json` | Recompensa media/maxima/minima |
| **Activity Coverage** | nomes dos arquivos em `test_cases/` vs activities do `requirements.csv` | % de activities requeridas que foram descobertas |
| **Requirements Coverage** | conteudo de `test_cases/` vs linhas do `requirements.csv` | % de requisitos cobertos pelas acoes dos testes |
| **Transcription Coverage** | contagem de arquivos em `transcriptions/` vs `test_cases/` | % de test cases transcritos (CrewAI) |
| **JaCoCo Coverage** | `coverage/*.ec` + `inputs/tools/jacococli.jar` + `inputs/classfiles/{pkg}/` | Line, Branch e Method coverage (N/A se nao configurado — ver `docs/jacoco_setup.md`) |
| **Tabela de Artefatos** | Todas as pastas acima | Contagens de cada tipo de artefato |

---

## Como Disparar a Geracao do Report

### Via pipeline (metodo atual)

```bash
rlmobtest pipeline -m original --only-transcribe --all-dates --app <package_name>
```

O report e gerado como ultimo passo do pipeline, apos a transcricao.

### Via Python (direto)

```python
from pathlib import Path
from rlmobtest.training.report import generate_report

run_paths = [
    Path("output/com.blogspot.e_kanivets.moneytracker/original/2026/03/01"),
]

generate_report(
    run_paths=run_paths,
    package_name="com.blogspot.e_kanivets.moneytracker",
    agent_type="original",
)
```

### Via CLI standalone (comando dedicado)

```bash
rlmobtest report --all-dates -m original
rlmobtest report --app com.blogspot.e_kanivets.moneytracker --all-dates
```

---

## Conclusao

O report e fundamentalmente baseado nos **test_cases brutos** e nas **metricas**,
nao nas transcricoes. As transcricoes sao apenas contadas (nao lidas) para mostrar
quantos test cases foram transcritos. Se voce quiser que o report reflita a qualidade
ou o conteudo das transcricoes, a logica do report precisaria ser estendida.
