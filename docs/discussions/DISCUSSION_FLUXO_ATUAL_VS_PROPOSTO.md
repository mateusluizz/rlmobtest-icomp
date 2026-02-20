# Fluxo Atual vs. Fluxo Proposto — DRL-MOBTEST

**Data:** 2026-02-19
**Referência:** Conversa de análise do RL (`conversa_analise_rl_19022026.md`)
**Checkpoint analisado:** `output/protect.budgetwatch/original/2026/02/12/checkpoints/checkpoint_ep12_20260212_165931.pt`

---

## Sumário

| # | Seção |
|---|---|
| 1 | [Fluxo Atual](#1-fluxo-atual) |
| 2 | [Limitações do Fluxo Atual](#2-limitações-do-fluxo-atual) |
| 3 | [Fluxo Proposto](#3-fluxo-proposto) |
| 4 | [Descrição das Fases Propostas](#4-descrição-das-fases-propostas) |
| 5 | [Comparativo Final](#5-comparativo-final) |

---

## 1. Fluxo Atual

### Descrição das Etapas

**Etapa 1 — Instalação do APK**
O APK é instalado no dispositivo via `adb install`. Nenhuma análise é feita antes da execução.
O agente não tem nenhum conhecimento sobre o app: nem quais telas existem, nem quais elementos esperar.

**Etapa 2 — Inicialização do agente RL**
O agente (OriginalDQN ou DuelingDQN) é criado com pesos aleatórios.
A replay memory começa completamente vazia. Não há warm-up nem pré-exploração.

**Etapa 3 — Loop de treino (episódios)**
A cada episódio:
- `env.reset()` força o encerramento e reabertura do app
- O ambiente captura screenshot (38×38 px) e o XML hierarchy da tela atual
- O XML é usado apenas para montar a lista de ações disponíveis naquele momento e depois **é descartado**
- O agente escolhe uma ação via política ε-greedy
- A recompensa é baseada em quantidade de navegação (mudança de tela, ação válida)
- A transição é armazenada na replay memory
- O agente otimiza os pesos via backpropagation

**Etapa 4 — Log de ações brutas**
Cada ação executada é registrada em log sem contexto semântico.
Exemplo real do log:
```
Clicked android.widget.ImageView  More options  bounds:[1107,139][1220,274]
Clicked android.widget.LinearLayout    bounds:[658,139][1209,274]
Got Error
Go to next activity: TransactionViewActivity
```

**Etapa 5 — Transcrição via CrewAI**
O log bruto é enviado ao CrewAI, que gera um test case textual.
O CrewAI recebe apenas o log — sem XML, sem screenshot, sem contexto funcional.

**Etapa 6 — Test case sem oráculo**
Saída atual do CrewAI:
```
Test Steps:
1- Clicked on an ImageButton to navigate up.
2- Got an error.
3- Clicked on multiple Linelayouts.

Result:
The test continued and clicked on multiple Linelayouts,
but no specific actions were taken or expected.
```
Não há pré-condição, resultado esperado nem condição de sucesso/falha verificável.

---

### Diagrama — Fluxo Atual

```
╔══════════════════════════════════════════════════════════════════╗
║                        FLUXO ATUAL                               ║
╚══════════════════════════════════════════════════════════════════╝

                            APK
                             │
                             ▼
                ┌────────────────────────┐
                │    Instala no device   │
                │     (adb install)      │
                │                        │
                │  Nenhuma análise prévia│
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Agente RL             │
                │  • pesos aleatórios    │
                │  • replay memory vazia │
                │  • nenhum conhecimento │
                └────────────┬───────────┘
                             │
                ┌────────────▼───────────┐
                │     env.reset()        │
                │  Abre app, captura:    │
                │  • screenshot 38×38 px │
                │  • XML hierarchy       │
                └────────────┬───────────┘
                             │
             ┌───────────────▼──────────────┐
             │  XML → lista de ações        │
             │  (índices numéricos)         │
             │                              │
             │  XML descartado após isso ✗  │
             └───────────────┬──────────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  DQN escolhe ação      │
                │  via política ε-greedy │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Executa ação no device│
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Função de recompensa  │
                │  por navegação:        │
                │  +10 nova activity     │
                │  +5  mudança de tela   │
                │  +1  ação válida       │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Log bruto de ações    │◄──────────────────┐
                │  (sem semântica)       │                   │
                └────────────┬───────────┘     mais steps   │
                             │                e episódios   │
                             └───────────────────────────────┘
                             │
                    treino concluído
                             │
                             ▼
                ┌────────────────────────┐
                │  CrewAI Transcriber    │
                │  Input: só o log bruto │
                └────────────┬───────────┘
                             │
                             ▼
                ┌────────────────────────┐
                │  Test case             │
                │  • sem pré-condição    │
                │  • sem resultado       │
                │    esperado            │
                │  • sem oráculo         │
                └────────────────────────┘


  FASES QUE NÃO EXISTEM NO FLUXO ATUAL:
  ┌──────────────────────────────────────────────────────────┐
  │  Análise estática do APK   → ✗  não existe               │
  │  Leitura do manifesto      → ✗  não existe               │
  │  Warm-up da replay memory  → ✗  não existe               │
  │  Crawling inicial do app   → ✗  não existe               │
  │  XML como contexto         → ✗  descartado imediatamente │
  │  Screenshot no CrewAI      → ✗  capturado mas não usado  │
  └──────────────────────────────────────────────────────────┘
```

---

## 2. Limitações do Fluxo Atual

| Limitação | Impacto |
|---|---|
| XML descartado após gerar ações | Toda semântica da UI é perdida; CrewAI não sabe o que cada tela significa |
| Replay memory começa vazia | Primeiros episódios são puramente aleatórios; aprendizado lento |
| Nenhuma análise prévia do app | Agente não sabe quais telas existem antes de encontrá-las por acaso |
| Recompensa por navegação, não por funcionalidade | Agente aprende a navegar rápido entre telas, não a testar funcionalidades |
| `is_req: false` por padrão | Sistema de requisitos existe mas nunca é ativado |
| Screenshot 38×38 px | Resolução elimina todo texto e semântica visual |
| CrewAI recebe só log bruto | Test cases sem oráculo, sem pré-condição, sem resultado esperado |
| `requirements.csv` preenchido manualmente | Trabalho humano repetitivo; raramente mantido atualizado |

**Problema central em uma frase:**
O sistema documenta *o que aconteceu*, não *o que deveria acontecer*.

---

## 3. Fluxo Proposto

### Visão Geral das Fases

```
Fase 0a  →  Leitura do manifesto Android (sem executar o app)
Fase 0b  →  Crawling semântico guiado por LLM
Fase 0c  →  Warm-up da replay memory
Fase 1   →  Treino RL com cobertura funcional
Fase 2   →  Geração de test cases com oráculo via CrewAI
```

---

### Diagrama — Fluxo Proposto

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     FLUXO PROPOSTO — DRL-MOBTEST                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

                              APK
                               │
                               ▼
                  ┌────────────────────────┐
                  │    Instala no device   │
                  │     (adb install)      │
                  └────────────┬───────────┘
                               │
   ╔═══════════════════════════▼════════════════════════════╗
   ║  FASE 0a — Leitura do Manifesto Android                ║
   ║                                                        ║
   ║   Lê AndroidManifest.xml do APK (sem executar o app)  ║
   ║                                                        ║
   ║   Output:                                              ║
   ║   ┌──────────────────────────────────────────────┐    ║
   ║   │  Lista de todas as Activities declaradas     │    ║
   ║   │  • protect.budgetwatch.MainActivity          │    ║
   ║   │  • protect.budgetwatch.TransactionActivity   │    ║
   ║   │  • protect.budgetwatch.SettingsActivity      │    ║
   ║   │  • ...                                       │    ║
   ║   └──────────────────────────────────────────────┘    ║
   ╚═══════════════════════════╤════════════════════════════╝
                               │
   ╔═══════════════════════════▼════════════════════════════╗
   ║  FASE 0b — Crawling Semântico Guiado                   ║
   ║                                                        ║
   ║   Para cada Activity da lista (Fase 0a):               ║
   ║                                                        ║
   ║   ┌──────────┐    ┌──────────┐    ┌────────────────┐  ║
   ║   │ Abre     │───►│ Captura  │───►│ LLM interpreta │  ║
   ║   │ Activity │    │ XML hier.│    │ semântica:     │  ║
   ║   └──────────┘    └──────────┘    │ • tipo da tela │  ║
   ║                                   │ • campos/valid.│  ║
   ║                                   │ • resultado    │  ║
   ║                                   │   esperado     │  ║
   ║                                   └───────┬────────┘  ║
   ║                                           │            ║
   ║   ┌───────────────────────────────────────▼──────────┐ ║
   ║   │           requirements.csv (gerado auto)         │ ║
   ║   │  activity, field, id, action, type, size, value  │ ║
   ║   └──────────────────────────────────────────────────┘ ║
   ╚═══════════════════════════╤════════════════════════════╝
                               │
   ╔═══════════════════════════▼════════════════════════════╗
   ║  FASE 0c — Warm-up do Agente RL                        ║
   ║                                                        ║
   ║   Reutiliza transições coletadas no crawling:          ║
   ║                                                        ║
   ║   transição do crawling                                ║
   ║   (state, action, reward, next_state)                  ║
   ║          │                                             ║
   ║          ▼                                             ║
   ║   ┌─────────────────────────────────────────────────┐ ║
   ║   │            Replay Memory                        │ ║
   ║   │   [ t1 ][ t2 ][ t3 ][ t4 ][ t5 ] ...          │ ║
   ║   │   populada antes do treino começar              │ ║
   ║   └─────────────────────────────────────────────────┘ ║
   ║                                                        ║
   ║   Agente RL inicia com:                                ║
   ║   ✓ Mapa semântico do app                              ║
   ║   ✓ requirements.csv preenchido                        ║
   ║   ✓ Replay memory não vazia                            ║
   ╚═══════════════════════════╤════════════════════════════╝
                               │
   ╔═══════════════════════════▼════════════════════════════╗
   ║  FASE 1 — Treino RL com Cobertura Funcional            ║
   ║                                                        ║
   ║  ┌─────────────────────────────────────────────────┐  ║
   ║  │  Agente RL (DQN/Dueling)                        │◄─╫──────────┐
   ║  │  Estado: screenshot + contexto semântico        │  ║          │
   ║  └───────────────────┬─────────────────────────────┘  ║          │
   ║                      │                                 ║          │
   ║                      ▼                                 ║          │
   ║  ┌─────────────────────────────────────────────────┐  ║          │
   ║  │  Executa ação no device                         │  ║          │
   ║  └───────────────────┬─────────────────────────────┘  ║          │
   ║                      │                                 ║          │
   ║                      ▼                                 ║          │
   ║  ┌─────────────────────────────────────────────────┐  ║          │
   ║  │  Função de recompensa funcional:                │  ║          │
   ║  │                                                 │  ║          │
   ║  │  +10  nova activity visitada                    │  ║          │
   ║  │  +15  elemento interativo nunca testado         │  ║          │
   ║  │  +20  nova classe de entrada testada            │  ║          │
   ║  │  +50  oráculo confirmado (requisito atendido)   │  ║          │
   ║  │  -10  elemento interativo nunca tocado          │  ║          │
   ║  └───────────────────┬─────────────────────────────┘  ║          │
   ║                      │                                 ║          │
   ║                      ▼                                 ║          │
   ║  ┌─────────────────────────────────────────────────┐  ║          │
   ║  │  Log enriquecido por step:                      │  ║          │
   ║  │  • ação realizada                               │  ║          │
   ║  │  • XML da tela                                  │  ║          │
   ║  │  • anotação semântica (Fase 0b)                 │  ║          │
   ║  │  • screenshot                                   │  ║          │
   ║  │  • resultado observado vs esperado              │  ║          │
   ║  └───────────────────┬─────────────────────────────┘  ║          │
   ║                      │           mais episódios        ║          │
   ║                      └─────────────────────────────────╫──────────┘
   ╚═══════════════════════════╤════════════════════════════╝
                               │  treino concluído
   ╔═══════════════════════════▼════════════════════════════╗
   ║  FASE 2 — Geração de Test Cases com Oráculo            ║
   ║                                                        ║
   ║  Input para o CrewAI:                                  ║
   ║  ┌──────────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ║
   ║  │ Log de ações │ │  XML   │ │Anotação  │ │Screen- │ ║
   ║  │   brutas     │ │por step│ │semântica │ │ shot   │ ║
   ║  └──────┬───────┘ └───┬────┘ └────┬─────┘ └───┬────┘ ║
   ║         └─────────────┴───────────┴────────────┘      ║
   ║                               │                        ║
   ║                               ▼                        ║
   ║              ┌────────────────────────────┐            ║
   ║              │       CrewAI Transcriber   │            ║
   ║              └────────────────┬───────────┘            ║
   ║                               │                        ║
   ║                               ▼                        ║
   ║  ┌──────────────────────────────────────────────────┐ ║
   ║  │  Test Case: Adicionar transação com valor válido │ ║
   ║  │  ─────────────────────────────────────────────  │ ║
   ║  │  Pré-condição: App aberto na MainActivity        │ ║
   ║  │  Passo 1: Tocar em "+" → abre TransactionAct.   │ ║
   ║  │  Passo 2: Inserir 100 no campo "amount"          │ ║
   ║  │           (numérico, 1–10 dígitos)               │ ║
   ║  │  Passo 3: Tocar no botão "Save"                  │ ║
   ║  │  Esperado: transação aparece na lista       ✓    │ ║
   ║  │  Observado: navegou para TransactionViewAct ✓    │ ║
   ║  └──────────────────────────────────────────────────┘ ║
   ╚════════════════════════════════════════════════════════╝
```

---

## 4. Descrição das Fases Propostas

### Fase 0a — Leitura do Manifesto Android

**O que faz:** Lê o `AndroidManifest.xml` do APK usando ferramentas como `aapt` ou `apktool`, sem precisar executar o app.

**Por que é necessária:** Hoje o agente só descobre uma Activity quando navega até ela por acaso. Com o manifesto, sabe de antemão todas as telas declaradas, garantindo que nenhuma fique fora do escopo do teste.

**Output:** Lista ordenada de Activities, seus filtros de intent e permissões declaradas.

**Exemplo:**
```
protect.budgetwatch.MainActivity         (LAUNCHER)
protect.budgetwatch.TransactionActivity
protect.budgetwatch.TransactionViewActivity
protect.budgetwatch.SettingsActivity
```

---

### Fase 0b — Crawling Semântico Guiado

**O que faz:** Para cada Activity da lista (Fase 0a), abre a tela, captura o XML hierarchy e envia ao LLM (CrewAI já integrado) para interpretação semântica.

**Por que é necessária:** O XML capturado hoje pelo `uiautomator2` contém `class`, `text`, `resource-id`, `clickable` e `bounds` — informação semântica real que é descartada imediatamente. Um botão "Save" em qualquer app tem `text=Save` e `clickable=true`. Isso é transferível e interpretável.

**Output:**
- Anotação semântica de cada tela (tipo, propósito, elementos e validações)
- `requirements.csv` gerado automaticamente — elimina preenchimento manual
- Mapa de navegação do app

**Exemplo de anotação gerada pelo LLM:**
```
Tela: TransactionActivity
Propósito: Criar nova transação financeira
Campos:
  - amount (EditText, numérico, obrigatório, 1–10 dígitos)
  - description (EditText, texto livre, opcional)
Ações:
  - Save (Button) → confirma criação, navega para MainActivity
  - Cancel (Button) → descarta, volta para MainActivity
Resultado esperado ao salvar: transação aparece na lista da MainActivity
```

---

### Fase 0c — Warm-up da Replay Memory

**O que faz:** Reutiliza as transições coletadas durante o crawling (Fase 0b) para popular a replay memory antes do treino começar.

**Por que é necessária:** Hoje a replay memory começa vazia e os primeiros episódios são puramente aleatórios — o agente não consegue aprender até acumular amostras suficientes. O crawling já percorre o app; as transições geradas são aproveitadas gratuitamente.

**Output:** Replay memory com experiências iniciais reais do app, acelerando a convergência do agente.

---

### Fase 1 — Treino RL com Cobertura Funcional

**O que faz:** Substitui a função de recompensa baseada em navegação por uma baseada em cobertura funcional, usando o `requirements.csv` da Fase 0b (`is_req: true`).

**Por que é necessária:** A recompensa atual premia *quantidade de telas visitadas*. O agente aprende a navegar rapidamente entre telas — não a testar funcionalidades. Com a nova recompensa, o agente é incentivado a interagir com elementos específicos e confirmar oráculos.

**Comparativo da função de recompensa:**

| Evento | Recompensa atual | Recompensa proposta |
|---|---|---|
| Nova activity visitada | +10 | +10 |
| Mudança de activity | +5 | — |
| Ação válida | +1 | — |
| Elemento interativo nunca testado | — | +15 |
| Nova classe de entrada testada | — | +20 |
| Oráculo confirmado (requisito atendido) | — | +50 |
| Elemento interativo nunca tocado | — | -10 |

**Log enriquecido por step:** cada transição registra ação realizada, XML da tela, anotação semântica, screenshot e resultado observado vs. esperado.

---

### Fase 2 — Geração de Test Cases com Oráculo

**O que faz:** Envia ao CrewAI o log enriquecido (log + XML + anotação semântica + screenshot + resultado esperado), gerando test cases com estrutura completa.

**Por que é necessária:** O CrewAI hoje recebe apenas o log bruto sem contexto funcional, produzindo test cases sem pré-condição, sem resultado esperado e sem condição de sucesso verificável. Com o contexto enriquecido, o LLM consegue gerar oráculos reais.

**Comparativo do output do CrewAI:**

| Campo | Hoje | Proposto |
|---|---|---|
| Pré-condição | Ausente | App aberto na tela X |
| Passos | Ações brutas | Passos semânticos numerados |
| Resultado esperado | Ausente | Definido pelo requirements.csv + LLM |
| Resultado observado | Parcial | Capturado e comparado |
| Veredicto (pass/fail) | Ausente | Gerado automaticamente |

---

## 5. Comparativo Final

### O que muda em cada dimensão

```
DIMENSÃO              FLUXO ATUAL              FLUXO PROPOSTO
─────────────────     ──────────────────────   ──────────────────────────────
Conhecimento prévio   Nenhum                   Manifesto + mapa semântico
Início do treino      Replay memory vazia      Replay memory populada
Entrada do agente     Screenshot 38×38 px      Screenshot + contexto semântico
Função de recompensa  Navegação                Cobertura funcional
XML hierarchy         Descartado               Preservado e anotado por LLM
requirements.csv      Manual / vazio           Gerado automaticamente (Fase 0b)
is_req                false (desligado)        true (ativado)
Input do CrewAI       Só log bruto             Log + XML + anotação + screenshot
Test case output      Sem oráculo              Com pré-condição e oráculo
```

### Ponto de entrada recomendado (menor esforço, maior impacto)

Sem alterar nada no loop de RL, a mudança de menor esforço e maior impacto imediato é:

```
Passar o XML já capturado como contexto adicional para o CrewAI
       │
       ▼
Test cases com semântica real das telas,
mesmo sem as Fases 0a, 0b, 0c e 1 implementadas
```

### Diferencial em relação ao estado da arte

| Ferramenta | Exploração | Semântica | Oráculo funcional |
|---|---|---|---|
| Monkey | Aleatória | Nenhuma | Nenhum |
| DroidBot | Baseada em modelo | Nenhuma | Nenhum |
| Q-Testing / Sapienz | RL | Nenhuma | Nenhum |
| Testes com LLM puro | Manual/scriptada | Alta | Parcial |
| **DRL-MOBTEST proposto** | **RL sistemático** | **LLM automatizada** | **LLM gerado** |

O diferencial é a combinação: **exploração autônoma por RL** + **extração automática de semântica via LLM** + **geração de oráculos funcionais** — sem intervenção humana além de apontar o APK.
