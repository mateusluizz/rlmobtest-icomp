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

- **Deep Q-Learning Aprimorado**: Double DQN, Dueling Networks e Prioritized Experience Replay (PER)
- **Automação Android**: Integração com UIAutomator2 para controle de dispositivos e emuladores
- **JaCoCo Code Coverage**: Instrumentação automática, coleta de cobertura em tempo real e relatórios HTML/CSV (suporte a AGP 1.x até 8.x)
- **Build Agent Autônomo**: Compila APKs com JaCoCo automaticamente, compatível com projetos Android antigos e modernos
- **Pipeline Completo**: Exploração → Requisitos → Treino Guiado → Transcrição, em um único comando
- **Transcrição Inteligente**: Geração automática de casos de teste ISO/IEC/IEEE 29119-3 usando CrewAI + LLMs
- **Métricas em Tempo Real**: Monitoramento visual de treinamento com Rich UI
- **CLI Moderna**: Interface de linha de comando com Typer

---

## Arquitetura

```
rlmobtest-icomp/
├── rlmobtest/                        # Pacote principal
│   ├── cli/                          # Comandos CLI (Typer)
│   │   ├── check.py                  # Pre-validação de Java/Gradle/SDK
│   │   ├── setup.py                  # Build APK + classfiles + jacococli
│   │   ├── pipeline.py               # Pipeline completo (4 etapas)
│   │   ├── train.py                  # Treino do agente DQN
│   │   ├── report.py                 # Geração de relatório HTML
│   │   ├── clean.py                  # Limpeza de output
│   │   └── info.py                   # Info do ambiente
│   │
│   ├── models/                       # Redes neurais DQN
│   │   └── dqn_model.py              # Original e Dueling DQN
│   │
│   ├── android/                      # Ambiente Android
│   │   └── android_env.py            # Interface com dispositivos (UIAutomator2)
│   │
│   ├── training/                     # Lógica de treinamento RL
│   │   ├── loop.py                   # Loop de treino principal
│   │   ├── agents.py                 # Agentes DQN (Original + Improved)
│   │   ├── reward.py                 # Função de recompensa
│   │   ├── memory.py                 # Experience Replay (PER)
│   │   ├── report.py                 # Geração de report.html
│   │   └── generate_requirements.py  # Extração de requisitos via LLM
│   │
│   ├── transcription/                # Transcrição de casos de teste
│   │   ├── crew_transcriber/         # Backend CrewAI (padrão)
│   │   │   ├── core.py               # Agente, Task, Crew
│   │   │   ├── discovery.py          # Descoberta de datas no output
│   │   │   └── multimodal.py         # Suporte multimodal
│   │   ├── transcriber.py            # Backend LangChain (alternativo)
│   │   ├── similarity_filter.py      # Filtragem de duplicados (>90%)
│   │   └── prompts.py                # System prompt ISO 29119-3
│   │
│   ├── utils/                        # Utilitários
│   │   ├── jacoco_setup.py           # Instrumentação JaCoCo e build
│   │   ├── jacoco.py                 # Processamento de cobertura (CSV/HTML)
│   │   ├── build_agent.py            # Build agent autônomo (fallback)
│   │   ├── config_reader.py          # Parser de configurações (Pydantic)
│   │   └── app_context.py            # Extração de contexto da app para LLM
│   │
│   ├── constants/                    # Constantes e paths
│   │   ├── paths.py                  # Caminhos do projeto
│   │   └── actions.py                # Ações do agente
│   │
│   └── config/                       # Configurações
│       └── settings.json             # Configurações das apps
│
├── inputs/                           # Artefatos de entrada
│   ├── apks/                         # APKs instrumentados
│   ├── classfiles/                   # Classes compiladas por pacote
│   ├── source_codes/                 # Código-fonte das apps
│   └── tools/                        # jacococli.jar + legacy Jacoco tools
│
├── output/                           # Resultados gerados
│   └── {package}/{mode}/{Y}/{M}/{D}/
│       ├── test_cases/               # Logs brutos de interação
│       ├── transcriptions/           # Casos ISO 29119-3 (CrewAI)
│       ├── coverage/                 # Dados JaCoCo (.ec + HTML)
│       ├── metrics/                  # Métricas JSON do treinamento
│       ├── checkpoints/              # Checkpoints do modelo DQN
│       ├── requirements.csv          # Requisitos extraídos via LLM
│       └── report.html               # Relatório HTML consolidado
│
├── docs/                             # Documentação
│   ├── architecture.drawio           # Fluxograma da arquitetura
│   └── transcription_flow.drawio     # Fluxo de transcrição
│
├── .claude/commands/                 # Slash commands do Claude Code
│   └── setup-build.md               # Build agent autônomo
│
├── pyproject.toml                    # Configuração do projeto
├── CLAUDE.md                         # Instruções para Claude Code
└── README.md
```

---

## Instalação

### Pré-requisitos

- **Python 3.11+**
- **Android SDK** com `adb` configurado no PATH
- **Dispositivo Android** ou **Emulador** (Android 7.0+, targetSdk >= 24)
- **Java** (JDK 8+ para build, JDK 17+ para sdkmanager)
- **CUDA** (opcional, para aceleração GPU)
- **Ollama** (para transcrição e geração de requisitos)

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
        "source_code": "seu_app_src.tar.gz",
        "is_coverage": true,
        "is_req": false,
        "time": 3600,
        "time_exploration": 3600,
        "time_guided": 3600,
        "episodes": 20
    }
]
```

### 5. Valide o Ambiente (opcional)

```bash
rlmobtest check
```

---

## Uso

### Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `rlmobtest check` | Pré-validar Java, Gradle, SDK e dependências |
| `rlmobtest setup` | Compilar APKs + copiar classfiles + baixar jacococli |
| `rlmobtest pipeline` | Pipeline completo (exploração → requisitos → guiado → transcrição) |
| `rlmobtest train` | Treinar agente DQN em uma ou mais apps |
| `rlmobtest report` | Gerar relatório HTML a partir de dados existentes |
| `rlmobtest clean` | Limpar pastas de output |
| `rlmobtest info` | Informações do ambiente |

### Pipeline Completo

```bash
# Executa todas as etapas para todos os apps configurados
rlmobtest pipeline

# App específico com modelo LLM customizado
rlmobtest pipeline --app com.seu.pacote -l gemma3:12b

# Pular exploração, executar apenas requisitos + guiado + transcrição
rlmobtest pipeline --skip-exploration

# Somente transcrição (todas as datas)
rlmobtest pipeline --only-transcribe --all-dates
```

**Etapas do pipeline:**

| Etapa | Descrição |
|-------|-----------|
| **Step 0** | Build & Setup (APK + JaCoCo) — automático se `is_coverage` e `source_code` |
| **Step 1** | Exploração — DQN aprende via heurísticas |
| **Step 2** | Requirements — Extrai requisitos dos test_cases via LLM |
| **Step 3** | Treino Guiado — DQN usa happy path dos requisitos |
| **Step 4** | Transcrição — CrewAI gera casos ISO 29119-3 |

### Setup & Build

```bash
# Setup com build agent autônomo (padrão)
rlmobtest setup

# Setup sem build agent (Gradle direto)
rlmobtest setup --no-agent

# App específico, forçar rebuild
rlmobtest setup --app com.seu.pacote --force
```

### Treinamento

```bash
# Treinar todos os apps do config
rlmobtest train

# Treinar por tempo específico (10 minutos)
rlmobtest train --time 600

# Treinar por número de episódios, modo original
rlmobtest train -m original --episodes 50

# Continuar de um checkpoint
rlmobtest train --app com.seu.pacote -c output/.../checkpoint.pt
```

---

## JaCoCo Code Coverage

O RLMobTest integra JaCoCo para medir cobertura de código durante os testes:

- **Instrumentação automática** via `rlmobtest setup`
- **Coleta em tempo real** durante o treinamento (broadcast → CoverageReceiver → .ec files)
- **Relatórios CSV e HTML** com cobertura por linha, branch e método
- **Suporte a projetos legados** (AGP 1.x-2.x) via fallback JaCoCo 0.7.4

```bash
# Setup completo (build + instrumentação + jacococli)
rlmobtest setup --app com.seu.pacote

# Gerar relatório com métricas JaCoCo
rlmobtest report --app com.seu.pacote --all-dates
```

Para detalhes, veja [docs/jacoco_setup.md](docs/jacoco_setup.md).

---

## Saída e Resultados

### Relatório HTML (`report.html`)

Gerado em `output/{pkg}/{mode}/{Y}/{M}/{D}/report.html`, inclui:

- **Training Overview**: episódios, passos, tempo, duração média
- **Rewards**: recompensa média, máxima e mínima
- **Activity Coverage**: % de activities requeridas descobertas
- **Requirements Coverage**: % de requisitos cobertos pelas ações
- **Transcription Coverage**: % de test cases transcritos (CrewAI)
- **JaCoCo Coverage**: Line, Branch e Method coverage com link para relatório detalhado

### Métricas JSON (`metrics/`)

```json
{
  "summary": {
    "total_episodes": 14,
    "total_steps": 1358,
    "avg_reward_last_10": 413.9,
    "training_time": "01:00:01"
  },
  "episode_rewards": [413, 407, 413, ...],
  "episode_losses": [3.65, 1.88, ...]
}
```

### Casos de Teste Transcritos (`transcriptions/`)

Formato ISO/IEC/IEEE 29119-3 com: Test Case ID, Title, Description, Priority, Preconditions, Test Steps (tabela), Postconditions.

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

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [docs/cli_commands.md](docs/cli_commands.md) | Referência completa de comandos CLI |
| [docs/jacoco_setup.md](docs/jacoco_setup.md) | Configuração do JaCoCo (automática e manual) |
| [docs/report_generation.md](docs/report_generation.md) | Como o report.html é gerado |
| [docs/DQN_MODEL_EXPLICACAO.md](docs/DQN_MODEL_EXPLICACAO.md) | Explicação detalhada do DQN |
| [docs/coverage_metrics.md](docs/coverage_metrics.md) | Métricas de cobertura de código |
| [docs/architecture.drawio](docs/architecture.drawio) | Fluxograma da arquitetura |
| [docs/transcription_flow.drawio](docs/transcription_flow.drawio) | Fluxo de transcrição de casos de teste |

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
