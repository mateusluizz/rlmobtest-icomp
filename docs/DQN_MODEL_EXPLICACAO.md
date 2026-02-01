# Explicação do Arquivo dqn_model.py

Este documento explica o funcionamento do arquivo `agent/dqn_model.py`, que implementa uma **Deep Q-Network (DQN)** para aprendizado por reforço.

---

## O que é DQN?

**DQN (Deep Q-Network)** é uma técnica de Inteligência Artificial onde o computador aprende **por tentativa e erro**, igual uma criança aprendendo a andar de bicicleta.

O objetivo é treinar um agente (robô) para interagir com um aplicativo móvel, aprendendo quais ações levam aos melhores resultados.

---

## Visão Geral das Partes

| Componente | Linhas | Função |
|------------|--------|--------|
| Configuração CUDA | 21-26 | Detecta GPU para processamento rápido |
| Classe `DQN` | 30-46 | Rede neural que "enxerga" a tela |
| Classe `ReplayMemory` | 49-68 | Memória de experiências passadas |
| Hiperparâmetros | 71-77 | Configurações do aprendizado |
| `select_action()` | 91-109 | Escolhe qual ação executar |
| `optimize_model()` | 115-157 | Treina a rede neural |

---

## 1. Configuração de Hardware (linhas 21-26)

```python
USE_CUDA = torch.cuda.is_available()
FloatTensor = torch.cuda.FloatTensor if USE_CUDA else torch.FloatTensor
```

### O que faz
Verifica se o computador tem uma **placa de vídeo (GPU)** disponível.

### Por quê?
GPUs processam redes neurais até **100x mais rápido** que CPUs. É como ter uma calculadora científica vs fazer conta no papel.

---

## 2. A Estrutura "Transition" (linha 27)

```python
Transition = namedtuple("Transition", ("state", "action", "next_state", "reward"))
```

É o **formato de uma memória**. Cada experiência guardada tem 4 partes:

| Campo | Significado | Exemplo no contexto do app |
|-------|-------------|---------------------------|
| `state` | Foto da tela atual | Screenshot do app |
| `action` | O que o robô fez | Clicou no botão X |
| `next_state` | Foto depois da ação | Nova tela que apareceu |
| `reward` | Recompensa recebida | +1 se descobriu tela nova, -1 se crashou |

---

## 3. Arquitetura da Rede Neural (linhas 30-46)

```python
class DQN(nn.Module):
    def __init__(self):
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, 30)
```

### Camadas Convolucionais (`Conv2d`)

Funcionam como **detectores de padrões**. Imagine vários "carimbos" passando pela imagem:

- **Primeira camada**: Detecta coisas simples (bordas, cores, linhas)
- **Segunda camada**: Combina padrões simples (formas, botões)
- **Terceira camada**: Reconhece elementos complexos (menus, ícones)

### Os números significam:

| Parâmetro | Valor | Significado |
|-----------|-------|-------------|
| Entrada | `3` | 3 canais de cor (RGB: vermelho, verde, azul) |
| Filtros | `16, 32` | Quantidade de "detectores" em cada camada |
| `kernel_size` | `5` | Tamanho do "carimbo" (5x5 pixels) |
| `stride` | `2` | Pula 2 pixels por vez (reduz tamanho da imagem) |

### BatchNorm (`bn1`, `bn2`, `bn3`)

É como **calibrar uma balança** antes de pesar. Normaliza os valores para que o aprendizado seja mais estável.

### Função de Ativação ReLU

```python
def forward(self, x):
    x = F.relu(self.bn1(self.conv1(x)))
    x = F.relu(self.bn2(self.conv2(x)))
    x = F.relu(self.bn3(self.conv3(x)))
    x = x.view(x.size(0), -1)
    return self.head(x)
```

**ReLU** é um filtro simples: se o valor é negativo, vira zero. Se é positivo, mantém. Isso ajuda a rede a aprender padrões não-lineares (coisas complexas do mundo real).

### Diagrama da Rede

```
Imagem (3 canais RGB)
         │
         ▼
┌─────────────────┐
│   Conv1 + BN1   │  → 16 filtros
│      ReLU       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Conv2 + BN2   │  → 32 filtros
│      ReLU       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Conv3 + BN3   │  → 32 filtros
│      ReLU       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flatten (448)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Linear (30)   │  → 30 ações possíveis
└─────────────────┘
```

---

## 4. Memória de Replay (linhas 49-68)

```python
class ReplayMemory:
    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, *args):
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = Transition(*args)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)
```

### O que é
É como um **álbum de fotos** das experiências passadas com capacidade limitada (10.000 memórias).

### Como funciona
- **Buffer circular**: Quando enche, sobrescreve as memórias mais antigas
- **Amostragem aleatória**: Pega experiências aleatórias para evitar "viciar" o aprendizado

### Por que é importante?
Sem replay memory, a rede só aprenderia com experiências recentes e "esqueceria" o que aprendeu antes.

---

## 5. Hiperparâmetros (linhas 71-77)

```python
BATCH_SIZE = 256
GAMMA = 0.999
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 500
```

| Parâmetro | Valor | Significado |
|-----------|-------|-------------|
| `BATCH_SIZE` | 256 | Quantas memórias usa para estudar de cada vez |
| `GAMMA` | 0.999 | Quanto valoriza recompensas futuras (0.999 = muito!) |
| `EPS_START` | 0.9 | 90% de chance de ação aleatória no início |
| `EPS_END` | 0.05 | 5% de chance de ação aleatória no final |
| `EPS_DECAY` | 500 | Velocidade da transição entre curioso → confiante |

### Sobre o GAMMA (Fator de Desconto)

Imagine que você pode ganhar R$100 hoje ou R$110 amanhã:

- `GAMMA = 0` → Só quer dinheiro AGORA (imediatista)
- `GAMMA = 0.999` → Aceita esperar por recompensas maiores (paciente)

---

## 6. Política Epsilon-Greedy (linhas 91-109)

```python
def select_action(state, actions):
    global steps_done
    sample = random.random()
    eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(
        -1.0 * steps_done / EPS_DECAY
    )
    steps_done += 1
    if sample > eps_threshold:
        # Explora: usa o conhecimento
        with torch.no_grad():
            vals = model(Variable(state.type(dtype))).data[0]
            max_idx = vals[: len(actions)].max(0)[1]
            return LongTensor([[max_idx]])
    else:
        # Exploita: ação aleatória
        return LongTensor([[random.randrange(len(actions))]])
```

### Curva de Decaimento do Epsilon

```
Probabilidade de explorar (ação aleatória)
     │
0.9  │████
     │    ████
     │        ████
     │            ████
0.05 │                ████████████████████
     │________________________________________________
         0        500       1000      1500+    passos
```

### Explicação

- **No início (90% aleatório)**: O agente experimenta tudo, descobre o ambiente
- **No final (5% aleatório)**: Usa o conhecimento adquirido, mas ainda tenta coisas novas ocasionalmente

É como um estudante: no começo experimenta vários métodos de estudo, depois foca no que funciona melhor.

---

## 7. Otimização do Modelo (linhas 115-157)

Este é o **coração do algoritmo**. É onde o aprendizado realmente acontece.

### Passo 1: Verificar se há memórias suficientes

```python
if len(memory) < BATCH_SIZE:
    return
```

Só começa a aprender quando tem pelo menos 256 experiências.

### Passo 2: Pegar memórias aleatórias

```python
transitions = memory.sample(BATCH_SIZE)
batch = Transition(*zip(*transitions))
```

Pega 256 experiências aleatórias. Por que aleatórias? Para não "viciar" o aprendizado em experiências recentes.

### Passo 3: Separar estados finais e não-finais

```python
non_final_mask = BoolTensor(tuple(map(lambda s: s is not None, batch.next_state)))
```

Alguns estados são "finais" (app crashou, fim do episódio). Esses precisam de tratamento especial.

### Passo 4: Calcular valores Q atuais

```python
state_action_values = model(state_batch).gather(1, action_batch)
```

Pergunta à rede: "Qual o valor da ação que foi tomada naquele estado?"

### Passo 5: Calcular valores Q esperados (Equação de Bellman)

```python
next_state_values = Variable(torch.zeros(BATCH_SIZE).type(Tensor))
next_state_values[non_final_mask] = model(non_final_next_states).max(1)[0]
expected_state_action_values = (next_state_values * GAMMA) + reward_batch
```

**Equação de Bellman simplificada:**

```
Q(s,a) = recompensa_imediata + γ × max(Q(próximo_estado))
```

Traduzindo: *"O valor de uma ação = recompensa imediata + valor futuro descontado"*

**Exemplo prático:**
- Clicar num botão deu +1 de recompensa
- A próxima tela tem valor estimado de 10
- Valor total = 1 + (0.999 × 10) = **10.99**

### Passo 6: Calcular o erro (loss)

```python
loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)
```

Compara o que o robô **previu** com o que **realmente aconteceu**. A diferença é o erro.

O `smooth_l1_loss` (também chamado de Huber Loss) é menos sensível a outliers que o erro quadrático comum.

### Passo 7: Backpropagation e atualização

```python
optimizer.zero_grad()
loss.backward()
for param in model.parameters():
    param.grad.data.clamp_(-1, 1)
optimizer.step()
```

| Linha | O que faz |
|-------|-----------|
| `zero_grad()` | Limpa gradientes anteriores |
| `backward()` | Calcula como ajustar cada peso |
| `clamp_(-1, 1)` | Limita ajustes para evitar instabilidade |
| `step()` | Aplica os ajustes aos pesos |

**Gradient Clipping** (linha do `clamp_`): Limita os ajustes entre -1 e 1. Evita mudanças bruscas que poderiam "desestabilizar" o aprendizado (como girar demais a tarraxa do violão e arrebentar a corda).

---

## Fluxo Completo do Aprendizado

```
┌─────────────────────────────────────────────────────────────┐
│                    CICLO DE APRENDIZADO                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Ver tela       │
                    │  (state)        │
                    └────────┬────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Escolher ação  │ ← epsilon-greedy
                    │  (explorar ou   │
                    │   exploitar?)   │
                    └────────┬────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Executar ação  │
                    │  no app         │
                    └────────┬────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Receber reward │
                    │  e ver nova     │
                    │  tela           │
                    └────────┬────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Guardar na     │
                    │  memória        │
                    └────────┬────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Estudar        │
                    │  (se tiver 256+ │
                    │   memórias)     │
                    └────────┬────────┘
                              │
                              ▼
                         REPETIR
```

---

## Resumo

O arquivo `dqn_model.py` implementa um agente de aprendizado por reforço que:

1. **Observa** a tela do aplicativo através de screenshots
2. **Decide** qual ação tomar usando uma rede neural convolucional
3. **Executa** a ação e observa o resultado
4. **Memoriza** a experiência para aprender depois
5. **Aprende** comparando previsões com resultados reais
6. **Melhora** gradualmente suas decisões ao longo do tempo

O objetivo final é que o agente aprenda a navegar pelo aplicativo de forma inteligente, descobrindo novas telas e funcionalidades automaticamente.
