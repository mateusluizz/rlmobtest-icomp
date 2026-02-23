# RLMobTest - Reinforcement Learning for Mobile Testing

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-ee4c2c.svg)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Automated Android App Testing usando Deep Reinforcement Learning**

</div>

---

## Sobre o Projeto

**RLMobTest** é uma ferramenta de teste automatizado para aplicativos Android que utiliza **Deep Q-Networks (DQN)** para explorar inteligentemente a interface do usuário e gerar casos de teste. O sistema aprende a navegar por aplicativos Android de forma autônoma, descobrindo novas funcionalidades, testando fluxos de trabalho e gerando documentação de casos de teste em linguagem natural.

### Características Principais

- **🤖 Deep Q-Learning Aprimorado**: Implementação com Double DQN, Dueling Networks e Prioritized Experience Replay (PER)
- **📱 Automação Android**: Integração com UIAutomator2 para controle de dispositivos e emuladores
- **📊 Métricas em Tempo Real**: Monitoramento visual de treinamento com Rich UI
- **💾 Sistema de Checkpoints**: Salvamento automático de progresso e recuperação de treinamento
- **📝 Transcrição Inteligente**: Geração automática de casos de teste em linguagem natural usando CrewAI + LLMs
- **🎨 CLI Moderna**: Interface de linha de comando com Typer

---

## Arquitetura

```
rlmobtest-icomp/
│
├── rlmobtest/                     # Pacote principal
│   ├── __init__.py
│   ├── __main__.py               # Entry point
│   ├── cli.py                    # CLI com Typer
│   │
│   ├── models/                   # Modelos DQN e lógica de agentes RL
│   │   ├── dqn_model.py          # Redes neurais (Original, Dueling DQN)
│   │   └── __init__.py
│   │
│   ├── android/                  # Ambiente Android
│   │   ├── android_env.py        # Interface com dispositivos Android
│   │   └── __init__.py
│   │
│   ├── transcription/            # Sistema de geração de casos de teste
│   │   ├── transcriber.py        # Transcrição usando LLMs
│   │   ├── crew_transcriber.py   # Transcrição com CrewAI
│   │   ├── similarity_filter.py  # Filtragem de casos duplicados
│   │   └── __init__.py
│   │
│   ├── browser/                  # Automação web (opcional)
│   │   ├── web_automation.py
│   │   └── __init__.py
│   │
│   ├── utils/                    # Utilitários
│   │   ├── config_reader.py      # Leitor de configurações (Pydantic)
│   │   └── __init__.py
│   │
│   ├── constants/                # Constantes e paths
│   │   ├── paths.py              # Caminhos do projeto
│   │   └── __init__.py
│   │
│   ├── config/                   # Configurações
│   │   ├── settings.json         # Configurações principais
│   │   └── requirements.csv      # Requisitos (happy paths)
│   │
│   ├── data/                     # Dados de treinamento
│   │   └── few_shot_examples/    # Exemplos para few-shot learning
│   │
│   └── output/                   # Saídas geradas
│       ├── test_cases/           # Casos de teste gerados
│       ├── transcriptions/       # Transcrições em NL
│       ├── screenshots/          # Capturas de tela
│       ├── checkpoints/          # Checkpoints do modelo
│       ├── metrics/              # Métricas de treinamento
│       └── logs/                 # Logs de execução
│
├── docs/                         # Documentação
│   └── DQN_MODEL_EXPLICACAO.md   # Explicação detalhada do DQN
│
├── pyproject.toml                # Configuração do projeto e dependências
└── README.md
```

---

## Instalação

### Pré-requisitos

- **Python 3.11+**
- **Android SDK** com `adb` configurado no PATH
- **Dispositivo Android** ou **Emulador** (Android 5.0+)
- **CUDA** (opcional, para aceleração GPU)

### 1. Clone o Repositório

```bash
git clone https://github.com/mateusluizz/rlmobtest-icomp.git
cd rlmobtest-icomp
```

### 2. Instale as Dependências

**Com uv (recomendado):**

```bash
uv sync
```

**Ou com pip:**

```bash
pip install -e .
```

### 3. Configure o Android

```bash
# Verifique se o ADB está funcionando
adb devices

# Inicie o ATX Agent no dispositivo/emulador
python -m uiautomator2 init
```

### 4. Configure o Projeto

Edite o arquivo `rlmobtest/config/settings.json`:

```json
[
    {
        "apk_name": "seu_app.apk",
        "package_name": "com.seu.pacote",
        "resolution": "1080x1920",
        "is_coverage": false,
        "is_req": false,
        "time": 3600
    }
]
```

---

## Uso

### CLI com Typer

O RLMobTest utiliza uma CLI moderna com Typer. Após a instalação, o comando `rlmobtest` fica disponível.

### Comandos Disponíveis

```bash
# Ver ajuda geral
rlmobtest --help

# Ver informações do ambiente
rlmobtest info

# Treinar o agente
rlmobtest train --help
```

### Treinamento

```bash
# Usa configurações do settings.json
rlmobtest train

# Treinar por tempo específico (10 minutos)
rlmobtest train --time 600
rlmobtest train -t 600

# Treinar por número de episódios
rlmobtest train --episodes 50
rlmobtest train -e 50

# Usar modo DQN original
rlmobtest train --mode original
rlmobtest train -m original

# Continuar de um checkpoint
rlmobtest train --checkpoint path/to/checkpoint.pt
rlmobtest train -c path/to/checkpoint.pt
```

### Opções do Comando `train`

| Argumento | Alias | Descrição | Padrão |
|-----------|-------|-----------|--------|
| `--mode` | `-m` | Modo do agente: `improved` ou `original` | `improved` |
| `--time` | `-t` | Tempo de treinamento em segundos | Valor de `settings.json` |
| `--episodes` | `-e` | Número de episódios | Ilimitado (baseado em tempo) |
| `--checkpoint` | `-c` | Caminho para checkpoint a continuar | Nenhum |

> **Nota:** `--time` e `--episodes` são mutuamente exclusivos.

### Executando como Módulo

```bash
# Alternativa ao comando rlmobtest
python -m rlmobtest train
```

---

## Saída e Resultados

### Durante o Treinamento

O sistema exibe em tempo real:

-🎮 **Número do Episódio** e epsilon
-📈 **Recompensas** acumuladas
-🎯 **Q-values** estimados
-📉 **Loss** da rede neural
-⏱️ **Duração** de cada episódio
-📊 **Progresso** visual com barra

### Após o Treinamento

#### 1. **Checkpoints** (`rlmobtest/output/checkpoints/`)
Modelos salvos automaticamente contendo:
- Estado da rede neural
- Otimizador
- Métricas de treinamento
- Número de episódios/steps

#### 2. **Métricas** (`rlmobtest/output/metrics/`)
JSON com dados detalhados:
```json
{
  "summary": {
    "total_episodes": 50,
    "total_steps": 1523,
    "avg_reward_last_10": 45.2,
    "training_time": "01:23:45"
  },
  "episode_rewards": [10, 15, 23, ...],
  "episode_losses": [0.45, 0.32, ...]
}
```

#### 3. **Casos de Teste** (`rlmobtest/output/test_cases/`)
Scripts de teste gerados automaticamente

#### 4. **Transcrições** (`rlmobtest/output/transcriptions/`)
Casos de teste em linguagem natural usando LLM

#### 5. **Screenshots** (`rlmobtest/output/screenshots/`)
Capturas de tela de cada ação executada

---

## Algoritmos Implementados

### DQN Original
- Rede convolucional padrão
- Experience Replay básico
- Epsilon-greedy exploration

### DQN Aprimorado
- **Double DQN**: Reduz superestimação de Q-values
- **Dueling Networks**: Separa Value e Advantage streams
- **Target Network**: Estabiliza o treinamento
- **Prioritized Experience Replay (PER)**: Prioriza experiências importantes
- **Gradient Clipping**: Previne explosão de gradientes
- **Soft Updates**: Atualização suave da target network

Para uma explicação detalhada do modelo DQN, veja [docs/DQN_MODEL_EXPLICACAO.md](docs/DQN_MODEL_EXPLICACAO.md).

---

## Sistema de Recompensas

| Evento | Recompensa |
|--------|-----------|
| Nova activity descoberta | +10 |
| Mudança de activity válida | +5 |
| Happy path executado | Variável (baseado em requisitos) |
| Ação repetida | -2 |
| Saída do app / Voltar ao home | -5 |
| Crash detectado | -5 |
| Ação válida | +1 |

---

## Dependências Principais

| Biblioteca | Versão | Propósito |
|------------|--------|-----------|
| **PyTorch** | 2.9+ | Deep Learning framework |
| **Typer** | 0.15+ | CLI moderna |
| **UIAutomator2** | 3.5+ | Automação Android |
| **Rich** | - | Interface visual no terminal |
| **Pydantic** | - | Validação de configurações |
| **CrewAI** | 1.9+ | Agentes de IA para transcrição |
| **Langchain-Ollama** | 1.0+ | Integração com LLMs locais |
| **Pandas** | 2.3+ | Manipulação de dados |
| **Matplotlib** | 3.10+ | Visualização de métricas |

---

## Contribuindo

Contribuições são bem-vindas! Por favor:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Add MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

## Contato

**Mateus Luiz** - [@mateusluizz](https://github.com/mateusluizz)

**Link do Projeto**: [https://github.com/mateusluizz/rlmobtest-icomp](https://github.com/mateusluizz/rlmobtest-icomp)

---

## Agradecimentos

- Baseado no trabalho original de **Eliane Collins**
- Inspirado em pesquisas de RL aplicado a testes de software
- Comunidade PyTorch e OpenAI Gym

---

## Referências

- [Deep Q-Learning (DQN) - DeepMind](https://www.nature.com/articles/nature14236)
- [Double DQN](https://arxiv.org/abs/1509.06461)
- [Dueling Network Architectures](https://arxiv.org/abs/1511.06581)
- [Prioritized Experience Replay](https://arxiv.org/abs/1511.05952)

---

<div align="center">

**Se este projeto foi útil, considere dar uma estrela!**

</div>
