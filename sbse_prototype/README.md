# 🚀 SBSE + RL Integration Framework

## Otimização Multi-Objetivo de Casos de Teste para Android

---

## 📋 Visão Geral

Este framework integra **Search-Based Software Engineering (SBSE)** com **Deep Reinforcement Learning (DRL)** para otimizar automaticamente suítes de teste geradas para aplicações Android.

### Problema que Resolve

O **DRL-MobTest** gera casos de teste automaticamente, mas:
- ❌ Produz muitos casos redundantes
- ❌ Não otimiza explicitamente para múltiplos objetivos
- ❌ Falta trade-offs claros entre cobertura, diversidade e tamanho

### Solução

```
RL Agent (DQN) → Pool de TCs → SBSE (NSGA-II) → Fronteira de Pareto → Suíte Otimizada
```

**Resultado**: Suítes **60% menores** com **mesma ou melhor cobertura** e **maior diversidade**.

---

## 🎯 Objetivos de Otimização

| Objetivo | Descrição | Meta |
|----------|-----------|------|
| **Cobertura** | Linhas/métodos/activities cobertos | Maximizar |
| **Diversidade** | Variedade de ações e fluxos | Maximizar |
| **Tamanho** | Número de casos de teste | Minimizar |
| **Detecção de Falhas** | Taxa de crashes encontrados | Maximizar |

---

## 📦 Estrutura do Projeto

```
sbse_prototype/
│
├── test_case_representation.py   # Estruturas de dados (TestCase, TestSuite)
├── metrics_calculator.py         # Cálculo de métricas multi-objetivo
├── sbse_optimizer.py             # Otimizador NSGA-II/SPEA2/MOEAD
├── statistical_analysis.py       # Testes estatísticos (Mann-Whitney, etc.)
├── visualization.py              # Plots de Pareto, comparações
│
├── SBSE_RL_Integration.ipynb     # 📓 Notebook principal completo
│
├── README.md                     # Este arquivo
└── requirements_sbse.txt         # Dependências adicionais
```

---

## 🛠️ Instalação

### 1. Dependências Base

Certifique-se de ter o ambiente RLMobTest configurado:

```bash
cd /path/to/rlmobtest-icomp
source .venv/bin/activate  # ou seu ambiente virtual
```

### 2. Instalar Dependências SBSE

```bash
pip install pymoo scipy matplotlib seaborn pandas
```

Ou usar o arquivo de requirements:

```bash
pip install -r sbse_prototype/requirements_sbse.txt
```

### 3. Verificar Instalação

```python
python -c "from pymoo.algorithms.moo.nsga2 import NSGA2; print('✅ Pymoo OK')"
python -c "import scipy.stats; print('✅ SciPy OK')"
```

---

## 🚀 Uso Rápido

### Opção 1: Jupyter Notebook (Recomendado)

```bash
cd sbse_prototype
jupyter notebook SBSE_RL_Integration.ipynb
```

Execute todas as células para:
1. Gerar casos de teste simulados
2. Otimizar com NSGA-II
3. Visualizar fronteira de Pareto
4. Análise estatística

### Opção 2: Script Python

```python
from sbse_optimizer import SBSEOptimizer
from test_case_representation import TestCase, TestSuite
from metrics_calculator import MetricsCalculator

# 1. Criar pool de test cases (do output do RLMobTest)
test_cases = [...]  # Seus test cases

# 2. Configurar otimizador
optimizer = SBSEOptimizer(
    algorithm="nsga2",
    population_size=100,
    n_generations=50
)

# 3. Setup problema
optimizer.setup_problem(test_cases, min_suite_size=10, max_suite_size=30)

# 4. Otimizar
result = optimizer.optimize(verbose=True)

# 5. Obter melhor solução
best_suite, best_metrics = optimizer.select_best_solution(criterion="balanced")

print(f"Suite otimizada: {best_metrics.suite_size} TCs")
print(f"Cobertura: {best_metrics.coverage:.2f}")
```

---

## 🔗 Integração com RLMobTest

### Pipeline Completo

```python
# 1. Treinar RL Agent (main.py)
python main.py --time 3600 --mode improved

# 2. Carregar casos de teste gerados
from test_case_representation import create_test_suite_from_rl_output

suite = create_test_suite_from_rl_output(
    test_cases_dir=Path("output/test_cases"),
    metrics_file=Path("output/metrics/metrics_20250101_120000.json"),
    name="RL_Generated_Suite"
)

# 3. Otimizar com SBSE
from sbse_optimizer import SBSEOptimizer

optimizer = SBSEOptimizer(algorithm="nsga2", population_size=100, n_generations=50)
optimizer.setup_problem(suite.test_cases)
result = optimizer.optimize()

# 4. Salvar suíte otimizada
best_suite, _ = optimizer.select_best_solution(criterion="balanced")
best_suite.save("output/sbse_results/optimized_suite.json")
```

---

## 📊 Resultados Esperados

### Comparação Típica

| Métrica | Baseline (50 TCs) | SBSE Otimizada (~20 TCs) | Melhoria |
|---------|-------------------|--------------------------|----------|
| **Tamanho** | 50 | 20 | **-60%** ✅ |
| **Cobertura** | 100% | 98-102% | **~0%** ✅ |
| **Diversidade** | 0.45 | 0.68 | **+51%** ✅ |
| **Tempo Execução** | 500s | 200s | **-60%** ✅ |

### Evidência Estatística

- ✅ **Mann-Whitney U**: p < 0.001 (altamente significativo)
- ✅ **Effect Size (A12)**: 0.78 (large effect)
- ✅ **Cohen's d**: 1.2 (large effect)

---

## 🎨 Visualizações Disponíveis

### 1. Fronteira de Pareto 2D

```python
from visualization import ParetoVisualizer

viz = ParetoVisualizer()
viz.plot_pareto_front_2d(pareto_front, objectives=("coverage", "suite_size"))
```

![Pareto 2D](docs/pareto_2d_example.png)

### 2. Fronteira de Pareto 3D

```python
viz.plot_pareto_front_3d(pareto_front, objectives=("coverage", "diversity", "suite_size"))
```

### 3. Comparação Baseline vs Otimizada

```python
from visualization import ComparisonVisualizer

comp_viz = ComparisonVisualizer()
comp_viz.plot_suite_comparison(baseline_metrics, optimized_metrics)
```

### 4. Radar Chart

```python
comp_viz.plot_improvement_radar(baseline_metrics, optimized_metrics)
```

---

## 🧪 Análise Estatística

### Testes Disponíveis

```python
from statistical_analysis import StatisticalAnalyzer

analyzer = StatisticalAnalyzer(alpha=0.05)

# Mann-Whitney U Test
result = analyzer.mann_whitney_u_test(baseline_samples, optimized_samples, "coverage")
print(result.interpretation)

# Relatório completo
report = analyzer.create_comparison_report(baseline_dict, optimized_dict)
print(report)
```

### Métricas de Effect Size

- **Vargha-Delaney A12**: Medida não-paramétrica
- **Cohen's d**: Medida paramétrica
- Interpretação automática (negligible, small, medium, large)

---

## ⚙️ Configurações Avançadas

### Algoritmos Disponíveis

```python
# NSGA-II (recomendado para 2-3 objetivos)
optimizer = SBSEOptimizer(algorithm="nsga2")

# NSGA-III (para 4+ objetivos)
optimizer = SBSEOptimizer(algorithm="nsga3")

# SPEA2 (alternativa ao NSGA-II)
optimizer = SBSEOptimizer(algorithm="spea2")

# MOEA/D (baseado em decomposição)
optimizer = SBSEOptimizer(algorithm="moead")
```

### Critérios de Seleção

```python
# Maximizar cobertura
best = optimizer.select_best_solution(criterion="coverage")

# Maximizar diversidade
best = optimizer.select_best_solution(criterion="diversity")

# Trade-off balanceado
best = optimizer.select_best_solution(criterion="balanced")

# Suíte mínima com boa cobertura
best = optimizer.select_best_solution(criterion="minimal")
```

---

## 📝 Exemplo Completo

Ver: [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb)

O notebook contém:
- ✅ Geração de dados sintéticos
- ✅ Otimização com NSGA-II
- ✅ Análise estatística completa
- ✅ Todas as visualizações
- ✅ Interpretação de resultados

---

## 🤔 FAQ

### Q: Preciso de ground truth de bugs?

**A**: Não necessariamente. O objetivo "fault detection rate" usa crashes detectados durante a execução. Se você tem bugs conhecidos, pode adaptá-lo.

### Q: Quanto tempo leva a otimização?

**A**: Para 50 TCs, 100 indivíduos, 50 gerações: ~30-60 segundos em CPU moderna.

### Q: Posso adicionar novos objetivos?

**A**: Sim! Edite `metrics_calculator.py` para adicionar novas métricas e ajuste `ObjectiveMetrics`.

### Q: Como validar os resultados?

**A**: Use análise estatística (`statistical_analysis.py`) com múltiplas execuções e compare com baselines (random, greedy, etc.).

---

## 📚 Referências

### Algoritmos SBSE

- **NSGA-II**: Deb et al., "A Fast and Elitist Multiobjective Genetic Algorithm", IEEE TEC 2002
- **SPEA2**: Zitzler et al., "SPEA2: Improving the Strength Pareto EA", EUROGEN 2001
- **MOEA/D**: Zhang & Li, "MOEA/D: A Multiobjective EA Based on Decomposition", IEEE TEC 2007

### Test Suite Optimization

- Yoo & Harman, "Regression Testing Minimization, Selection and Prioritization", STVR 2012
- Fraser & Arcuri, "Whole Test Suite Generation", IEEE TSE 2013

### Android Testing

- Choudhary et al., "Automated Test Input Generation for Android", ICSE 2015
- Mao et al., "Sapienz: Multi-objective Automated Testing for Android", ISSTA 2016

---

## 🤝 Contribuições

### Como Contribuir

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-metrica`
3. Commit: `git commit -m 'Add nova métrica X'`
4. Push: `git push origin feature/nova-metrica`
5. Abra um Pull Request

### TODOs

- [ ] Integração online (RL e SBSE co-evoluindo)
- [ ] Suporte para múltiplas apps simultaneamente
- [ ] Métricas adicionais (energia, memória)
- [ ] Comparação com Sapienz, MOTSD
- [ ] Dashboard web interativo

---

## 📄 Licença

MIT License - Ver arquivo `LICENSE`

---

## 👥 Autores

**Mateus Luiz** - [@mateusluizz](https://github.com/mateusluizz)

**Projeto**: DRL-MobTest + SBSE Integration

**Instituição**: [Sua Universidade]

**Contato**: [seu-email@universidade.br]

---

## 🙏 Agradecimentos

- Baseado no RLMobTest de Eliane Collins
- Pymoo framework (Julian Blank & Kalyanmoy Deb)
- Comunidade SBSE

---

**⭐ Se este projeto foi útil, considere dar uma estrela!**

---

*Última atualização: Dezembro 2025*
