# Tutorial: Como a DQN do RLMobTest Funciona

## O que o projeto faz?

Imagine que você tem um app Android e quer testá-lo automaticamente — clicar em botões, preencher campos, navegar pelas telas. Em vez de um humano fazer isso manualmente, este projeto treina um **agente de inteligência artificial** para fazer isso sozinho, como um robozinho aprendendo a usar o app.

## O que é DQN?

**DQN = Deep Q-Network** (Rede Q Profunda). É uma técnica onde uma rede neural aprende, por tentativa e erro, qual a **melhor ação** a tomar em cada situação.

Pense assim: é como ensinar um cachorro. Ele faz algo bom → ganha petisco (recompensa positiva). Faz algo ruim → não ganha nada ou leva uma bronca (recompensa negativa). Com o tempo, ele aprende o que fazer.

## Os 4 Pilares do Aprendizado

### 1. O que o agente "enxerga" (Estado)

O agente tira uma **screenshot da tela do celular**, redimensiona para uma imagem pequena de **38x38 pixels** e passa pela rede neural. É como se o robô tirasse uma foto da tela e tentasse entender o que está vendo.

### 2. O que o agente pode fazer (Ações)

O agente tem até **30 ações** disponíveis em cada momento:

| Tipo | Exemplos |
|------|----------|
| **Cliques** | Tocar em botões, links |
| **Digitação** | Preencher campos de texto (textos curtos, longos, números, símbolos) |
| **Scroll** | Rolar para cima, baixo, esquerda, direita |
| **Navegação** | Botão home, voltar, menu |
| **Outros** | Marcar checkbox, clique longo, rotacionar tela |

As ações disponíveis mudam conforme a tela — se não tem campo de texto, a ação "digitar" não aparece.

### 3. Como o agente aprende (Recompensas)

Cada ação recebe uma "nota":

| Situação | Recompensa |
|----------|------------|
| Descobrir uma **tela nova** do app | **+10** |
| Navegar para uma tela útil | **+5** |
| Fazer uma ação **diferente** da anterior | **+1** |
| Clicar num botão importante (ex: "Save") | **+20 a +50** |
| Repetir a mesma ação | **-2** |
| App **crashar** | **-5** |
| Sair do app | **-5** |

O agente aprende que explorar telas novas e clicar em botões importantes dá mais recompensa. Repetir ações ou causar crashes é punido.

### 4. A rede neural (o "cérebro")

A rede recebe a imagem da tela e dá uma **pontuação para cada ação possível**. A ação com maior pontuação é a que o agente acha que vai trazer mais recompensa. Com o treino, essas pontuações ficam cada vez mais precisas.

Arquitetura simplificada:

```
Screenshot (38x38) → [Filtros de imagem] → [Camada de decisão] → Pontuação de cada ação
                      (3 camadas CNN)        (camada linear)       (ex: clicar botão = 8.5,
                                                                         scroll = 3.2, ...)
```

## Como Funciona o Treino (Passo a Passo)

```
1. Abre o app no celular/emulador
2. Tira screenshot → estado inicial
3. Para cada passo (até 100 por episódio):
   a. O agente escolhe uma ação (aleatória no início, inteligente depois)
   b. Executa a ação no celular (clica, digita, etc.)
   c. Recebe recompensa (+10, -2, etc.)
   d. Tira nova screenshot → novo estado
   e. Guarda essa experiência na memória
   f. Aprende com experiências passadas (treina a rede neural)
4. Se o app crashar ou travar → reinicia
5. Repete por vários episódios (ex: 20 episódios de 1 hora)
```

## Exploração vs. Aproveitamento

No início, o agente é **90% aleatório** — fica clicando em coisas sem saber o que faz. Isso é proposital! Ele precisa experimentar para descobrir o que funciona.

Com o tempo, a aleatoriedade cai para **5%**, e ele passa a usar o que aprendeu. É como um estagiário: no começo explora tudo, depois foca no que sabe que funciona.

```
Início:  ████████████░░  90% aleatório / 10% inteligente
Meio:    ██████░░░░░░░░  50% / 50%
Final:   █░░░░░░░░░░░░░   5% aleatório / 95% inteligente
```

## Memória de Replay

O agente guarda suas experiências numa "memória" (até 10.000 ou 50.000 experiências). Na hora de aprender, ele sorteia experiências antigas e aprende com elas de novo — como um aluno revisando provas anteriores.

## Versão Original vs. Melhorada

O projeto tem **dois agentes**:

| | Original | Melhorado |
|---|---|---|
| **Rede** | Simples (3 filtros + decisão) | Dueling (separa "valor da tela" de "valor da ação") |
| **Memória** | Aleatória (10k) | Priorizada (50k) — revisa mais as experiências difíceis |
| **Estabilidade** | Básica | Double DQN + Target Network — evita "vicios" de aprendizado |
| **Exploração** | Rápida (decai em ~500 passos) | Gradual (decai em ~10.000 passos) |

A versão melhorada é mais estável e aprende melhor, mas é mais lenta.

## Resultado Final

Depois do treino, o agente sabe navegar pelo app, e o projeto:

- Mede a **cobertura de código** (quantos % do código foram executados via JaCoCo)
- Gera **casos de teste** descrevendo o que o agente fez em cada tela
- Produz **gráficos** mostrando a evolução do aprendizado
