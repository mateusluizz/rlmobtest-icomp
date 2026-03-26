# Tutorial: Parâmetros da DQN no RLMobTest

Este documento explica cada parâmetro configurável da DQN, dividido em duas partes:
os **parâmetros do usuário** (que você configura no `settings.json` e na linha de comando)
e os **hiperparâmetros internos** (definidos no código dos agentes).

---

## Parte 1 — Parâmetros do Usuário

Esses são os parâmetros que você configura no arquivo `rlmobtest/config/settings.json`:

```json
{
  "apk_name": "moneytracker.apk",
  "package_name": "com.blogspot.e_kanivets.moneytracker",
  "source_code": "open_money_tracker-dev.zip",
  "is_coverage": true,
  "is_req": false,
  "time_exploration": 3600,
  "time_guided": 3600,
  "episodes": 20
}
```

### Tabela de referência

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `apk_name` | string | Nome do arquivo APK dentro de `inputs/apks/` |
| `package_name` | string | Nome do pacote Android (ex: `com.example.app`) |
| `source_code` | string | Nome do arquivo zip do código-fonte dentro de `inputs/source_codes/` |
| `is_coverage` | bool | Se `true`, coleta cobertura de código via JaCoCo durante o treino |
| `is_req` | bool | Se `true`, habilita análise de requisitos (happy path). O agente recebe recompensas extras por seguir caminhos específicos no app |
| `time_exploration` | int | Tempo máximo em **segundos** para a fase de exploração. Padrão: 3600 (1 hora) |
| `time_guided` | int | Tempo máximo em **segundos** para a fase guiada (treino com requisitos, Step 3 do pipeline) |
| `episodes` | int | Número máximo de episódios de treino |

### Parâmetros da linha de comando (`rlmobtest train`)

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--mode` | `improved` | Tipo de agente: `original` ou `improved` |
| `--max-steps` | `100` | Máximo de passos (ações) por episódio |
| `--checkpoint` | — | Caminho para um checkpoint `.pt` para retomar treino |

### Como eles interagem

```
time_exploration = 3600   →  O treino roda por no máximo 1 hora
episodes = 20             →  OU no máximo 20 episódios (o que vier primeiro)
max_steps = 100           →  Cada episódio tem no máximo 100 ações

Exemplo: Se cada episódio leva ~3 minutos e você tem 20 episódios,
o treino levará ~60 min. Se time_exploration=1800 (30 min),
o treino para em 30 min mesmo que não tenha completado 20 episódios.
```

---

## Parte 2 — Hiperparâmetros Internos

Esses parâmetros estão definidos no código dos agentes e controlam **como** a rede neural aprende.

### 2.1 Epsilon (Exploração vs. Aproveitamento)

O epsilon (ε) controla o equilíbrio entre **explorar** (ações aleatórias) e **aproveitar** (usar o que já aprendeu).

**Fórmula:** `ε = eps_end + (eps_start - eps_end) × e^(-steps_done / eps_decay)`

| Parâmetro | Original | Melhorado | O que faz |
|-----------|----------|-----------|-----------|
| `eps_start` | 0.9 | 1.0 | Valor inicial do epsilon. Quanto mais alto, mais aleatório no início |
| `eps_end` | 0.05 | 0.01 | Valor mínimo do epsilon. Quanto mais baixo, menos aleatório no final |
| `eps_decay` | 500 | 10000 | Velocidade de decaimento. Quanto maior, mais devagar o agente para de explorar |

**Exemplo prático:**

```
Original (eps_decay=500):
  Após   500 passos → ε ≈ 0.36 (36% aleatório)
  Após  1000 passos → ε ≈ 0.16
  Após  2000 passos → ε ≈ 0.05 (já quase não explora)

Melhorado (eps_decay=10000):
  Após   500 passos → ε ≈ 0.95 (ainda muito aleatório)
  Após  5000 passos → ε ≈ 0.61
  Após 20000 passos → ε ≈ 0.14 (ainda explorando um pouco)
```

**Quando ajustar:**
- App complexo com muitas telas → aumente `eps_decay` (ex: 15000) para explorar mais
- App simples com poucas telas → diminua `eps_decay` (ex: 3000) para convergir mais rápido

---

### 2.2 Gamma (Fator de Desconto)

O gamma (γ) define o quanto o agente valoriza **recompensas futuras** em relação a recompensas imediatas.

| Parâmetro | Original | Melhorado | O que faz |
|-----------|----------|-----------|-----------|
| `gamma` | 0.999 | 0.99 | Peso das recompensas futuras. Mais perto de 1 = mais peso no futuro |

**Analogia:** Imagine que você pode ganhar R$10 agora ou R$15 daqui 5 minutos.
- `gamma=0.99` → O agente aceita esperar um pouco por recompensas maiores
- `gamma=0.5` → O agente prefere recompensas imediatas
- `gamma=0.999` → O agente planeja muito a longo prazo

**Efeito prático:**
```
gamma=0.99:  Recompensa daqui 100 passos vale 0.99^100 ≈ 0.37 do valor original
gamma=0.999: Recompensa daqui 100 passos vale 0.999^100 ≈ 0.90 do valor original
```

**Quando ajustar:**
- Se o agente fica "travado" fazendo ações repetitivas → diminua o gamma (ex: 0.95)
- Se o agente é muito imediatista e não navega bem → aumente o gamma (ex: 0.999)

---

### 2.3 Batch Size (Tamanho do Lote)

Define quantas experiências passadas o agente usa para aprender a cada passo de otimização.

| Parâmetro | Original | Melhorado | O que faz |
|-----------|----------|-----------|-----------|
| `batch_size` | 256 | 128 | Quantidade de experiências por atualização da rede |

**Analogia:** É como quantas provas antigas um aluno revisa antes de estudar um conceito novo.

- **Batch grande (256):** Aprendizado mais estável, mas mais lento por passo
- **Batch pequeno (128):** Aprendizado mais rápido, mas com mais variação

---

### 2.4 Memória (Experience Replay)

A memória armazena experiências passadas `(estado, ação, próximo_estado, recompensa)` para o agente reutilizar no aprendizado.

| Parâmetro | Original | Melhorado | O que faz |
|-----------|----------|-----------|-----------|
| `capacity` | 10.000 | 50.000 | Quantidade máxima de experiências armazenadas |
| Tipo | `ReplayMemory` | `PrioritizedReplayMemory` | Uniforme vs. priorizada |

**ReplayMemory (Original):**
- Sorteia experiências **aleatoriamente** (todas com a mesma chance)
- Simples e funcional

**PrioritizedReplayMemory (Melhorado):**
- Experiências com **maior erro de predição** (TD-error) têm mais chance de serem sorteadas
- O agente revisa mais as situações onde errou bastante

Parâmetros exclusivos da memória priorizada:

| Parâmetro | Valor | O que faz |
|-----------|-------|-----------|
| `alpha` | 0.6 | Grau de priorização. 0 = uniforme, 1 = totalmente priorizada |
| `beta_start` | 0.4 | Peso inicial de correção de viés (importance sampling) |
| `beta_frames` | 100.000 | Frames até beta chegar a 1.0 (correção total) |

**Analogia:**
- `alpha=0`: Todas as experiências têm a mesma chance (= ReplayMemory normal)
- `alpha=1`: Só revisa as experiências onde mais errou
- `alpha=0.6`: Meio-termo — prioriza erros, mas ainda revisa experiências fáceis

---

### 2.5 Otimizador e Taxa de Aprendizado

O otimizador é o algoritmo que ajusta os pesos da rede neural.

| Parâmetro | Original | Melhorado | O que faz |
|-----------|----------|-----------|-----------|
| Otimizador | `RMSprop` | `Adam` | Algoritmo de otimização |
| `lr` (learning rate) | padrão PyTorch | 0.0001 | Tamanho do passo de aprendizado |
| Gradient clip | [-1, 1] (por valor) | norm=10 (por norma) | Limita gradientes para evitar instabilidade |

**Taxa de aprendizado (lr):**
- Muito alta (ex: 0.01) → aprendizado instável, oscila sem convergir
- Muito baixa (ex: 0.00001) → aprendizado muito lento
- 0.0001 é um valor conservador e estável

---

### 2.6 Target Network (Apenas Melhorado)

A rede-alvo é uma **cópia congelada** da rede principal, usada como referência estável durante o aprendizado.

| Parâmetro | Valor | O que faz |
|-----------|-------|-----------|
| `target_update` | 1.000 | A cada 1.000 passos, a rede-alvo é atualizada com os pesos da rede principal |

**Analogia:** É como ter um professor (target) que só atualiza seu conhecimento periodicamente, enquanto o aluno (policy) aprende continuamente. Isso evita que o aluno fique confuso ao tentar aprender de um professor que muda o tempo todo.

Sem target network (Original): a rede usa a si mesma como referência, o que pode causar instabilidade.

---

### 2.7 Número de Ações

| Parâmetro | Valor | O que faz |
|-----------|-------|-----------|
| `num_actions` | 30 | Máximo de ações que a rede neural pode representar |

Este é o tamanho da camada de saída da rede. Em cada estado, apenas as primeiras N ações (onde N = número de elementos interagíveis na tela) são consideradas.

---

## Parte 3 — Recompensas

As recompensas não são "parâmetros configuráveis", mas são valores fixos no código que definem o que o agente considera bom ou ruim:

| Evento | Valor | Arquivo |
|--------|-------|---------|
| Ação diferente da anterior | +1 | `reward.py` |
| Repetir a mesma ação | -2 | `reward.py` |
| Navegar para nova tela (não-home) | +5 | `reward.py` |
| Sair do app (home/outapp) | -5 | `reward.py` |
| Descobrir tela nova | +10 | `reward.py` + `loop.py` |
| Crash do app | -5 | `reward.py` |
| Ações do happy path (quando `is_req=true`) | +5 a +50 | `android_env.py` |

---

## Parte 4 — Arquitetura da Rede Neural

### OriginalDQN

```
Entrada: Imagem 38×38 (3 canais RGB)
    ↓
Conv2d(3→16, kernel=5, stride=2) + BatchNorm + ReLU    → extrai bordas e formas simples
    ↓
Conv2d(16→32, kernel=5, stride=2) + BatchNorm + ReLU   → combina formas em padrões
    ↓
Conv2d(32→32, kernel=5, stride=2) + BatchNorm + ReLU   → detecta elementos de UI
    ↓
Flatten → 448 neurônios
    ↓
Linear(448→30)                                          → pontuação para cada ação
```

### DuelingDQN

```
Entrada: Imagem 38×38 (3 canais RGB)
    ↓
Conv2d(3→32, kernel=8, stride=4) + ReLU
    ↓
Conv2d(32→64, kernel=4, stride=2) + ReLU
    ↓
Conv2d(64→64, kernel=3, stride=1) + ReLU
    ↓
Flatten
    ↓
    ├── Value Stream:     Linear→512→ReLU→1        → "quão boa é esta tela?"
    │
    └── Advantage Stream: Linear→512→ReLU→30       → "qual ação é melhor que a média?"
    ↓
Q(s,a) = V(s) + [A(s,a) - média(A)]               → pontuação final por ação
```

**Vantagem do Dueling:** Separa "valor da tela" de "vantagem da ação". Isso permite que a rede aprenda que uma tela é boa/ruim independente da ação, e vice-versa. Resulta em aprendizado mais eficiente.

---

## Resumo: Tabela Comparativa Completa

| Parâmetro | Original | Melhorado |
|-----------|----------|-----------|
| Rede | OriginalDQN | DuelingDQN |
| Otimizador | RMSprop | Adam (lr=1e-4) |
| Batch size | 256 | 128 |
| Memória | Uniforme (10k) | Priorizada (50k) |
| Gamma | 0.999 | 0.99 |
| Epsilon start | 0.9 | 1.0 |
| Epsilon end | 0.05 | 0.01 |
| Epsilon decay | 500 | 10.000 |
| Target network | Não | Sim (atualiza a cada 1k passos) |
| Double DQN | Não | Sim |
| Gradient clip | [-1, 1] valor | norm=10 |
| Loss | Smooth L1 | Smooth L1 (ponderada por PER) |
