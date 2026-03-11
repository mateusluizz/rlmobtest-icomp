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

## 3. Gráficos do Protótipo SBSE (Otimização de Suíte de Testes)

**Localização:** `sbse_prototype/visualization.py`
**Gerado por:** Classes `ParetoVisualizer` e `ComparisonVisualizer`

> **Nota:** Estes gráficos fazem parte do módulo experimental de otimização de suítes de teste via Search-Based Software Engineering (SBSE) e não são gerados no pipeline principal.

### 3.1 Pareto Front 2D (Frente de Pareto)

- **Arquivo:** `pareto_2d.png`
- **Eixo X:** Coverage (Cobertura)
- **Eixo Y:** Suite Size (Tamanho da Suíte)
- **O que mostra:** As soluções não-dominadas no espaço bi-objetivo, representando o trade-off entre maximizar cobertura e minimizar o número de casos de teste.
- **Como interpretar:**
  - Pontos mais à direita → maior cobertura.
  - Pontos mais abaixo → suíte mais compacta.
  - A curva de Pareto mostra as soluções ótimas onde não é possível melhorar uma métrica sem piorar a outra.
  - Estrela vermelha (se presente) → melhor solução selecionada.

### 3.2 Pareto Front 3D

- **Arquivo:** `pareto_3d.png`
- **Eixo X:** Coverage
- **Eixo Y:** Diversity (Diversidade)
- **Eixo Z:** Suite Size
- **O que mostra:** Extensão tridimensional da frente de Pareto, adicionando a dimensão de diversidade dos casos de teste.

### 3.3 Objectives Heatmap (Mapa de Calor)

- **Arquivo:** `heatmap.png`
- **O que mostra:** Matriz de correlação entre os objetivos de otimização (Coverage, Diversity, Size, Fault Rate). Valores próximos de +1/-1 indicam forte correlação positiva/negativa.
- **Como interpretar:**
  - Correlação negativa entre Coverage e Size → mais testes geralmente significam mais cobertura.
  - Correlação entre Diversity e Fault Rate → suítes diversas tendem a encontrar mais falhas.

### 3.4 Objectives Distribution (Distribuição dos Objetivos)

- **Arquivo:** `distribution.png`
- **Layout:** 2×2 histogramas
- **O que mostra:** Distribuição estatística de cada objetivo (Coverage, Diversity, Size, Fault Rate) na população de soluções. Inclui linhas de média (vermelha) e mediana (azul).
- **Como interpretar:**
  - Distribuição concentrada → soluções similares.
  - Distribuição dispersa → alta variabilidade nas soluções.
  - Diferença entre média e mediana → assimetria na distribuição.

### 3.5 Convergence (Convergência)

- **Arquivo:** `convergence.png`
- **Layout:** 3 subplots verticais
- **Eixo X:** Geração do algoritmo evolutivo
- **O que mostra:** Evolução das métricas médias (Coverage, Diversity, Suite Size) ao longo das gerações do algoritmo genético.
- **Como interpretar:**
  - Curvas estabilizando → algoritmo convergiu.
  - Coverage subindo + Size descendo → otimização está funcionando.

### 3.6 Suite Comparison (Comparação de Suítes)

- **Arquivo:** `comparison.png`
- **O que mostra:** Gráfico de barras agrupadas comparando a suíte de testes **original** (coral) com a suíte **otimizada pelo SBSE** (azul) em três métricas normalizadas: Coverage, Diversity e Fault Rate.
- **Como interpretar:**
  - Barras azuis maiores que corais → a otimização melhorou a métrica.
  - Valores no topo das barras → valores exatos para referência.

### 3.7 Radar Chart (Gráfico Radar)

- **Arquivo:** `radar_chart.png`
- **O que mostra:** Comparação visual em formato polar entre a suíte original e a otimizada em 4 dimensões: Coverage, Diversity, Fault Rate e Efficiency.
- **Como interpretar:**
  - Área maior da suíte otimizada (azul) → melhoria geral.
  - Cada eixo vai de 0 a 1 (normalizado).
  - Sobreposição → dimensões onde ambas as suítes têm desempenho similar.

---

## Resumo dos Arquivos Gerados

| Arquivo | Gerador | Pipeline Principal | Descrição Resumida |
|---------|---------|-------------------|-------------------|
| `metrics_{run_id}.png` | `metrics.py` | Sim | 7 subplots de métricas de treinamento DQN |
| `report.html` | `report.py` | Sim | Relatório consolidado com barras de progresso |
| `pareto_2d.png` | `visualization.py` | Não (SBSE) | Frente de Pareto 2D |
| `pareto_3d.png` | `visualization.py` | Não (SBSE) | Frente de Pareto 3D |
| `heatmap.png` | `visualization.py` | Não (SBSE) | Correlação entre objetivos |
| `distribution.png` | `visualization.py` | Não (SBSE) | Histogramas dos objetivos |
| `convergence.png` | `visualization.py` | Não (SBSE) | Convergência por geração |
| `comparison.png` | `visualization.py` | Não (SBSE) | Baseline vs. Otimizado |
| `radar_chart.png` | `visualization.py` | Não (SBSE) | Comparação radar 4 dimensões |
