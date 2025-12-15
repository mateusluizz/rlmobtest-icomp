# Changelog - Alterações Recentes

## Data: 2025-12-01

---

## 1. Logs de Progresso

**Arquivo:** `main.py` (linhas 684-773)

Adicionado sistema de logs para acompanhar o progresso do treinamento em tempo real.

### Log de Episódio
No início de cada episódio, exibe:
- Número do episódio
- Valor de epsilon (exploração)
- Total de steps executados

### Log de Step
A cada 10 steps, exibe:
- Número do step atual
- Recompensa obtida
- Q-value estimado
- Loss da rede neural
- Activity atual

### Exemplo de Output
```
🎮 Episode 1 | ε=0.900 | Steps: 0
   Step 0 | R=+1 | Q=0.00 | Loss=N/A | Act=protect.budgetwatch
   Step 10 | R=+5 | Q=0.12 | Loss=0.0234 | Act=protect.budgetwatch
   Step 20 | R=-2 | Q=0.15 | Loss=0.0198 | Act=protect.budgetwatch

🎮 Episode 2 | ε=0.875 | Steps: 45
   Step 0 | R=+1 | Q=0.18 | Loss=0.0187 | Act=protect.budgetwatch
```

---

## 2. Sistema Anti-Stuck

**Arquivo:** `environment/android_env.py` (linhas 505-652)

Sistema para evitar que o agente fique preso em telas problemáticas como calendários, date pickers e dialogs.

### 2.1 Detecção de Dialogs (`_detect_dialog`)

Detecta automaticamente componentes problemáticos:
- `android.widget.DatePicker`
- `android.widget.TimePicker`
- `android.widget.CalendarView`
- `android.widget.NumberPicker`
- `android.app.DatePickerDialog`
- `android.app.TimePickerDialog`

### 2.2 Escape de Dialogs (`_escape_dialog`)

Sequência de tentativas para escapar:
1. **Primeira tentativa:** Clicar em "OK", "Done", "Confirm", "Set"
2. **Segunda tentativa:** Clicar em "Cancel", "Cancelar"
3. **Última tentativa:** Pressionar botão Back

### 2.3 Detecção de Stuck (`_check_stuck`)

Monitora se o agente está na mesma activity por muito tempo:
- Contador de steps na mesma activity
- Após `max_same_activity` steps (default: 15), tenta escapar
- Incrementa contador de tentativas de escape

### 2.4 Retorno à Home (`_return_to_app_home`)

Quando todas as tentativas de escape falham:
1. Force stop do app (`adb shell am force-stop`)
2. Reinicia o app (`adb shell monkey`)
3. Limpa lista de ações do test case
4. Registra no arquivo de log

### Fluxo de Escape
```
Stuck 15 steps → Tentativa 1: Back/Dialog escape
        ↓
Ainda stuck 15 steps → Tentativa 2: Back/Dialog escape
        ↓
Ainda stuck 15 steps → Tentativa 3: 🏠 Volta para Home do App
```

### Exemplo de Output
```
⚠️ Stuck in protect.budgetwatch/.DateActivity for 15 steps (attempt 1/3)
📅 Detected calendar, attempting escape...
🔓 Escaped dialog by clicking 'OK'
...
⚠️ Stuck in protect.budgetwatch/.DateActivity for 15 steps (attempt 2/3)
🔙 Pressed back to escape stuck state
...
⚠️ Stuck in protect.budgetwatch/.DateActivity for 15 steps (attempt 3/3)
🏠 Too many escape attempts, returning to app home...
🔄 Force stopping and restarting app...
✅ App restarted at: protect.budgetwatch/.MainActivity
```

---

## 3. Tratamento de UiObjectNotFoundError

**Arquivo:** `environment/android_env.py` (linhas 85-193)

Tratamento robusto para quando elementos UI desaparecem durante a execução.

### 3.1 Verificação de Existência (`_check_element_exists`)

Antes de executar ações que dependem de elementos UI (click, long-click, check, type), verifica se o elemento ainda existe na tela.

```python
def _check_element_exists(self):
    """Verifica se o elemento GUI ainda existe na tela."""
    try:
        if self.gui_object is not None:
            return self.gui_object.exists
    except Exception:
        pass
    return False
```

### 3.2 Try-catch Global no `execute`

Captura qualquer `UiObjectNotFoundError` que escape das verificações individuais:
- Identifica o tipo de erro
- Registra no arquivo de log
- Continua a execução sem crashar

### 3.3 Proteção no `_get_actions`

Se falhar ao obter a hierarquia UI do dispositivo, retorna lista vazia em vez de crashar o script.

### Exemplo de Output
```
⚠️ Element not found for click: android.widget.Button protect.budgetwatch...
⚠️ Element disappeared during action: click
⚠️ Error getting UI hierarchy, returning empty actions
```

---

## 4. Parâmetros Configuráveis

**Arquivo:** `environment/android_env.py` (linhas 421-463)

Novos parâmetros no construtor do `AndroidEnv`:

| Parâmetro | Default | Descrição |
|-----------|---------|-----------|
| `max_same_activity` | 15 | Número de steps na mesma activity antes de tentar escapar |
| `max_escape_attempts` | 3 | Número de tentativas de escape antes de reiniciar o app |
| `max_time_same_activity` | 60 | **NOVO** - Segundos máximos na mesma activity antes de forçar retorno à home |

### Exemplo de Uso
```python
env = AndroidEnv(
    apk,
    app_package,
    coverage_enabled="no",
    max_same_activity=20,         # Mais tolerante (default: 15)
    max_escape_attempts=5,        # Mais tentativas (default: 3)
    max_time_same_activity=120,   # 2 minutos antes de forçar escape (default: 60s)
)
```

---

## 5. Verificação de Tempo (Anti-Stuck por Tempo)

**Arquivo:** `environment/android_env.py` (linhas 650-704)

Sistema de escape baseado em tempo real, complementando a verificação por número de steps.

### Como Funciona

1. **Timer por Activity**: Cada vez que o agente muda de activity, um timer é iniciado
2. **Verificação Contínua**: A cada step, verifica se o tempo na activity atual excedeu o limite
3. **Escape Forçado**: Se exceder `max_time_same_activity` segundos, força retorno à home do app

### Prioridade

A verificação por tempo tem **prioridade mais alta** que a verificação por steps:
- Se o tempo limite for atingido, vai direto para home (sem tentar escapes intermediários)
- Isso garante que o script nunca fique preso por mais de X segundos

### Fluxo de Decisão
```
┌─────────────────────────────────────────────────────────────┐
│                    A cada step                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Tempo >= 60 segundos? │
              └───────────────────────┘
                    │           │
                   SIM         NÃO
                    │           │
                    ▼           ▼
        ┌──────────────┐   ┌───────────────────────┐
        │ 🏠 Volta pra │   │ Steps >= 15 na mesma? │
        │    Home      │   └───────────────────────┘
        └──────────────┘         │           │
                               SIM         NÃO
                                 │           │
                                 ▼           ▼
                    ┌──────────────────┐  ┌──────────┐
                    │ Tenta escapar    │  │ Continua │
                    │ (dialog/back)    │  │ normal   │
                    └──────────────────┘  └──────────┘
```

### Exemplo de Output
```
🎮 Episode 5 | ε=0.750 | Steps: 120
   Step 10 | R=+1 | Q=0.15 | Loss=0.0234 | Act=protect.budgetwatch
   ...
   ⏰ TIME LIMIT: Stuck in protect.budgetwatch/.DateActivity for 62s (max: 60s)
   🏠 Forcing return to app home due to time limit...
   🔄 Force stopping and restarting app...
   ✅ App restarted at: protect.budgetwatch/.MainActivity
```

### Vantagens
- **Garantia de tempo máximo**: O script nunca fica preso por mais de X segundos
- **Independente de steps**: Funciona mesmo se os steps forem muito lentos
- **Complementar**: Funciona junto com a verificação por steps

---

## 6. Timeout em Ações UI (Anti-Travamento)

**Arquivo:** `environment/android_env.py` (linhas 95-111, 175-217)

Sistema de timeout para **ações de interação com elementos** que podem travar indefinidamente.

### Problema Resolvido

Quando o agente clica em certos elementos (WebViews, calendários, inputs especiais), a ação pode travar indefinidamente esperando uma resposta que nunca vem.

### Solução: `_execute_with_timeout`

Método helper na classe `Action` que executa ações com timeout usando `ThreadPoolExecutor`:

```python
def _execute_with_timeout(self, func, env, timeout=30):
    """Executa uma ação com timeout. Retorna True se sucesso, False se timeout."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        future.result(timeout=timeout)
        return True
    # Se timeout, força retorno à home do app
```

### Ações Protegidas

| Ação | Timeout | Ação se timeout |
|------|---------|-----------------|
| `click` | 30s | Reinicia o app |
| `long-click` | 30s | Reinicia o app |
| `check` | 30s | Reinicia o app |
| `type` | 30s | Reinicia o app |

### Exemplo de Output
```
Click: android.widget.LinearLayout protect.budgetwatch...
   ⏰ ACTION TIMEOUT: click took longer than 30s
   🏠 Forcing return to app home...
   🔄 Force stopping and restarting app...
   ✅ App restarted at: protect.budgetwatch/.MainActivity
```

### Nota

Operações como `dump_hierarchy()` e `screenshot()` **não** têm timeout, pois são operações de leitura que normalmente completam rapidamente. O timeout é aplicado apenas em ações de **interação** com elementos UI.

---

## 7. Configuração de Tempo de Treinamento

**Arquivo:** `config/settings.txt`

Tempo de treinamento aumentado de 30 segundos para 300 segundos (5 minutos).

### Antes
```
TIME:30
```

### Depois
```
TIME:300
```

### Recomendações de Tempo
| Cenário | Tempo (segundos) |
|---------|------------------|
| Teste rápido | 300 (5 min) |
| Treinamento curto | 1800 (30 min) |
| Treinamento médio | 3600 (1 hora) |
| Treinamento longo | 7200+ (2+ horas) |

---

## 8. Sistema de Logs com Rich (Cores e Formatação)

**Arquivo:** `main.py`

Interface visual melhorada usando a biblioteca Rich.

### Logs de Episódio
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 Episode 5 │ ε=0.750 │ Total Steps: 120
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Logs de Step (com cores)
- Reward positivo: verde
- Reward negativo: vermelho
- Q-value: ciano
- Loss: amarelo

```
   Step  10 │ R=   +5 │ Q=  0.15 │ Loss=0.0234 │ protect.budgetwatch
   Step  20 │ R=   -2 │ Q=  0.12 │ Loss=0.0198 │ protect.budgetwatch
```

---

## 9. Logging por Execução (Arquivos Separados)

**Arquivo:** `main.py` (função `setup_logging`)

Cada execução agora gera seu próprio arquivo de log.

### Estrutura
```
output/logs/
├── run_20251201_143052.log
├── run_20251201_150030.log
└── run_20251201_161545.log
```

### Conteúdo do Log
```
INFO  2025-12-01 14:30:52  Episode 1 started | epsilon=0.900 | steps=0
DEBUG 2025-12-01 14:30:53  Step 0 | action=5 | reward=1 | activity=MainActivity
INFO  2025-12-01 14:30:55  New activity: SettingsActivity
WARNING 2025-12-01 14:31:00  Crash detected at step 15
```

---

## 10. Tracking de Duração de Episódio

**Arquivo:** `main.py` (classe `TrainingMetrics`)

O sistema agora rastreia quanto tempo cada episódio leva.

### Métricas Coletadas
- Duração de cada episódio individual
- Duração média dos episódios
- Lista completa de durações no JSON

### Como saber a duração de um episódio
Após rodar um treinamento, o sistema mostra:
```
📊 Episode Duration Info
─────────────────────────────
Average Episode Duration: 36.2s
Use this to estimate training time for a given number of episodes
```

### Estimativa de tempo
Se a média é 36.2s por episódio:
- 50 episódios ≈ 30 minutos
- 100 episódios ≈ 1 hora

---

## 11. Escolha entre Tempo ou Episódios

**Arquivo:** `main.py`

Agora você pode escolher entre treinar por tempo ou por número de episódios.

### Argumentos CLI

| Argumento | Descrição | Exemplo |
|-----------|-----------|---------|
| `--time` | Tempo máximo em segundos | `--time 600` (10 min) |
| `--episodes` | Número de episódios | `--episodes 50` |

### Exemplos de Uso

```bash
# Treinar por 10 minutos
python main.py --time 600

# Treinar por 50 episódios
python main.py --episodes 50

# Usar tempo do settings.txt (padrão)
python main.py

# Combinar com modo do agente
python main.py --mode original --time 300
```

### Nota
`--time` e `--episodes` são mutuamente exclusivos. Use apenas um.

---

## 12. Barra de Progresso

**Arquivo:** `main.py` (classe `TrainingProgress`)

Barra de progresso visual para acompanhar o treinamento.

### Por Tempo
```
⠋ Training ████████████████████░░░░░░░░░░░░░░░░░░░░  50% • 05:00 / 10:00
```

### Por Episódios
```
⠋ Training ████████████████████░░░░░░░░░░░░░░░░░░░░  25/50 • 03:45
```

---

## Arquivos Modificados

| Arquivo | Tipo de Alteração |
|---------|-------------------|
| `main.py` | Rich UI, logging por run, duração de episódio, barra de progresso, escolha tempo/episódios |
| `environment/android_env.py` | Sistema anti-stuck, tratamento de erros, timeout em ações |
| `config/settings.txt` | Tempo de treinamento aumentado |

---

## Compatibilidade

Todas as alterações são retrocompatíveis. Os novos parâmetros possuem valores default que mantêm o comportamento similar ao anterior, porém mais robusto.
