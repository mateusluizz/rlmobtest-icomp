# Sugestões de Melhoria de Cobertura — RLMobTest

Este documento descreve o diagnóstico e as sugestões concretas para melhorar as métricas de cobertura de requisitos e cobertura de código (JaCoCo) da ferramenta DRL-MOBTest.

---

## Diagnóstico Atual

### Cobertura de Requisitos (41–60%)

1. **Extração via LLM imprecisa** — o Gemma 3:4b extrai requisitos dos logs brutos, mas frequentemente erra IDs ou normaliza de forma incorreta.
2. **Matching rígido** — exige par exato `(action_type, resource_id)` na mesma activity. Se o ID mudou ligeiramente, não conta como coberto.
3. **Requisitos inalcançáveis** — o LLM pode gerar requisitos para telas que o agente nunca atinge (deep activities).

### Cobertura JaCoCo (branches ~23%, linhas ~47%)

1. **JaCoCo não influencia o treinamento** — os arquivos `.ec` são coletados a cada step, mas **nunca retroalimentam a função de recompensa**. O agente não "sabe" que precisa cobrir mais código.
2. **Estado visual 38×38** — resolução muito baixa perde detalhes de UI (botões pequenos, menus dropdown).
3. **Exploração superficial** — o agente favorece *happy paths* e activities novas, mas não exercita condicionais (branches).
4. **Inputs aleatórios** — textos gerados são random letters/numbers, não provocam caminhos condicionais como validação de email, campos vazios, overflow, etc.

---

## Resultados de Referência (1ª rodada)

| Aplicação     | Requisitos (%) | Instrução (%) | Linhas (%) | Branches (%) | Métodos (%) |
|---------------|---------------|--------------|-----------|-------------|------------|
| Money Tracker | 41,6          | 35,9         | 36,5      | 21,1        | 42,7       |
| Exceer        | 44,3          | 30,0         | 42,8      | 34,0        | 53,9       |
| SilliNote     | 57,0          | 69,3         | 68,9      | 36,7        | 78,4       |
| ToDo List     | 60,0          | 44,0         | 40,6      | 0,0         | 33,3       |

---

## Sugestões de Melhoria

### 1. Retroalimentar JaCoCo na Função de Recompensa (maior impacto)

**Arquivo:** `rlmobtest/training/reward.py`

Atualmente o JaCoCo é coletado a cada step mas completamente ignorado na recompensa. Adicionar um **reward incremental por cobertura nova** faria o agente aprender quais ações aumentam cobertura de código e priorizá-las.

```python
def coverage_reward(prev_coverage, curr_coverage):
    """Bônus por linhas/branches novas cobertas neste step."""
    delta_lines = curr_coverage["line_pct"] - prev_coverage["line_pct"]
    delta_branches = curr_coverage["branch_pct"] - prev_coverage["branch_pct"]

    reward = 0
    if delta_lines > 0:
        reward += delta_lines * 5    # +5 por cada 1% de linha nova
    if delta_branches > 0:
        reward += delta_branches * 10  # +10 por cada 1% de branch novo (mais raro, mais valioso)
    return reward
```

**Integração no loop de treinamento (`loop.py`):**
- Antes de cada step: salvar `prev_coverage = get_current_coverage()`
- Depois do step: calcular `curr_coverage = get_current_coverage()`
- Somar `coverage_reward(prev, curr)` à recompensa do step

**Considerações:**
- Pode adicionar latência (~0.5s por step para pull do `.ec` e parse). Avaliar se a coleta já acontece e se o overhead é aceitável.
- Alternativa: calcular o delta de cobertura a cada N steps (ex: a cada 5 steps) em vez de todo step.

**Impacto estimado:** Alto — o agente passa a otimizar diretamente para cobertura de código.

---

### 2. Flexibilizar Matching de Requisitos (fuzzy matching)

**Arquivo:** `rlmobtest/training/report.py`

O matching atual exige par exato `(action_type, resource_id)`. IDs que diferem por um sufixo, prefixo de package, ou variação de case não são reconhecidos. Implementar fuzzy matching:

```python
from difflib import SequenceMatcher

def fuzzy_match_id(req_id, test_id, threshold=0.8):
    """Match parcial de IDs para tolerar variações."""
    if req_id == "N/A" or test_id == "N/A":
        return req_id == test_id
    # Comparar só a parte após o último '/'
    req_short = req_id.split("/")[-1] if "/" in req_id else req_id
    test_short = test_id.split("/")[-1] if "/" in test_id else test_id
    ratio = SequenceMatcher(None, req_short, test_short).ratio()
    return ratio >= threshold
```

**Também considerar:**
- Normalizar IDs removendo prefixo de package (`com.example:id/btn_save` → `btn_save`)
- Aceitar `action_type` sinônimos (ex: `tap` = `click`, `input` = `type`)
- Matching por `content-desc` ou `text` do elemento quando `resource_id` é vazio

**Impacto estimado:** Médio — recupera requisitos "quase" cobertos que eram descartados por diferenças triviais.

---

### 3. Inputs Semânticos para Exercitar Branches

**Arquivo:** `rlmobtest/android/android_env.py` (método `_get_actions()`)

Os textos gerados atualmente são aleatórios (`random letters`, `random digits`). Para provocar **branches** (validações, error paths, edge cases), adicionar inputs inteligentes:

```python
SMART_INPUTS = {
    "email": ["", "invalid", "a@b.c", "test@test.com", "@", "x" * 256],
    "password": ["", "1", "12345678", "a" * 100, "P@ssw0rd!"],
    "number": ["0", "-1", "999999999", "abc", "", "3.14", "00001"],
    "text": ["", " ", "a" * 1000, "<script>alert(1)</script>", "null", "   spaces   "],
    "date": ["00/00/0000", "31/02/2025", "01/01/2000", "99/99/9999"],
    "phone": ["", "123", "+5511999999999", "abc", "0000000000"],
    "currency": ["0", "-100", "0.001", "999999.99", "abc"],
}
```

**Como integrar:**
- Detectar o tipo de campo via `android:inputType`, `android:hint`, ou `content-desc`
- Selecionar inputs do dicionário `SMART_INPUTS` correspondente
- Misturar com os inputs aleatórios existentes (ex: 50% smart, 50% random)

**Impacto estimado:** Alto — provoca caminhos de validação e tratamento de erro no código, aumentando significativamente branch coverage.

---

### 4. Aumentar Resolução do Estado Visual

**Arquivo:** `rlmobtest/android/android_env.py` (método `_image_to_torch()`)

O estado atual é uma imagem 38×38 pixels — resolução muito baixa que dificulta a distinção entre telas similares. O padrão em DQN para Atari é 84×84.

```python
# Alterar de:
T.Resize(38, interpolation=Image.Resampling.BICUBIC)

# Para:
T.Resize(84, interpolation=Image.Resampling.BICUBIC)
```

**Ajustes necessários nas camadas convolucionais do DQN:**

```python
# OriginalDQN — ajustar para 84x84 input
Conv2d(3, 32, kernel_size=8, stride=4)   # → (32, 20, 20)
Conv2d(32, 64, kernel_size=4, stride=2)  # → (64, 9, 9)
Conv2d(64, 64, kernel_size=3, stride=1)  # → (64, 7, 7)
# Flatten → 3136 dims
Linear(3136, 512)
Linear(512, 30)  # 30 actions
```

**Considerações:**
- Aumenta uso de memória GPU e tempo de treinamento
- Avaliar se o dispositivo (RTX 5070Ti) comporta o aumento
- Pode ser necessário reduzir batch size de 256 para 128

**Impacto estimado:** Médio — melhor distinção entre estados leva a política mais informada.

---

### 5. Ajustar Hiperparâmetros de Exploração

**Arquivo:** `rlmobtest/training/agents/` (OriginalAgent e ImprovedAgent)

#### OriginalAgent (configuração atual problemática):

| Parâmetro    | Atual  | Sugerido | Justificativa                                    |
|-------------|--------|----------|--------------------------------------------------|
| EPS_DECAY   | 500    | 2000     | Explorar por mais tempo antes de exploitar        |
| GAMMA       | 0.999  | 0.99     | Foco mais imediato, menos ruído de recompensas distantes |
| BATCH_SIZE  | 256    | 128      | Atualizações mais frequentes com gradientes menos ruidosos |
| MEMORY_SIZE | 10000  | 50000    | Mais diversidade de experiências para replay      |

#### ImprovedAgent (já melhor, ajustes finos):

| Parâmetro      | Atual  | Sugerido | Justificativa                              |
|---------------|--------|----------|--------------------------------------------|
| EPS_DECAY     | 10000  | 5000     | Pode ser um pouco mais rápido dado o tempo limitado (1h) |
| TARGET_UPDATE | 1000   | 500      | Sincronizar target network mais frequentemente |
| LR            | 1e-4   | 3e-4     | Aprendizado ligeiramente mais rápido       |

**Impacto estimado:** Médio — mais exploração = mais activities e caminhos de código descobertos.

---

### 6. Multi-run com Acumulação de Conhecimento (Curriculum Learning)

Atualmente cada execução do pipeline começa do zero — o agente não retém conhecimento entre runs. Implementar acumulação:

**Fluxo proposto:**

```
Run 1: Exploração (1h) → salvar checkpoint + lista de activities/requisitos cobertos
    ↓
Run 2: Guiado (1h) → carregar checkpoint → focar em requisitos NÃO cobertos
    ↓
Run 3: Refinamento (1h) → carregar checkpoint → focar em activities NÃO visitadas
    ↓
Relatório final: merge de todos os .ec + todos os test cases
```

**Implementação:**
- Salvar `covered_requirements` e `visited_activities` no checkpoint
- No carregamento, filtrar requisitos já cobertos do CSV
- Aumentar recompensa para requisitos/activities não cobertos: `reward * 2`
- Fazer merge cumulativo dos `.ec` de todas as runs

**Impacto estimado:** Alto — conhecimento não se perde entre execuções, cobertura cresce monotonicamente.

---

### 7. Encoding de Estado Híbrido (Visual + Textual)

**Estado atual:** apenas screenshot 38×38 (sem informação textual).

**Proposta:** concatenar ao vetor visual um encoding da hierarquia de UI:

```python
# Features textuais por estado
ui_features = [
    num_clickable_elements,      # quantos botões disponíveis
    num_edittexts,               # quantos campos de texto
    num_scrollables,             # quantos elementos scrolláveis
    is_dialog_open,              # 0 ou 1
    activity_hash % 1000,        # encoding da activity atual
    steps_in_this_activity,      # há quanto tempo está aqui
    pct_requirements_covered,    # progresso de requisitos (0-1)
    pct_jacoco_lines,            # progresso de cobertura (0-1)
]
# Concatenar com saída do CNN antes da camada final
combined = torch.cat([cnn_features, ui_features_tensor])
```

**Impacto estimado:** Alto — o agente ganha consciência do progresso e do contexto além dos pixels.

---

## Resumo de Prioridades

| #  | Melhoria                          | Métrica Alvo     | Impacto  | Complexidade |
|----|-----------------------------------|-----------------|----------|-------------|
| 1  | JaCoCo na recompensa              | Linhas/Branches | **Alto** | Média       |
| 2  | Fuzzy matching de IDs             | Requisitos      | Médio    | Baixa       |
| 3  | Smart inputs (boundary/edge case) | Branches        | **Alto** | Média       |
| 4  | Resolução 84×84                   | Todas           | Médio    | Média       |
| 5  | Ajuste de hiperparâmetros         | Todas           | Médio    | Baixa       |
| 6  | Multi-run acumulativo             | Todas           | **Alto** | Alta        |
| 7  | Estado híbrido (visual+textual)   | Todas           | **Alto** | Alta        |

**Recomendação de ordem de implementação:**
1. **Quick wins:** #2 (fuzzy matching) + #5 (hiperparâmetros) — baixa complexidade, ganho imediato
2. **Alto impacto:** #1 (JaCoCo reward) + #3 (smart inputs) — maior ganho de cobertura
3. **Longo prazo:** #6 (multi-run) + #7 (estado híbrido) — mudanças arquiteturais mais profundas
