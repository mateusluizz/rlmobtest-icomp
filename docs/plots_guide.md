# Guia dos Gráficos Gerados pelo RLMobTest

Este documento descreve cada gráfico gerado durante o treinamento e análise do pipeline DRL-MOBTest.

---

## 1. Gráfico Principal de Métricas de Treinamento

**Arquivo:** `metrics_{run_id}.png`
**Localização:** `output/{package}/{agent_type}/{YYYY}/{MM}/{DD}/plots/`
**Gerado por:** `rlmobtest/training/metrics.py` → método `plot_metrics()`
**Dimensões:** 18×14 polegadas, 150 DPI
**Layout:** Grade 3×3 com 7 subplots ativos

### 1.1 Episode Rewards (Recompensas por Episódio)

- **Posição:** Linha 0, Coluna 0
- **Eixo X:** Episódio
- **Eixo Y:** Recompensa
- **O que mostra:** A recompensa total acumulada pelo agente DQN em cada episódio de treinamento. Inclui uma **média móvel de 10 episódios** (linha vermelha) que suaviza as oscilações e evidencia a tendência de aprendizado.
- **Como interpretar:**
  - Tendência crescente → o agente está aprendendo a navegar melhor pela interface.
  - Valores estáveis → a política de navegação convergiu.
  - Quedas bruscas → o agente encontrou estados problemáticos (crashes, loops, saída do app).

### 1.2 Training Loss (Perda do Treinamento)

- **Posição:** Linha 0, Coluna 1
- **Eixo X:** Episódio
- **Eixo Y:** Loss
- **O que mostra:** A perda (loss) da rede neural DQN ao longo dos episódios. Indica o erro entre os Q-values previstos e os valores-alvo calculados pelo algoritmo.
- **Como interpretar:**
  - Decaimento gradual → a rede neural está convergindo e as estimativas de Q-value estão melhorando.
  - Valores muito altos ou instáveis → pode indicar problemas de hiperparâmetros (learning rate alto, batch size inadequado).
  - Se não houver dados, exibe "No loss data" (ocorre nos primeiros episódios antes do replay memory ter amostras suficientes).

### 1.3 Q-Values (Valores Q Médios)

- **Posição:** Linha 0, Coluna 2
- **Eixo X:** Episódio
- **Eixo Y:** Q-Value Médio
- **O que mostra:** A média dos Q-values estimados pela rede neural em cada episódio, com **média móvel de 10 episódios** (linha teal). Representa a "confiança" do agente sobre a qualidade das ações disponíveis.
- **Como interpretar:**
  - Crescimento gradual → o agente está aprendendo a estimar melhor o valor das ações.
  - Estabilização → a política convergiu.
  - Valores excessivamente altos → possível superestimação (overestimation bias), comum em DQN vanilla.

### 1.4 Episode Duration (Duração dos Episódios)

- **Posição:** Linha 1, Coluna 0
- **Eixo X:** Episódio
- **Eixo Y:** Duração (segundos)
- **O que mostra:** O tempo de duração de cada episódio em segundos, exibido como **gráfico de barras** (laranja). Uma **linha vermelha tracejada** indica a duração média de todos os episódios.
- **Como interpretar:**
  - Barras próximas ao limite (300s) → o agente usou o tempo máximo do episódio, explorando amplamente.
  - Barras curtas → o episódio terminou cedo, possivelmente por crash do app ou saída para a tela inicial.
  - Variação alta → o agente encontra cenários diversos a cada episódio.

### 1.5 Cumulative Reward (Recompensa Acumulada)

- **Posição:** Linha 1, Coluna 1
- **Eixo X:** Episódio
- **Eixo Y:** Recompensa Acumulada
- **O que mostra:** A soma acumulada das recompensas ao longo de todos os episódios (linha roxa com preenchimento). Representa o progresso total do agente durante todo o treinamento.
- **Como interpretar:**
  - Curva crescente linear → recompensas consistentes a cada episódio.
  - Curva crescente acelerando → o agente está melhorando progressivamente.
  - Platô → o agente parou de acumular recompensas significativas (pode indicar saturação ou estagnação).

### 1.6 Epsilon Decay (Taxa de Exploração)

- **Posição:** Linha 1, Coluna 2
- **Eixo X:** Passo (step)
- **Eixo Y:** Epsilon (0.0 a 1.0)
- **O que mostra:** O decaimento do parâmetro epsilon ao longo dos passos de treinamento. Epsilon controla o balanço entre **exploração** (ações aleatórias) e **explotação** (ações da política aprendida).
- **Como interpretar:**
  - Início alto (ε ≈ 0.9) → o agente explora bastante no começo (ações majoritariamente aleatórias).
  - Decaimento exponencial → transição gradual para explotação da política aprendida.
  - Final baixo (ε ≈ 0.05) → o agente usa predominantemente a política aprendida, com pequena margem de exploração residual.
- **Parâmetros padrão:** ε_start = 0.9, ε_end = 0.05, decay = 500 passos.

### 1.7 Activity Coverage (Cobertura de Activities)

- **Posição:** Linha 2, Colunas 0-1 (subplot duplo)
- **Eixo X:** Episódio
- **Eixo Y primário:** Activities Únicas (barras verdes)
- **Eixo Y secundário:** Activities Acumuladas (linha vermelha com marcadores)
- **O que mostra:** Gráfico de eixo duplo combinando barras (activities únicas descobertas por episódio) com uma linha acumulada (total de activities distintas ao longo do treinamento).
- **Como interpretar:**
  - Barras altas → o agente descobriu muitas telas novas naquele episódio.
  - Linha acumulada subindo → novas telas estão sendo descobertas continuamente.
  - Linha acumulada estabilizando → o agente já explorou a maioria das telas acessíveis.
  - Comparar com o número total de activities do app para avaliar a cobertura funcional.

---

## 2. Relatório HTML (report.html)

**Arquivo:** `report.html`
**Localização:** `output/{package}/{agent_type}/{YYYY}/{MM}/{DD}/`
**Gerado por:** `rlmobtest/training/report.py`

Embora não seja um gráfico propriamente dito, o relatório HTML contém **barras de progresso visuais** para as seguintes métricas:

| Métrica | Cor | Descrição |
|---------|-----|-----------|
| Activity Coverage | Verde/Laranja/Vermelho | Activities descobertas vs. requeridas |
| Requirements Coverage | Verde/Laranja/Vermelho | Requisitos satisfeitos vs. total extraído |
| Transcription Coverage | Verde/Laranja/Vermelho | Casos de teste transcritos vs. gerados |
| JaCoCo Line Coverage | Verde/Laranja/Vermelho | Linhas de código exercitadas |
| JaCoCo Branch Coverage | Verde/Laranja/Vermelho | Ramificações condicionais exercitadas |
| JaCoCo Method Coverage | Verde/Laranja/Vermelho | Métodos invocados durante exploração |

**Código de cores:**
- 🟢 Verde: ≥ 70% (boa cobertura)
- 🟠 Laranja: ≥ 40% (cobertura moderada)
- 🔴 Vermelho: < 40% (cobertura baixa)

---

## Resumo dos Arquivos Gerados

| Arquivo | Gerador | Descrição Resumida |
|---------|---------|-------------------|
| `metrics_{run_id}.png` | `metrics.py` | 7 subplots de métricas de treinamento DQN |
| `report.html` | `report.py` | Relatório consolidado com barras de progresso |
