# Contexto Passado a LLM na Transcricao com CrewAI

## Visao Geral

A transcricao com CrewAI usa um agente LLM (por padrao `gemma3:8b` via Ollama) para
transformar logs brutos de interacao Android em casos de teste legiveis no formato
ISO/IEC/IEEE 29119-3. Este documento detalha **todos os dados** que a LLM recebe
como contexto durante esse processo.

---

## Arquitetura do Contexto

O contexto e montado em duas camadas: o **Agent** (quem e a LLM e como deve agir)
e a **Task** (o que ela deve fazer com a entrada especifica).

```
┌─────────────────────────────────────────────────────────┐
│                      AGENT (CrewAI)                     │
│                                                         │
│  role:      "Mobile Test Case Specialist"               │
│  goal:      Transformar logs em test cases limpos       │
│  backstory: SYSTEM_PROMPT (regras + formato ISO 29119)  │
│  context:   Few-shot examples + App Context             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                      TASK (CrewAI)                       │
│                                                         │
│  description: Log bruto + App Context + instrucoes      │
│  expected_output: Formato ISO 29119-3 esperado          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 1. SYSTEM_PROMPT (backstory do agente)

**Arquivo:** `rlmobtest/transcription/prompts.py`

O prompt de sistema define a persona e as regras que a LLM deve seguir.
Ele e compartilhado tanto pelo transcriber CrewAI quanto pelo LangChain.

### Conteudo

```
You are a Senior QA Engineer specialized in mobile application testing.
Your task is to transform raw interaction logs into clean, human-readable test cases
following the ISO/IEC/IEEE 29119-3 Test Case Specification format.

RULES:
1. LANGUAGE: Write everything in English.
2. NO TECHNICAL IDS: Never include Android resource IDs, widget class names, or bounds.
3. NO ERROR FILE REFERENCES: Do not reference "errors.txt", "crash.txt", etc.
4. NO SCREENSHOT PATHS: Do not include "states/state_*.png" paths.
5. REAL ACTIONS: Describe what a real user would do.
6. EXPECTED RESULTS: Each test step MUST include an expected result.
7. FORMAT: Use the ISO/IEC/IEEE 29119-3 structure.
```

Alem das regras, inclui o template do formato de saida esperado com todos os campos:
Test Case ID, Title, Description, Priority, Preconditions, Test Steps (tabela), Postconditions.

### Papel no Contexto

Este prompt define o **comportamento base** da LLM. Sem ele, a LLM poderia
copiar IDs tecnicos do log bruto diretamente para o caso de teste.

---

## 2. Few-Shot Examples (context do agente)

**Diretorio:** `rlmobtest/data/few_shot_examples/`

A LLM recebe um par **entrada/saida** que serve como exemplo concreto de
como transformar um log bruto em um caso de teste limpo.

### Estrutura dos Arquivos

```
few_shot_examples/
├── scripts/
│   └── TC_.ImportExportActivity_20210401-002546.txt    ← Entrada (log bruto)
└── transcriptions/
    └── CleanTC_.ImportExportActivity_20210401-002546.txt  ← Saida esperada
```

### Exemplo de Entrada (log bruto)

```
Test Case protect.budgetwatch/.ImportExportActivity

scroll down android.widget.ScrollView  bounds:[0,153][720,1381]
clicked  android.widget.Spinner  bounds:[182,465][692,507]
clicked  android.widget.CheckedTextView  bounds:[217,549][601,633]
clicked  android.widget.Button  bounds:[28,667][692,751]
Got Error, see errors.txt line 5
clicked  android.widget.ImageButton Mes passado bounds:[87,1255][171,1299]
```

### Exemplo de Saida (caso de teste limpo)

```
Test Case ID: TC_001
Test Case Title: Import/Export Activity - File Format Selection and Date Navigation
Description: Verify the import and export functionality including file format
selection, date navigation, and data review.
Priority: Medium
Preconditions:
- Budget Watch application is installed and launched.
- The Import/Export screen is open.
Test Steps:
| Step | Action                                    | Test Data | Expected Result                          |
|------|-------------------------------------------|-----------|------------------------------------------|
| 1    | Scroll down to reveal additional options   | N/A       | Additional import/export options visible  |
| 2    | Tap the file format dropdown               | N/A       | List of available formats displayed       |
| 3    | Select a file format from the dropdown     | N/A       | Selected format is highlighted            |
...
Postconditions:
- The application is on the Home screen in a stable state.
```

### Papel no Contexto

O few-shot example ensina a LLM **pelo exemplo**. Ela aprende o mapeamento entre
o formato de entrada (widgets, bounds, erros) e o formato de saida (acoes em
linguagem natural, resultados esperados, tabela ISO 29119-3).

---

## 3. App Context (contexto da aplicacao)

**Arquivo:** `rlmobtest/utils/app_context.py`

**Novo na versao atual.** O app context e extraido automaticamente do codigo-fonte
da aplicacao Android (arquivo zip ou tar.gz em `inputs/source_codes/`).

### Fontes de Dados

O contexto e construido a partir de tres arquivos XML encontrados no source code:

| Arquivo | O que contem | Para que serve |
|---------|-------------|----------------|
| `AndroidManifest.xml` | Declaracoes de Activities com labels | Mapear nomes tecnicos para nomes legiveis |
| `res/values/strings.xml` | Constantes de texto do app | Resolver referencias `@string/` |
| `res/layout/activity_*.xml` | Componentes de UI com IDs, hints e textos | Descrever os elementos de cada tela |

### Exemplo de Contexto Gerado

Para o app Money Tracker (`open_money_tracker-dev.zip`):

```
## App Context: com.blogspot.e_kanivets.moneytracker

### Screens (Activities)
- .activity.account.AccountsActivity = "Accounts"
- .activity.record.MainActivity = "Money Tracker"
- .activity.ReportActivity = "Report"
- .activity.SettingsActivity = "Settings"
- .activity.external.ImportExportActivity = "Import/Export"

### Screen Components
**Accounts** (activity_accounts.xml):
  - Toolbar id="toolbar"
  - ListView id="listView"
  - Button id="btn_add_account" | text="Add account"
  - AppCompatSpinner id="spinner"

**Add Record** (activity_add_record.xml):
  - EditText id="etPrice" | hint="Price"
  - EditText id="etTitle" | hint="Title"
  - AutoCompleteTextView id="etCategory" | hint="Category"
  - AppCompatSpinner id="spinnerAccount"

**Main** (activity_main.xml):
  - Button id="btnAddIncome" | text="Add income"
  - Button id="btnAddExpense" | text="Add expense"
  - RecyclerView id="recyclerView"
```

### Papel no Contexto

Sem o app context, a LLM ve o log:
```
Clicked android.widget.Spinner com.blogspot:id/spinnerCurrency bounds:[841,405][1175,475]
```
E precisa **adivinhar** o que e `spinnerCurrency`. Pode gerar:
> "Tap the dropdown" (generico)

Com o app context, ela sabe que `spinnerCurrency` esta na tela "Report" e e um
`AppCompatSpinner`. Pode gerar:
> "Tap the currency selector on the Report screen" (preciso)

### Onde e Injetado

O app context aparece em **dois lugares** do CrewAI:

1. **Agent context** — junto com os few-shot examples, com a instrucao:
   > "Use the following information to write more descriptive, user-friendly test steps.
   > Replace technical IDs with the human-readable labels shown below."

2. **Task description** — apos o log bruto, com o cabecalho:
   > "Application Context (use for reference only, do not copy verbatim)"

---

## 4. Log Bruto de Interacao (entrada da task)

**Diretorio:** `output/{package}/{agent}/{Y}/{M}/{D}/test_cases/`

O log bruto e o arquivo `.txt` gerado durante o treinamento DQN. Cada arquivo
representa uma sessao de exploracao em uma Activity especifica.

### Exemplo Real

```
Test Casecom.blogspot.e_kanivets.moneytracker/.activity.account.AccountsActivity

Clicked android.widget.Spinner com.blogspot.e_kanivets.moneytracker:id/spinnerCurrency
  bounds:[841,405][1175,475]
  Screen: .../screenshots/state_20260301-160353.png

Clicked android.widget.TextView android:id/text1  AWG
  bounds:[841,1215][1040,1350]

Go to next activity: com.blogspot.e_kanivets.moneytracker/.activity.record.MainActivity
```

### Informacoes Presentes no Log

| Dado | Exemplo | Uso pela LLM |
|------|---------|-------------|
| Activity | `.activity.account.AccountsActivity` | Identificar a tela |
| Tipo de widget | `android.widget.Spinner` | Descrever o tipo de elemento |
| Resource ID | `com.blogspot:id/spinnerCurrency` | Identificar qual elemento |
| Texto do elemento | `AWG` | Dados de teste (Test Data) |
| Coordenadas | `bounds:[841,405][1175,475]` | Ignorado (regra 2) |
| Path de screenshot | `Screen: .../state_20260301.png` | Ignorado (regra 4) |
| Erros | `Got Error, see errors/error_...txt` | Descrito como comportamento |
| Transicao | `Go to next activity: ...` | Descrever navegacao |

---

## 5. Instrucoes da Task

Junto com o log bruto, a task inclui instrucoes explicitas:

```
Your task:
1. Identify the sequence of user actions from the raw log
2. Describe each action in plain language (e.g., "Tap the Save button")
3. Do NOT include Android resource IDs, widget class names, coordinate bounds,
   screenshot paths, or references to errors.txt / crash.txt
4. If an error occurred, describe it as an expected application behavior
5. Maintain the logical flow of the test scenario
6. Use the exact ISO/IEC/IEEE 29119-3 format shown in the examples
```

---

## 6. Expected Output

A task tambem define o formato esperado da saida:

```
A test case following ISO/IEC/IEEE 29119-3 format with these sections:
Test Case ID, Test Case Title, Description, Priority, Preconditions,
Test Steps (as a table with Step/Action/Test Data/Expected Result columns),
and Postconditions.
The output must NOT contain resource IDs, widget types, screenshot paths,
or error file references.
```

---

## Resumo: Fluxo Completo de Dados

```
inputs/source_codes/app.zip ──► app_context.py ──► App Context (str)
                                                        │
                                                        ▼
prompts.py ──► SYSTEM_PROMPT ──────────────────► Agent.backstory
                                                        │
few_shot_examples/ ──► load_few_shot_examples() ──►     │
                                                        ▼
                                                  Agent.context
                                                  (few-shot + app context)
                                                        │
output/.../test_cases/TC_*.txt ──► read_text_file() ──► │
                                                        ▼
                                                  Task.description
                                                  (log bruto + app context + instrucoes)
                                                        │
                                                        ▼
                                                  CrewAI.kickoff()
                                                        │
                                                        ▼
                                        output/.../transcriptions/TC_*.txt
                                        (caso de teste ISO 29119-3)
```

---

## O Que NAO e Passado (e por que)

| Dado | Por que nao e passado |
|------|-----------------------|
| **Screenshots (imagens)** | Parametro existe mas nao e injetado no prompt. Adiciona custo significativo de tokens e nem todos os modelos locais suportam multimodal. Preparado para uso futuro. |
| **Arquivos de erro** (`errors/*.txt`) | Contem logcat tecnico do Android. O log bruto ja menciona que houve erro; a LLM deve descreve-lo como comportamento esperado. |
| **Arquivos de crash** (`crashes/*.txt`) | Mesmo motivo dos erros. |
| **Metricas de treinamento** (`metrics/*.json`) | Dados de performance do DQN, irrelevantes para a geracao de casos de teste. |
| **requirements.csv** | Gerado para o report, nao para a transcricao. |
| **Layouts de menu/drawable** | Filtrados no `app_context.py` — apenas `activity_*` e `dialog_*` sao incluidos para manter o contexto compacto. |

---

## Tamanho Estimado do Contexto

Para o app Money Tracker com `gemma3:4b` (contexto de 8K tokens):

| Componente | Estimativa |
|------------|-----------|
| SYSTEM_PROMPT | ~550 tokens |
| Few-shot example (1 par) | ~1000 tokens |
| App Context | ~1500 tokens |
| Log bruto (1 test case) | ~200-500 tokens |
| Instrucoes da task | ~200 tokens |
| **Total** | **~3500-3750 tokens** |

O total fica bem abaixo do limite de 8K, deixando espaco suficiente para a
geracao da resposta.
