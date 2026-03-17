# Metricas de Cobertura do RLMobTest

Este documento descreve cada metrica de cobertura exibida no relatorio HTML gerado pelo RLMobTest e como cada uma e computada.

---

## 1. Activity Coverage (Cobertura de Atividades)

**O que mede:** A proporcao de Activities Android do app que foram visitadas/exploradas durante os testes.

**Como e computada:**

- **Activities requeridas:** Todas as Activities unicas listadas na coluna `activity` do arquivo `requirements.csv`, que e gerado a partir da analise estatica do APK (via `generate_requirements.py`). Cada nome de Activity e normalizado para usar apenas o nome da classe (ex: `com.example.app.MainActivity` vira `MainActivity`).

- **Activities descobertas:** Todas as Activities unicas extraidas dos nomes dos arquivos de casos de teste gerados durante a exploracao. Os arquivos seguem o padrao `TC_.{caminho.da.Activity}_{timestamp}.txt`, e o nome da classe e extraido do caminho (ex: `TC_.activity.account.AccountsActivity_20260301.txt` → `AccountsActivity`).

- **Formula:**

```
Activity Coverage = (Activities Descobertas / Activities Requeridas) * 100
```

**Exemplo:** `10/12 activities = 83.3%` significa que 10 das 12 Activities do app foram alcancadas pelos testes.

**Arquivo fonte:** `rlmobtest/training/report.py` (funcao `_collect_data`, linhas 225-280)

---

## 2. Requirements Coverage (Cobertura de Requisitos)

**O que mede:** A proporcao de requisitos de interacao (acoes possiveis na interface) que foram efetivamente executados durante os testes.

**O que e um "requisito":** Cada linha do `requirements.csv` representa um requisito unico de interacao, composto por:

| Campo         | Descricao                                          | Exemplo                       |
|---------------|-----------------------------------------------------|-------------------------------|
| `activity`    | Activity Android onde a interacao ocorre             | `AccountsActivity`            |
| `field`       | Tipo de elemento de UI                               | `button`, `edittext`, `imageview` |
| `id`          | Resource ID do elemento                              | `com.example:id/btn_save`     |
| `action_type` | Tipo de acao                                         | `click`, `scroll`, `rotate`   |
| `value`       | Valor opcional (ex: texto a digitar)                 | `"teste123"`                  |

**Como e computada:**

1. Carrega todos os requisitos do `requirements.csv`
2. Para cada caso de teste (arquivos `.txt` em `test_cases/`), extrai as acoes executadas usando reconhecimento de padroes (regex). Os padroes reconhecidos incluem:
   - `Clicked` → acao `click`
   - `Long click` → acao `long_click`
   - `Checked` → acao `click`
   - `Scroll (up/down/left/right)` → acao `scroll`
   - `Rotate` → acao `rotate`
   - `Home activity` → acao `home`
   - `Go to next activity` → acao `go_to`
   - `Type` / `Entered` / `Input` → acao `type`
3. Para cada acao extraida, identifica o resource ID associado (padrao `package:id/nome`)
4. Um requisito e considerado **coberto** se:
   - Caso o `id` do requisito seja `N/A` (ou invalido): basta que o `action_type` tenha sido executado naquela Activity
   - Caso contrario: o par `(action_type, resource_id)` deve ter sido executado naquela Activity

- **Formula:**

```
Requirements Coverage = (Requisitos Cobertos / Total de Requisitos) * 100
```

**Exemplo:** `72/382 requirements = 18.8%` significa que 72 dos 382 requisitos de interacao foram exercitados.

**Arquivo fonte:** `rlmobtest/training/report.py` (funcoes `_parse_tc_actions` e `_compute_requirements_coverage`, linhas 74-160)

---

## 3. Transcription Coverage (Cobertura de Transcricao)

**O que mede:** A proporcao de casos de teste brutos que foram transcritos com sucesso em casos de teste legiveis pelo pipeline de LLM (CrewAI).

**Como e computada:**

1. **Casos de teste brutos:** Contagem de arquivos `.txt` no diretorio `test_cases/`. Esses arquivos contem logs crus da exploracao automatizada (cliques, scrolls, erros, transicoes de tela).

2. **Transcricoes:** Contagem de arquivos `.txt` no diretorio `transcriptions/`. Cada transcricao e uma versao limpa e estruturada do caso de teste original, seguindo o formato ISO/IEC/IEEE 29119-3, gerada por um agente LLM especializado ("Mobile Test Case Specialist").

3. Antes da transcricao, um filtro de similaridade remove documentos duplicados ou quase-duplicados para evitar transcricoes redundantes.

- **Formula:**

```
Transcription Coverage = (Arquivos Transcritos / Total de Casos de Teste) * 100
```

**Exemplo:** `292/292 test cases = 100.0%` significa que todos os casos de teste foram transcritos com sucesso.

**Arquivo fonte:** `rlmobtest/training/report.py` (linhas 281-283)

---

## 4. JaCoCo Line Coverage (Cobertura de Linhas)

**O que mede:** A proporcao de linhas de codigo-fonte Java/Kotlin do app que foram executadas durante os testes.

**Como e computada:**

1. Durante os testes, o agente JaCoCo (instrumentado no APK) grava dados de execucao em arquivos `.ec` (execution data)
2. Os arquivos `.ec` sao mesclados em um unico arquivo:
   ```
   java -jar jacococli.jar merge *.ec --destfile merged.ec
   ```
3. Um relatorio CSV e gerado a partir dos dados mesclados e dos classfiles do APK:
   ```
   java -jar jacococli.jar report merged.ec --classfiles <dir> --csv coverage_report.csv
   ```
   Caso o jacococli moderno falhe (ex: `IncompatibleExecDataVersionException` para formato 0x1006), o sistema tenta automaticamente o fallback com JaCoCo legacy 0.7.4.
4. Do CSV, somam-se os valores de todas as classes:

- **Formula:**

```
Line Coverage = (LINE_COVERED / (LINE_COVERED + LINE_MISSED)) * 100
```

- `LINE_COVERED` = numero total de linhas executadas pelo menos uma vez
- `LINE_MISSED` = numero total de linhas nunca executadas

**Exemplo:** `38.2%` significa que 38.2% das linhas de codigo do app foram executadas.

**Arquivo fonte:** `rlmobtest/utils/jacoco.py` (funcao `parse_coverage_csv`, linhas 143-175)

---

## 5. JaCoCo Branch Coverage (Cobertura de Branches/Ramificacoes)

**O que mede:** A proporcao de ramificacoes logicas (branches) no codigo que foram percorridas durante os testes.

**O que sao branches:** Pontos de decisao no codigo como `if/else`, `switch/case`, loops (`for`, `while`), e operadores ternarios. Cada condicao tem pelo menos dois caminhos possiveis (verdadeiro/falso).

**Como e computada:**

Utiliza o mesmo pipeline JaCoCo descrito acima (merge de `.ec` → CSV, com fallback legacy 0.7.4 se necessario).

- **Formula:**

```
Branch Coverage = (BRANCH_COVERED / (BRANCH_COVERED + BRANCH_MISSED)) * 100
```

- `BRANCH_COVERED` = numero de caminhos de decisao executados
- `BRANCH_MISSED` = numero de caminhos de decisao nao executados

**Exemplo:** `22.1%` significa que apenas 22.1% dos caminhos de decisao foram percorridos, indicando que muitos cenarios condicionais nao foram testados.

**Arquivo fonte:** `rlmobtest/utils/jacoco.py` (funcao `parse_coverage_csv`, linha 172)

---

## 6. JaCoCo Method Coverage (Cobertura de Metodos)

**O que mede:** A proporcao de metodos Java/Kotlin do app que foram invocados pelo menos uma vez durante os testes.

**Como e computada:**

Utiliza o mesmo pipeline JaCoCo descrito acima (merge de `.ec` → CSV, com fallback legacy 0.7.4 se necessario).

- **Formula:**

```
Method Coverage = (METHOD_COVERED / (METHOD_COVERED + METHOD_MISSED)) * 100
```

- `METHOD_COVERED` = numero de metodos executados pelo menos uma vez
- `METHOD_MISSED` = numero de metodos nunca executados

**Exemplo:** `45.1%` significa que 45.1% dos metodos do app foram chamados durante os testes.

**Arquivo fonte:** `rlmobtest/utils/jacoco.py` (funcao `parse_coverage_csv`, linha 174)

---

## Cores das Barras de Progresso

As barras de cobertura no relatorio HTML seguem esta codificacao de cores:

| Cor      | Faixa        | Interpretacao        |
|----------|--------------|----------------------|
| Verde    | >= 70%       | Cobertura boa        |
| Laranja  | >= 40%       | Cobertura moderada   |
| Vermelho | < 40%        | Cobertura baixa      |

---

## Fluxo Geral

```
APK instrumentado com JaCoCo
        |
        v
Exploracao automatizada (RL agent)
        |
        +--> test_cases/*.txt          (logs brutos)
        +--> coverage.ec               (dados de execucao JaCoCo)
        +--> requirements.csv          (requisitos extraidos do APK)
        |
        v
Pos-processamento
        |
        +--> Transcricao via CrewAI    --> transcriptions/*.txt
        +--> Merge + report JaCoCo     --> coverage_report.csv + jacoco_report/
        |    (fallback legacy 0.7.4 para formato 0x1006)
        +--> Calculo de metricas       --> report.html
```
