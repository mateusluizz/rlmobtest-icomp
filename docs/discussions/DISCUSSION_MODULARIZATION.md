# Discussao: Modularizacao do __main__.py

**Data:** 2026-02-01
**Status:** Em discussao
**Arquivo alvo:** `rlmobtest/__main__.py` (1287 linhas)

---

## Situacao Atual

O arquivo `__main__.py` concentra toda a logica do treinamento RL em um unico arquivo monolitico:

### Classes/Funcoes em __main__.py

| Linha | Componente | Descricao |
|-------|-----------|-----------|
| 60 | `setup_logging()` | Configuracao de logging |
| 98 | `TrainingMetrics` | Metricas e graficos de treinamento |
| 378 | `ModelCheckpoint` | Gerenciamento de checkpoints |
| 433 | `ReplayMemory` | Buffer de experiencia simples |
| 454 | `PrioritizedReplayMemory` | Buffer com priorizacao |
| 514 | `OriginalDQN` | Rede neural DQN antiga |
| 535 | `DuelingDQN` | Rede neural Dueling DQN moderna |
| 583 | `OriginalAgent` | Agente DQN antigo |
| 657 | `ImprovedAgent` | Agente melhorado (Dueling + PER) |
| 787 | `calculate_reward()` | Calculo de recompensa |
| 840 | `TrainingProgress` | Barra de progresso (Rich) |
| 916 | `run()` | Loop principal de treinamento |
| 1279 | `main()` | Entry point CLI |

### Modulos Existentes (Subutilizados)

```
rlmobtest/
├── models/
│   └── dqn_model.py       # DQN antigo (duplicado no __main__)
├── android/
│   └── android_env.py     # Ambiente Android (OK)
├── constants/
│   └── paths.py           # OutputPaths (parcialmente usado)
├── utils/
│   └── config_reader.py   # Leitor de config
├── transcription/
│   ├── transcriber.py
│   ├── crew_transcriber.py
│   └── similarity_filter.py
└── __main__.py            # TUDO MAIS ESTA AQUI
```

---

## Proposta de Modularizacao

### Nova Estrutura Proposta

```
rlmobtest/
├── models/
│   ├── __init__.py
│   ├── networks.py        # OriginalDQN, DuelingDQN
│   └── replay_memory.py   # ReplayMemory, PrioritizedReplayMemory
├── agents/
│   ├── __init__.py
│   ├── base_agent.py      # Interface comum
│   ├── original_agent.py  # OriginalAgent
│   └── improved_agent.py  # ImprovedAgent
├── training/
│   ├── __init__.py
│   ├── metrics.py         # TrainingMetrics
│   ├── checkpoint.py      # ModelCheckpoint
│   ├── progress.py        # TrainingProgress
│   ├── rewards.py         # calculate_reward()
│   └── trainer.py         # Loop de treinamento (run())
├── android/
│   └── android_env.py     # (ja existe)
├── constants/
│   └── paths.py           # (ja existe)
├── utils/
│   ├── __init__.py
│   ├── config_reader.py   # (ja existe)
│   └── logging.py         # setup_logging()
├── transcription/
│   └── ...                # (ja existe)
├── cli.py                 # Comandos Typer
└── __main__.py            # Apenas imports e main()
```

---

## Mapeamento Detalhado

### 1. `rlmobtest/models/networks.py`

**Mover de __main__.py:**
- `OriginalDQN` (linhas 514-533)
- `DuelingDQN` (linhas 535-580)

**Acao:** Substituir versao antiga em `dqn_model.py`

```python
# networks.py
import torch
import torch.nn as nn

class OriginalDQN(nn.Module):
    ...

class DuelingDQN(nn.Module):
    ...
```

### 2. `rlmobtest/models/replay_memory.py`

**Mover de __main__.py:**
- `ReplayMemory` (linhas 433-452)
- `PrioritizedReplayMemory` (linhas 454-511)

**Acao:** Substituir versao em `dqn_model.py`

```python
# replay_memory.py
import random
import numpy as np

class ReplayMemory:
    ...

class PrioritizedReplayMemory:
    ...
```

### 3. `rlmobtest/agents/improved_agent.py`

**Mover de __main__.py:**
- `ImprovedAgent` (linhas 657-785)

```python
# improved_agent.py
from rlmobtest.models.networks import DuelingDQN
from rlmobtest.models.replay_memory import PrioritizedReplayMemory

class ImprovedAgent:
    ...
```

### 4. `rlmobtest/training/metrics.py`

**Mover de __main__.py:**
- `TrainingMetrics` (linhas 98-376)

```python
# metrics.py
import json
import matplotlib.pyplot as plt
from rich.console import Console

class TrainingMetrics:
    ...
```

### 5. `rlmobtest/training/checkpoint.py`

**Mover de __main__.py:**
- `ModelCheckpoint` (linhas 378-430)

```python
# checkpoint.py
import torch
from pathlib import Path

class ModelCheckpoint:
    ...
```

### 6. `rlmobtest/training/rewards.py`

**Mover de __main__.py:**
- `calculate_reward()` (linhas 787-838)

```python
# rewards.py
import torch

def calculate_reward(
    current_action,
    previous_action,
    activity,
    previous_activity,
    activities,
    crash,
    req_enabled,
    env,
    actions,
):
    ...
```

### 7. `rlmobtest/training/trainer.py`

**Mover de __main__.py:**
- `run()` (linhas 916-1277) - Refatorar para classe `Trainer`

```python
# trainer.py
from rlmobtest.training.metrics import TrainingMetrics
from rlmobtest.training.checkpoint import ModelCheckpoint
from rlmobtest.training.progress import TrainingProgress
from rlmobtest.training.rewards import calculate_reward

class Trainer:
    def __init__(self, agent, env, config):
        ...

    def run(self, max_time=None, max_episodes=None):
        ...
```

### 8. `rlmobtest/__main__.py` (Simplificado)

```python
# __main__.py (~50 linhas)
"""Entry point para rlmobtest."""

from rlmobtest.cli import app

if __name__ == "__main__":
    app()
```

---

## Codigo Duplicado Identificado

| Local 1 | Local 2 | Componente |
|---------|---------|------------|
| `__main__.py:433` | `models/dqn_model.py:43` | `ReplayMemory` |
| `__main__.py:514` | `models/dqn_model.py:24` | Arquitetura DQN |
| Constantes CUDA | Multiplos arquivos | `device`, `FloatTensor`, etc. |

**Recomendacao:** Centralizar em `rlmobtest/utils/torch_utils.py`:

```python
# torch_utils.py
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FloatTensor = torch.cuda.FloatTensor if device.type == "cuda" else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if device.type == "cuda" else torch.LongTensor
```

---

## Beneficios da Modularizacao

1. **Manutencao:** Arquivos menores e focados sao mais faceis de manter
2. **Testabilidade:** Componentes isolados podem ser testados unitariamente
3. **Reutilizacao:** Agentes e modelos podem ser importados separadamente
4. **Colaboracao:** Multiplas pessoas podem trabalhar em modulos diferentes
5. **Legibilidade:** Estrutura clara facilita onboarding de novos desenvolvedores

---

## Riscos e Consideracoes

1. **Imports circulares:** Cuidado ao separar componentes interdependentes
2. **Retrocompatibilidade:** Scripts existentes que importam de `__main__` quebrarao
3. **Tempo de refatoracao:** Estimativa de mudancas significativas
4. **Testes:** Necessario criar/atualizar testes apos refatoracao

---

## Estrategia de Migracao Sugerida

### Fase 1: Preparacao
- [ ] Criar testes para comportamento atual
- [ ] Documentar interfaces publicas

### Fase 2: Extracao (ordem sugerida)
1. [ ] `utils/torch_utils.py` - Constantes compartilhadas
2. [ ] `models/networks.py` - Redes neurais
3. [ ] `models/replay_memory.py` - Buffers de experiencia
4. [ ] `training/rewards.py` - Funcao de recompensa
5. [ ] `training/metrics.py` - Metricas
6. [ ] `training/checkpoint.py` - Checkpoints
7. [ ] `training/progress.py` - Barra de progresso
8. [ ] `agents/` - Agentes
9. [ ] `training/trainer.py` - Loop principal

### Fase 3: Limpeza
- [ ] Remover codigo duplicado de `dqn_model.py`
- [ ] Atualizar imports em todos os arquivos
- [ ] Atualizar `__main__.py` para ser minimalista

### Fase 4: Validacao
- [ ] Rodar testes
- [ ] Validar treinamento end-to-end
- [ ] Verificar carregamento de checkpoints antigos

---

## Proximos Passos

- [ ] Discutir proposta com equipe
- [ ] Priorizar modulos para migracao
- [ ] Decidir sobre retrocompatibilidade
- [ ] Definir timeline

---

## Referencias

- Arquivo atual: `rlmobtest/__main__.py` (1287 linhas)
- Modulos existentes: `rlmobtest/models/`, `rlmobtest/android/`, etc.
