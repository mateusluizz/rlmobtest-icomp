# Estratégias para Aumentar a Cobertura JaCoCo

> Documento de referência para quando a cobertura estagna ou está abaixo do esperado.
> Data: 2026-03-22

---

## 1. Por que a cobertura estagna?

O agente DQN converge para um conjunto de ações que maximizam recompensa **localmente** — não necessariamente o que exercita mais código. As causas mais comuns de estagnação:

| Causa | Descrição |
|---|---|
| **Loop de ações fáceis** | Agente aprende que clicar em elementos fixos (home, back) tem recompensa razoável e para de explorar |
| **Campos de formulário mal preenchidos** | Campos com validação forte nunca avançam para o próximo estado |
| **Telas de difícil acesso** | Requerem sequência específica de ações para chegar (ex: criar conta antes de entrar) |
| **Branches condicionais** | Código que só executa com dados específicos (ex: saldo negativo, data no passado) |
| **IDs errados no requirements.csv** | Happy path +50 nunca dispara → treino guiado cego (ver seção 2) |
| **Epsilon muito baixo** | Agente parou de explorar antes de cobrir as telas mais difíceis |
| **Código não acionável por UI** | Services, BroadcastReceivers, Workers que só disparam por eventos externos |

---

## 2. Melhoria pendente: `agrupar_ids` em `resolve_best_id()`

**Arquivo:** `rlmobtest/training/generate_requirements.py`
**Função:** `resolve_best_id()` (linha ~95)
**Status:** ❌ Não implementado

### O problema

O LLM às vezes retorna `btn_login` enquanto o APK declara `login_btn` (ou vice-versa).
O matching exato falha → o `requirements.csv` recebe um ID inventado → o happy path **+50** nunca dispara durante o treino guiado → o agente nunca aprende a clicar nos botões certos.

O mesmo vale para `field` type: IDs não resolvidos retornam `"view"` em vez de `"button"` ou `"edittext"`, silenciando `self.buttons` e `self.edittexts`.

### Prefixos a normalizar (do notebook `Script_requisitos.ipynb`)

```python
WIDGET_PREFIXES = re.compile(
    r"^(et|til|btn|tv|iv|cb|rb|spinner|cv|lv|rv|action|view|tab|tabs|drawer|nav)_",
    re.IGNORECASE,
)
```

### Implementação sugerida

```python
def _normalize_id(id_str: str) -> str:
    """Remove prefixos de tipo de widget para comparação semântica."""
    return WIDGET_PREFIXES.sub("", id_str).lower()

def resolve_best_id(mentioned_id, apk_base, package_name):
    if not mentioned_id:
        return "N/A", "view"
    cleaned = mentioned_id.replace("@+id/", "").replace("id/", "").lower()
    norm_cleaned = _normalize_id(cleaned)

    # 1. Matching exato (rápido, sem regressão)
    for item in apk_base:
        if cleaned == item["short_id"].lower():
            return item["full_id"], item["field"].lower()

    # 2. Matching por ID normalizado (novo)
    for item in apk_base:
        if norm_cleaned == _normalize_id(item["short_id"]):
            return item["full_id"], item["field"].lower()

    return f"{package_name}:id/{cleaned}", "view"
```

### Métricas afetadas

| Métrica | Impacto |
|---|---|
| Happy path reward **+50** | Dispara quando agente clica no botão correto |
| Smart inputs de EditText | Campo correto recebe valor de boundary (tc_text +20) |
| `requirements_coverage_pct` | IDs reais no CSV → fuzzy match encontra mais correspondências |
| JaCoCo line/branch (indireto) | Treino guiado mais preciso → mais código exercitado |

---

## 3. Estratégias quando a cobertura estagna

### 3.1 Aumentar diversidade de inputs (curto prazo) 🔜(Analisar)

**Status:** Parcialmente implementado (`SMART_INPUTS` em v0.1.13)

O `SMART_INPUTS` atual cobre boundary cases genéricos. Para apps específicos, adicionar dados do domínio da aplicação:

```python
# Exemplo para app de finanças
SMART_INPUTS["currency"] += ["1234.56", "0.01", "999999999.99"]
SMART_INPUTS["date"] += ["01/01/1900", "31/12/2099"]

# Dados reais extraídos do strings.xml do app (já disponível via app_context.py)
```

**Onde implementar:** `SMART_INPUTS` em `android_env.py` ou torná-lo configurável por app em `settings.json`.

---

### 3.2 Bônus de curiosidade para elementos inexplorados (médio prazo)

**Status:** ❌ Não implementado

O agente recebe +20 por activity nova entre runs (v0.1.15), mas não há bônus por elementos de UI nunca interagidos.

**Ideia:** manter um set de `(activity, resource_id)` visitados. Se o agente interage com um elemento nunca visto, recebe bônus extra.

```python
# Em loop.py, junto com all_visited_activities
all_visited_elements: set[tuple[str, str]] = set()

# No step, ao executar uma ação:
element_key = (activity, action.resourceid)
if element_key not in all_visited_elements:
    reward += 15   # bônus por elemento inexplorado
    all_visited_elements.add(element_key)
```

**Persiste** no checkpoint via `extra_state`, igual ao `visited_activities`.

---

### 3.3 Exploração direcionada por cobertura JaCoCo (longo prazo)

**Status:** ❌ Não implementado

A ideia mais poderosa: usar o relatório JaCoCo para identificar **quais classes têm cobertura baixa** e direcionar o agente para as activities relacionadas.

```
JaCoCo CSV → classes com < 20% coverage → mapear para Activities → dar bônus +30 ao visitar essas activities
```

**Desafio:** requer mapear nome de classe Java → Activity Android → elementos de UI que levam até ela.

**Implementação simplificada:**
1. Ao fim de cada episódio, processar `cumulative_coverage/` com `jacoco.py`
2. Identificar as N classes com menor cobertura
3. Cruzar com `activities_req` para encontrar quais activities hospedam essas classes
4. Adicionar essas activities a uma lista de `priority_activities`
5. No reward, dar bônus extra ao entrar em `priority_activities`

---

### 3.4 Epsilon decay mais lento ou reinício (curto prazo)

**Status:** Configurável via hiperparâmetros

Se o agente converge rápido demais, epsilon cai antes de cobrir telas difíceis.

**Original Agent** (ajustado em v0.1.14):
```python
eps_decay = 1000   # era 500 — decai mais devagar
```

**Estratégias adicionais:**
- **Epsilon restart:** ao fim de cada run, resetar epsilon para `eps_start * 0.5`
- **Epsilon mínimo dinâmico:** aumentar `eps_end` se cobertura ficar abaixo de X%

```python
# Em loop.py, ao carregar checkpoint:
if jacoco_coverage < 30.0:
    agent.steps_done = 0   # reseta epsilon para forçar mais exploração
```

---

### 3.5 Estados iniciais diversificados (médio prazo)

**Status:** ❌ Não implementado

Hoje todo episódio começa do zero (`force-stop + monkey`). Telas profundas (ex: detalhes de uma transação) nunca são o ponto de partida.

**Opções:**

**a) Deep links Android:**
```bash
adb shell am start -a android.intent.action.VIEW \
  -d "app://com.example/transactions/detail/123" \
  com.example
```

**b) Snapshot de estado (emulador):**
```bash
# Salvar estado do emulador com dados pré-carregados
adb emu avd snapshot save "state_with_data"
# Restaurar no início de episódios específicos
adb emu avd snapshot load "state_with_data"
```

**c) Script de setup por activity:**
Em `settings.json`, configurar comandos de setup por tela:
```json
{
  "package_name": "com.example",
  "setup_commands": [
    "adb shell am start -n com.example/.TransactionDetailActivity --ei id 1"
  ]
}
```

---

### 3.6 Detecção e desvio de loops (curto prazo)

**Status:** Parcialmente implementado (stuck detection por activity)

O stuck detector atual verifica se a activity não muda por N steps. Mas o agente pode ficar preso dentro da mesma activity em ações diferentes sem progresso.

**Melhoria:** detectar repetição de sequências de ações:
```python
# Últimas N ações formam um padrão?
action_window = deque(maxlen=10)
action_window.append(current_action_id)

if len(set(action_window)) <= 2:   # alternando só 2 ações
    reward -= 5                     # penalidade de loop
    # forçar ação aleatória (epsilon=1.0 por 5 steps)
```

---

### 3.7 Cobertura de Services e Receivers (longo prazo)

**Status:** ❌ Não implementado

Código em `Service`, `BroadcastReceiver` e `WorkManager` não é acionável por UI. Para exercitá-lo:

```bash
# Disparar broadcast manualmente
adb shell am broadcast -a com.example.ACTION_SYNC -n com.example/.SyncReceiver

# Simular mudança de rede
adb shell am broadcast -a android.net.conn.CONNECTIVITY_CHANGE

# Simular bateria baixa
adb shell am broadcast -a android.intent.action.BATTERY_LOW
```

**Onde implementar:** adicionar broadcasts configuráveis em `settings.json` e disparar aleatoriamente a cada N episódios no `loop.py`.

---

## 4. Diagnóstico rápido: por que minha cobertura está baixa?

```
Cobertura < 15%
    → Agente não está instalando/abrindo o app corretamente?
    → APK foi instrumentado com JaCoCo? (rlmobtest setup)
    → CoverageReceiver está no AndroidManifest? (jacoco_setup.py)

Cobertura entre 15-35% e estagnada
    → Epsilon caiu cedo demais? (aumentar eps_decay)
    → requirements.csv tem IDs corretos? (implementar agrupar_ids)
    → Agente preso em loop? (verificar stuck detection)

Cobertura entre 35-60% e estagnada
    → Telas profundas não acessadas? (deep links ou setup commands)
    → Campos de formulário com validação forte? (melhorar SMART_INPUTS)
    → Elementos nunca interagidos? (implementar bônus de curiosidade 3.2)

Cobertura > 60% e estagnada
    → Código não acionável por UI (Services, Workers)? (broadcasts 3.7)
    → Branches dependentes de dados externos (rede, GPS, câmera)?
    → Limite prático atingido para testes de UI
```

---

## 5. Ordem de implementação sugerida

| Prioridade | Melhoria | Esforço | Impacto esperado |
|---|---|---|---|
| 1 | `agrupar_ids` em `resolve_best_id()` | Baixo (~30 linhas) | +5-15% requirements coverage; happy path mais ativo |
| 2 | Epsilon mais lento / reinício por run | Baixo (config) | +3-10% cobertura em telas difíceis |
| 3 | Bônus de curiosidade por elemento UI | Médio | +5-15% cobertura em activities parcialmente visitadas |
| 4 | SMART_INPUTS por domínio da app | Médio | +5-20% em apps com validação forte |
| 5 | Deep links / estados iniciais | Médio | +10-25% em telas profundas |
| 6 | Exploração direcionada por JaCoCo CSV | Alto | +10-30% (requer mapeamento classe→UI) |
| 7 | Broadcasts para Services/Receivers | Alto | Desbloqueia código não-UI |
