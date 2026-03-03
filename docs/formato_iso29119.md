# Formato de Casos de Teste — ISO/IEC/IEEE 29119-3

## O Que e a ISO/IEC/IEEE 29119-3?

A ISO/IEC/IEEE 29119-3 e a parte 3 do padrao internacional de teste de software,
focada em **documentacao de teste**. Ela define templates padronizados para todos os
documentos produzidos durante o processo de teste, incluindo a especificacao de casos
de teste (Test Case Specification).

O padrao foi publicado originalmente em 2013 e revisado em 2021. Ele substitui o
antigo IEEE 829 (documentacao de teste) e pode ser adotado em qualquer metodologia
de desenvolvimento: tradicional (cascata, iterativo), agil ou DevOps.

---

## Por Que Adotamos Este Formato?

O formato anterior dos casos de teste gerados pelo RLMobTest tinha problemas:

| Problema | Exemplo no formato antigo |
|----------|--------------------------|
| IDs tecnicos do Android | `protect.budgetwatch:id/dateRangeSelectButton` |
| Nomes de widgets | `android.widget.Spinner`, `android.widget.Button` |
| Coordenadas de tela | `bounds:[182,465][692,507]` |
| Referencias a arquivos de erro | `Got Error, see errors.txt line 5` |
| Caminhos de screenshots | `states/state_20210413-104757.png` |
| Secoes em portugues | `Resultado obtido:` |
| Descricoes genericas | `Perform exploratory actions` |
| Sem resultados esperados | Passos sem `Expected Result` |

O formato ISO/IEC/IEEE 29119-3 resolve todos esses problemas com uma estrutura
padronizada e reconhecida internacionalmente.

---

## Estrutura do Novo Formato

Cada caso de teste gerado segue esta estrutura:

### Campos Obrigatorios

| Campo | Descricao |
|-------|-----------|
| **Test Case ID** | Identificador unico (ex: `TC_001`) |
| **Test Case Title** | Nome descritivo curto do cenario de teste |
| **Description** | Resumo de 1-2 frases do objetivo do teste |
| **Priority** | Prioridade: `High`, `Medium` ou `Low` |
| **Preconditions** | Condicoes que devem ser verdadeiras antes da execucao |
| **Test Steps** | Tabela com as colunas: Step, Action, Test Data, Expected Result |
| **Postconditions** | Estado esperado do sistema apos o teste |

### Tabela de Test Steps

Os passos de teste usam uma tabela com 4 colunas:

| Coluna | Descricao |
|--------|-----------|
| **Step** | Numero sequencial do passo |
| **Action** | Descricao da acao do usuario em linguagem natural |
| **Test Data** | Dados de entrada necessarios, ou `N/A` se nenhum |
| **Expected Result** | O que deve acontecer apos a acao |

---

## Exemplo Completo

### Entrada (log bruto de interacao)

```
Test Case protect.budgetwatch/.ImportExportActivity

scroll down android.widget.ScrollView  bounds:[0,153][720,1381]

clicked  android.widget.Spinner  bounds:[182,465][692,507]

clicked  android.widget.CheckedTextView  bounds:[217,549][601,633]

clicked  android.widget.Button  bounds:[28,667][692,751]

clicked  android.widget.Button  bounds:[67,786][179,860]

Got Error, see errors.txt line 5

clicked  android.widget.Button  bounds:[28,569][325,653]

clicked  android.widget.ImageButton Mes passado bounds:[87,1255][171,1299]
```

### Saida (caso de teste no formato ISO 29119-3)

```
Test Case ID: TC_001
Test Case Title: Import/Export Activity - File Format Selection and Date Navigation
Description: Verify the import and export functionality in the Budget Watch
application, including file format selection, date navigation, and data review.
Priority: Medium
Preconditions:
- Budget Watch application is installed and launched.
- The Import/Export screen is open.
Test Steps:
| Step | Action                                          | Test Data | Expected Result                                    |
|------|-------------------------------------------------|-----------|----------------------------------------------------|
| 1    | Scroll down to reveal additional options        | N/A       | Additional import/export options become visible     |
| 2    | Tap the file format dropdown                    | N/A       | A list of available file formats is displayed       |
| 3    | Select a file format from the dropdown list     | N/A       | The selected format is highlighted                  |
| 4    | Tap the action button below the format selector | N/A       | The application begins processing                   |
| 5    | Tap the confirmation button                     | N/A       | An error occurs; the app handles it gracefully      |
| 6    | Tap the main action button                      | N/A       | The application returns to a stable state           |
| 7    | Tap the "Previous Month" navigation button      | N/A       | The calendar view shifts to the previous month      |
Postconditions:
- The application is on the Home screen in a stable state.
- No data has been lost during the import/export operations.
```

---

## Comparacao: Formato Antigo vs Novo

### Formato Antigo

```
Test Case protect.budgetwatch/.ImportExportActivity

Description: Perform exploratory actions on the ImportExportActivity screen.

Preconditions:
1- Have Budget Watch installed.
2- Being on the ImportExportActivity screen.

Test Steps:
1- Scrolled down on the ScrollView.
2- Clicked on a Spinner.
3- Clicked on a CheckedTextView item.
6- Got an error (see errors.txt line 5).
8- Clicked on an ImageButton with the text "Mes passado".

Resultado obtido:
State 1: states/state_20210413-104757.png
State 2: states/state_20210413-104813.png
```

### Formato Novo (ISO 29119-3)

```
Test Case ID: TC_001
Test Case Title: Import/Export Activity - File Format Selection
Description: Verify the import and export functionality including
file format selection and date navigation.
Priority: Medium
Preconditions:
- Budget Watch application is installed and launched.
- The Import/Export screen is open.
Test Steps:
| Step | Action                          | Test Data | Expected Result                               |
|------|---------------------------------|-----------|-----------------------------------------------|
| 1    | Scroll down on the screen       | N/A       | Additional options become visible              |
| 2    | Tap the file format dropdown    | N/A       | A list of available formats is displayed       |
| 3    | Select a format from the list   | N/A       | The selected format is highlighted             |
| 6    | Tap the confirmation button     | N/A       | Error occurs; app handles it gracefully        |
| 8    | Tap "Previous Month" button     | N/A       | Calendar shifts to the previous month          |
Postconditions:
- The application is in a stable state.
```

### Diferencas Principais

| Aspecto | Antigo | Novo (ISO 29119-3) |
|---------|--------|---------------------|
| Identificador | Nome da Activity | `Test Case ID: TC_XXX` |
| Titulo | Generico | Descritivo e objetivo |
| Prioridade | Ausente | `High / Medium / Low` |
| Passos | Lista numerada simples | Tabela com 4 colunas |
| Dados de teste | Misturados na acao | Coluna dedicada `Test Data` |
| Resultado esperado | Ausente ou parcial | Obrigatorio em cada passo |
| Pos-condicoes | Ausente | Secao dedicada |
| IDs tecnicos | Presentes | Removidos |
| Screenshots | Lista de caminhos | Removidos |
| Erros | `see errors.txt line N` | Descricao comportamental |
| Idioma | Misto (PT/EN) | Ingles |

---

## Onde o Formato e Aplicado

O formato ISO 29119-3 e usado em **ambos os modulos de transcricao**:

| Modulo | Arquivo | Descricao |
|--------|---------|-----------|
| **LangChain (antigo)** | `rlmobtest/transcription/transcriber.py` | Usa `SYSTEM_PROMPT` + few-shot example |
| **CrewAI (novo)** | `rlmobtest/transcription/crew_transcriber/core.py` | Usa `SYSTEM_PROMPT` como backstory do agente |

Ambos compartilham:
- O mesmo prompt de sistema em `rlmobtest/transcription/prompts.py`
- O mesmo exemplo few-shot em `rlmobtest/data/few_shot_examples/transcriptions/`

---

## Regras de Limpeza

Alem do formato ISO 29119-3, o sistema aplica regras de limpeza para garantir
que os casos de teste sejam legiveis por qualquer pessoa:

1. **Sem IDs tecnicos** — Nenhum `com.example:id/btn_save` ou `android.widget.Spinner`
2. **Sem coordenadas** — Nenhum `bounds:[x,y][x,y]`
3. **Sem referencias a arquivos** — Nenhum `errors.txt`, `crash.txt`, `states/state_*.png`
4. **Acoes reais** — "Tap the Save button" ao inves de "Clicked android.widget.Button"
5. **Tudo em ingles** — Sem secoes mistas PT/EN
6. **Resultado esperado obrigatorio** — Cada passo deve ter um resultado esperado
