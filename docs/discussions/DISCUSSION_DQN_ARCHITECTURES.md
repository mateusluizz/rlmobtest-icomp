# Comparacao: OriginalDQN vs DuelingDQN

**Data:** 2026-02-01
**Arquivo:** `rlmobtest/__main__.py` (linhas 514-575)

---

## Resumo Executivo

O projeto possui duas arquiteturas de rede neural para o agente DQN:

| Arquitetura | Complexidade | Performance Esperada |
|-------------|--------------|---------------------|
| OriginalDQN | Simples | Baseline |
| DuelingDQN | Moderada | Superior em estados com acoes similares |

---

## 1. OriginalDQN

### Codigo

```python
class OriginalDQN(nn.Module):
    def __init__(self, num_actions=30):
        super(OriginalDQN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, num_actions)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = x.view(x.size(0), -1)
        return self.head(x)
```

### Arquitetura

```
Input (3, H, W)
       │
       ▼
┌──────────────────┐
│ Conv2d(3→16)     │  kernel=5, stride=2
│ BatchNorm2d(16)  │
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Conv2d(16→32)    │  kernel=5, stride=2
│ BatchNorm2d(32)  │
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Conv2d(32→32)    │  kernel=5, stride=2
│ BatchNorm2d(32)  │
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Flatten          │
│ Linear(448→30)   │
└────────┬─────────┘
         │
         ▼
   Q(s, a₁...a₃₀)
```

### Caracteristicas

- **Canais:** 3 → 16 → 32 → 32
- **Normalizacao:** BatchNorm apos cada convolucao
- **Feature size:** Fixo em 448 (hardcoded)
- **Saida:** Vetor de Q-values diretamente
- **Parametros:** ~15K (estimativa)

### Formula

```
Q(s, a) = Linear(flatten(conv_features))
```

---

## 2. DuelingDQN

### Codigo

```python
class DuelingDQN(nn.Module):
    def __init__(self, num_actions=30):
        super(DuelingDQN, self).__init__()

        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ReLU(),
        )

        self._feature_size = None
        self.num_actions = num_actions
        self.value_stream = None
        self.advantage_stream = None

    def _initialize_fc(self, feature_size):
        self.value_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, 1)
        )
        self.advantage_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, self.num_actions)
        )

    def forward(self, x):
        features = self.features(x)
        features = features.view(features.size(0), -1)

        if self.value_stream is None:
            self._feature_size = features.size(1)
            self._initialize_fc(self._feature_size)

        value = self.value_stream(features)
        advantage = self.advantage_stream(features)
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        return q_values
```

### Arquitetura

```
Input (3, H, W)
       │
       ▼
┌──────────────────┐
│ Conv2d(3→32)     │  kernel=8, stride=4
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Conv2d(32→64)    │  kernel=4, stride=2
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Conv2d(64→64)    │  kernel=3, stride=1
│ ReLU             │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Flatten          │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────────┐
│ Value  │ │ Advantage  │
│ Stream │ │ Stream     │
├────────┤ ├────────────┤
│ Lin→512│ │ Lin→512    │
│ ReLU   │ │ ReLU       │
│ Lin→1  │ │ Lin→30     │
└───┬────┘ └─────┬──────┘
    │            │
    ▼            ▼
  V(s)        A(s, a)
    │            │
    └─────┬──────┘
          │
          ▼
   Q(s,a) = V(s) + (A(s,a) - mean(A))
```

### Caracteristicas

- **Canais:** 3 → 32 → 64 → 64
- **Normalizacao:** Nenhuma (apenas ReLU)
- **Feature size:** Dinamico (lazy initialization)
- **Saida:** Combinacao de Value + Advantage
- **Parametros:** ~1.7M (estimativa para input 84x84)

### Formula

```
V(s)    = value_stream(features)           # Escalar
A(s, a) = advantage_stream(features)       # Vetor [30]
Q(s, a) = V(s) + (A(s, a) - mean(A(s, ·))) # Vetor [30]
```

---

## 3. Comparacao Detalhada

### 3.1 Arquitetura Convolucional

| Camada | OriginalDQN | DuelingDQN |
|--------|-------------|------------|
| Conv1 | 3→16, k=5, s=2 | 3→32, k=8, s=4 |
| Conv2 | 16→32, k=5, s=2 | 32→64, k=4, s=2 |
| Conv3 | 32→32, k=5, s=2 | 64→64, k=3, s=1 |
| Normalizacao | BatchNorm | Nenhuma |
| Ativacao | ReLU | ReLU |

**Observacao:** A arquitetura do DuelingDQN segue o padrao do paper original do DQN (Mnih et al., 2015), enquanto a OriginalDQN usa kernels menores e BatchNorm.

### 3.2 Camadas Fully Connected

| Aspecto | OriginalDQN | DuelingDQN |
|---------|-------------|------------|
| Estrutura | 1 camada linear | 2 streams paralelos |
| Neurons | 448 → 30 | features → 512 → 1 (value) |
|         |            | features → 512 → 30 (advantage) |
| Feature size | Fixo (448) | Dinamico |

### 3.3 Inicializacao

| Aspecto | OriginalDQN | DuelingDQN |
|---------|-------------|------------|
| Tipo | Eager (no __init__) | Lazy (no forward) |
| Flexibilidade | Requer input size conhecido | Adapta-se ao input |
| Checkpoint | Simples | Requer salvar feature_size |

---

## 4. Fundamento Teorico

### 4.1 DQN Tradicional

O Q-value e aprendido diretamente:

```
Q(s, a) = f(s, a; θ)
```

**Problema:** Para aprender que um estado e ruim, a rede precisa aprender Q baixo para TODAS as acoes separadamente.

### 4.2 Dueling DQN (Wang et al., 2016)

Decompoe o Q-value em dois componentes:

```
Q(s, a) = V(s) + A(s, a)
```

Onde:
- **V(s)** = Valor do estado (quao bom e estar neste estado)
- **A(s, a)** = Vantagem da acao (quao melhor e esta acao vs outras)

### 4.3 Por que subtrair a media?

```
Q(s, a) = V(s) + (A(s, a) - mean(A(s, ·)))
```

Isso garante **identificabilidade**: sem a subtracao, V e A seriam ambiguos (poderiamos adicionar constante a V e subtrair de A sem mudar Q).

A subtracao forca:
```
mean(A(s, ·)) = 0
```

Assim, V(s) representa o valor "medio" do estado.

---

## 5. Vantagens do Dueling DQN

### 5.1 Generalizacao entre Acoes

**Cenario:** Tela de crash iminente no app

| Rede | Comportamento |
|------|---------------|
| OriginalDQN | Precisa aprender Q(s, a) baixo para cada uma das 30 acoes |
| DuelingDQN | Aprende V(s) = -10 uma vez; todas acoes herdam esse valor |

### 5.2 Eficiencia em Estados com Acoes Similares

Quando varias acoes tem valor similar (ex: multiplos botoes inofensivos), o Dueling DQN:
- Aprende V(s) = valor base do estado
- A(s, a) ≈ 0 para acoes similares
- Menos atualizacoes necessarias para convergir

### 5.3 Melhor Estimativa de Valor de Estado

O stream de valor V(s) e treinado com TODAS as transicoes, nao apenas as da acao tomada. Isso resulta em:
- Estimativas mais estaveis
- Menor variancia no treinamento

---

## 6. Quando Usar Cada Uma

### Usar OriginalDQN quando:

- [ ] Prototipagem rapida
- [ ] Recursos computacionais limitados
- [ ] Baseline para comparacao
- [ ] Espaco de acoes pequeno (< 10 acoes)

### Usar DuelingDQN quando:

- [ ] Espaco de acoes grande (30 acoes)
- [ ] Muitos estados tem acoes com valores similares
- [ ] Performance e prioridade sobre simplicidade
- [ ] Treinamento longo (mais episodios)

---

## 7. Impacto no Projeto RLMobTest

### Contexto

- **Espaco de acoes:** 30 acoes possiveis
- **Estados:** Screenshots do app Android
- **Objetivo:** Explorar app e encontrar bugs

### Analise

O DuelingDQN e **recomendado** para este projeto porque:

1. **Muitas acoes similares:** Em uma tela tipica, varios botoes podem ter efeito similar (navegar para outra tela)

2. **Estados "bons" vs "ruins" claros:**
   - Tela de crash = estado ruim (V baixo)
   - Tela com muitos elementos = estado bom para exploracao (V alto)

3. **Eficiencia de amostra:** Com 30 acoes, o DuelingDQN generaliza melhor com menos experiencias

---

## 8. Metricas para Comparacao

Ao comparar as arquiteturas, monitorar:

| Metrica | O que indica |
|---------|--------------|
| Reward medio por episodio | Qualidade da politica |
| Numero de activities descobertas | Capacidade de exploracao |
| Convergencia do loss | Estabilidade do treinamento |
| Tempo por episodio | Eficiencia computacional |

### Experimento Sugerido

```bash
# Treinar com OriginalDQN
python -m rlmobtest train --agent original --episodes 100

# Treinar com DuelingDQN
python -m rlmobtest train --agent improved --episodes 100

# Comparar metricas
```

---

## Referencias

1. **DQN Original:** Mnih, V., et al. (2015). "Human-level control through deep reinforcement learning." Nature.

2. **Dueling DQN:** Wang, Z., et al. (2016). "Dueling Network Architectures for Deep Reinforcement Learning." ICML.

3. **Codigo:** `rlmobtest/__main__.py` linhas 514-575

---

## Anexo: Parametros Estimados

### OriginalDQN

```
Conv1:  3 * 16 * 5 * 5 + 16      = 1,216
BN1:    16 * 2                   = 32
Conv2:  16 * 32 * 5 * 5 + 32     = 12,832
BN2:    32 * 2                   = 64
Conv3:  32 * 32 * 5 * 5 + 32     = 25,632
BN3:    32 * 2                   = 64
Head:   448 * 30 + 30            = 13,470
─────────────────────────────────────────
Total:                           ~53K parametros
```

### DuelingDQN (para input 84x84)

```
Conv1:  3 * 32 * 8 * 8 + 32       = 6,176
Conv2:  32 * 64 * 4 * 4 + 64      = 32,832
Conv3:  64 * 64 * 3 * 3 + 64      = 36,928
Value:  3136 * 512 + 512          = 1,606,144
        512 * 1 + 1               = 513
Advant: 3136 * 512 + 512          = 1,606,144
        512 * 30 + 30             = 15,390
─────────────────────────────────────────────
Total:                            ~3.3M parametros
```

**Nota:** O DuelingDQN tem significativamente mais parametros devido aos streams fully connected maiores.
