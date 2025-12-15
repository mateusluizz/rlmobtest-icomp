# RLMobTest - Reinforcement Learning for Mobile Testing

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-ee4c2c.svg)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Automated Android App Testing usando Deep Reinforcement Learning**

</div>

---

## 📖 Sobre o Projeto

**RLMobTest** é uma ferramenta de teste automatizado para aplicativos Android que utiliza **Deep Q-Networks (DQN)** para explorar inteligentemente a interface do usuário e gerar casos de teste. O sistema aprende a navegar por aplicativos Android de forma autônoma, descobrindo novas funcionalidades, testando fluxos de trabalho e gerando documentação de casos de teste em linguagem natural.

### 🎯 Características Principais

- **🤖 Deep Q-Learning Aprimorado**: Implementação com Double DQN, Dueling Networks e Prioritized Experience Replay (PER)
- **📱 Automação Android**: Integração com UIAutomator2 para controle de dispositivos e emuladores
- **📊 Métricas em Tempo Real**: Monitoramento visual de treinamento com Rich UI
- **💾 Sistema de Checkpoints**: Salvamento automático de progresso e recuperação de treinamento
- **📝 Transcrição Inteligente**: Geração automática de casos de teste em linguagem natural usando LLMs
- **🎨 Interface Visual**: Progresso e estatísticas com visualização colorida no terminal

---

## 🏗️ Arquitetura

```
rlmobtest-mateus/
│
├── agent/                      # Modelos DQN e lógica de agentes RL
│   ├── dqn_model.py           # Redes neurais (Original, Dueling DQN)
│   └── __init__.py
│
├── environment/                # Ambiente Android
│   ├── android_env.py         # Interface com dispositivos Android
│   └── __init__.py
│
├── transcription/              # Sistema de geração de casos de teste
│   ├── transcriber.py         # Transcrição usando LLMs
│   ├── similarity_filter.py   # Filtragem de casos duplicados
│   └── __init__.py
│
├── browser/                    # Automação web (opcional)
│   ├── web_automation.py
│   └── __init__.py
│
├── utils/                      # Utilitários
│   ├── config_reader.py       # Leitor de configurações
│   ├── constants.py           # Constantes do projeto
│   └── __init__.py
│
├── config/                     # Configurações
│   ├── settings.txt           # Configurações principais
│   ├── api_keys.py            # Chaves de API
│   └── requirements.csv       # Requisitos (happy paths)
│
├── data/                       # Dados de treinamento
│   └── few_shot_examples/     # Exemplos para few-shot learning
│
├── output/                     # Saídas geradas
│   ├── test_cases/            # Casos de teste gerados
│   ├── transcriptions/        # Transcrições em NL
│   ├── screenshots/           # Capturas de tela
│   ├── checkpoints/           # Checkpoints do modelo
│   ├── metrics/               # Métricas de treinamento
│   └── logs/                  # Logs de execução
│
├── notebooks/                  # Jupyter notebooks para análise
│   ├── dqn_analysis.ipynb
│   ├── rl_experiments.ipynb
│   └── state_analysis.ipynb
│
├── main.py                     # Script principal
├── requirements.txt            # Dependências Python
└── pyproject.toml             # Configuração do projeto

```

---

## 🚀 Instalação

### Pré-requisitos

- **Python 3.11+**
- **Android SDK** com `adb` configurado no PATH
- **Dispositivo Android** ou **Emulador** (Android 5.0+)
- **CUDA** (opcional, para aceleração GPU)

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/rlmobtest-mateus.git
cd rlmobtest-mateus
```

### 2. Crie um Ambiente Virtual

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

### 3. Instale as Dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o Android

```bash
# Verifique se o ADB está funcionando
adb devices

# Inicie o ATX Agent no dispositivo/emulador
python -m uiautomator2 init
```

### 5. Configure o Projeto

Edite o arquivo [config/settings.txt](config/settings.txt):

```
APK NAME:seu_app.apk
PACKAGE:com.seu.pacote
RESOLUTION:1080x1920
COVERAGE:no
REQUIREMENT:no
TIME:3600
```

---

## 💻 Uso

### Modo Básico (DQN Aprimorado)

```bash
python main.py
```

### Modo Original (DQN Legado)

```bash
python main.py --mode original
```

### Treinar por Tempo Específico

```bash
python main.py --time 600  # 10 minutos
```

### Treinar por Número de Episódios

```bash
python main.py --episodes 50
```

### Opções Disponíveis

```bash
python main.py --help
```

| Argumento | Descrição | Padrão |
|-----------|-----------|--------|
| `--mode` | Modo do agente: `improved` ou `original` | `improved` |
| `--time` | Tempo de treinamento em segundos | Valor de `settings.txt` |
| `--episodes` | Número de episódios | Ilimitado (baseado em tempo) |
| `--checkpoint` | Caminho para checkpoint a continuar | Nenhum |

---

## 📊 Saída e Resultados

### Durante o Treinamento

O sistema exibe em tempo real:

- 🎮 **Número do Episódio** e epsilon (ε)
- 📈 **Recompensas** acumuladas
- 🎯 **Q-values** estimados
- 📉 **Loss** da rede neural
- ⏱️ **Duração** de cada episódio
- 📊 **Progresso** visual com barra

### Após o Treinamento

#### 1. **Checkpoints** (`output/checkpoints/`)
Modelos salvos automaticamente contendo:
- Estado da rede neural
- Otimizador
- Métricas de treinamento
- Número de episódios/steps

#### 2. **Métricas** (`output/metrics/`)
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

#### 3. **Casos de Teste** (`output/test_cases/`)
Scripts de teste gerados automaticamente

#### 4. **Transcrições** (`output/transcriptions/`)
Casos de teste em linguagem natural usando LLM

#### 5. **Screenshots** (`output/screenshots/`)
Capturas de tela de cada ação executada

---

## 🧠 Algoritmos Implementados

### DQN Original
- Rede convolucional padrão
- Experience Replay básico
- Epsilon-greedy exploration

### DQN Aprimorado ✨
- **Double DQN**: Reduz superestimação de Q-values
- **Dueling Networks**: Separa Value e Advantage streams
- **Target Network**: Estabiliza o treinamento
- **Prioritized Experience Replay (PER)**: Prioriza experiências importantes
- **Gradient Clipping**: Previne explosão de gradientes
- **Soft Updates**: Atualização suave da target network

---

## 📐 Sistema de Recompensas

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

## 🔧 Configuração Avançada

### Ajustar Hiperparâmetros

Edite os valores em [main.py](main.py:420-430):

```python
# Hiperparâmetros do DQN Aprimorado
self.batch_size = 128
self.gamma = 0.99           # Fator de desconto
self.eps_start = 1.0        # Epsilon inicial
self.eps_end = 0.01         # Epsilon final
self.eps_decay = 10000      # Taxa de decaimento
self.target_update = 1000   # Frequência de atualização da target network
```

### Usar GPU

O sistema detecta automaticamente CUDA:

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

Para forçar CPU:
```python
device = torch.device("cpu")
```

---

## 📚 Dependências Principais

| Biblioteca | Versão | Propósito |
|------------|--------|-----------|
| **PyTorch** | 2.9+ | Deep Learning framework |
| **NumPy** | - | Computação numérica |
| **UIAutomator2** | - | Automação Android |
| **Rich** | - | Interface visual no terminal |
| **Langchain-Ollama** | 1.0+ | Integração com LLMs para transcrição |
| **Pandas** | 2.3+ | Manipulação de dados |
| **Matplotlib** | 3.10+ | Visualização de métricas |

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Add MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

## 📧 Contato

**Mateus Luiz** - [@mateusluizz](https://github.com/mateusluizz)

**Link do Projeto**: [https://github.com/mateusluizz/rlmobtest-mateus](https://github.com/mateusluizz/rlmobtest-mateus)

---

## 🙏 Agradecimentos

- Baseado no trabalho original de **Eliane Collins**
- Inspirado em pesquisas de RL aplicado a testes de software
- Comunidade PyTorch e OpenAI Gym

---

## 📖 Referências

- [Deep Q-Learning (DQN) - DeepMind](https://www.nature.com/articles/nature14236)
- [Double DQN](https://arxiv.org/abs/1509.06461)
- [Dueling Network Architectures](https://arxiv.org/abs/1511.06581)
- [Prioritized Experience Replay](https://arxiv.org/abs/1511.05952)

---

<div align="center">

**⭐ Se este projeto foi útil, considere dar uma estrela!**

</div>
