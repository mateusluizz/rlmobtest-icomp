# 📑 Índice do Framework SBSE + RL

**Projeto**: DRL-MobTest + SBSE Integration
**Data**: Dezembro 2025

---

## 🚀 Por Onde Começar?

### Se você quer...

#### 📖 **Entender o projeto**
→ Leia: [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md)
- Visão geral em 5 minutos
- Problema, solução, resultados
- Ideal para apresentar ao professor

#### 💻 **Executar o código**
→ Opção 1: [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb) (Recomendado)
- Notebook interativo completo
- Gera dados, otimiza, visualiza
- Pronto para demonstração

→ Opção 2: [`example_full_pipeline.py`](example_full_pipeline.py)
- Script Python standalone
- Pipeline end-to-end
- Executa: `python example_full_pipeline.py`

#### 🔗 **Integrar ao RLMobTest**
→ Leia: [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md)
- Como adicionar SBSE ao main.py
- Exemplos de configuração
- Troubleshooting

#### 📚 **Usar como biblioteca**
→ Leia: [`README.md`](README.md)
- Documentação completa da API
- Exemplos de uso de cada módulo
- Configurações avançadas

---

## 📂 Estrutura de Arquivos

### 📄 Documentação

| Arquivo | Propósito | Quando Ler |
|---------|-----------|------------|
| [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) | Sumário executivo do projeto | Primeiro! Visão geral rápida |
| [`README.md`](README.md) | Guia completo de uso | Quando for usar os módulos |
| [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) | Como integrar ao RLMobTest | Ao implementar em produção |
| [`INDEX.md`](INDEX.md) | Este arquivo (navegação) | Quando estiver perdido 😊 |

### 💻 Código-Fonte

| Arquivo | Linhas | Descrição | Importar Como |
|---------|--------|-----------|---------------|
| [`test_case_representation.py`](test_case_representation.py) | ~400 | Estruturas de dados (TestCase, TestSuite, Action) | `from test_case_representation import TestCase` |
| [`metrics_calculator.py`](metrics_calculator.py) | ~500 | Cálculo de métricas multi-objetivo | `from metrics_calculator import MetricsCalculator` |
| [`sbse_optimizer.py`](sbse_optimizer.py) | ~600 | Otimizador NSGA-II/SPEA2/MOEA/D | `from sbse_optimizer import SBSEOptimizer` |
| [`statistical_analysis.py`](statistical_analysis.py) | ~550 | Testes estatísticos (Mann-Whitney, etc.) | `from statistical_analysis import StatisticalAnalyzer` |
| [`visualization.py`](visualization.py) | ~550 | Visualizações (Pareto, comparações) | `from visualization import ParetoVisualizer` |

**Total**: ~2600 linhas de código Python

### 📓 Notebooks e Scripts

| Arquivo | Propósito | Uso |
|---------|-----------|-----|
| [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb) | Notebook completo end-to-end | `jupyter notebook SBSE_RL_Integration.ipynb` |
| [`example_full_pipeline.py`](example_full_pipeline.py) | Script standalone demonstração | `python example_full_pipeline.py` |

### 📦 Configuração

| Arquivo | Propósito |
|---------|-----------|
| [`requirements_sbse.txt`](requirements_sbse.txt) | Dependências Python (pymoo, scipy, etc.) |

---

## 🎯 Casos de Uso

### Caso 1: Demonstração Rápida (15 minutos)

```bash
# 1. Instalar dependências
pip install -r requirements_sbse.txt

# 2. Executar notebook
jupyter notebook SBSE_RL_Integration.ipynb

# 3. Run All Cells
# Resultado: Visualizações + análise completa
```

**Output**:
- ✅ Fronteira de Pareto (2D e 3D)
- ✅ Análise estatística (p-values, effect sizes)
- ✅ Comparação baseline vs otimizada
- ✅ Arquivos salvos em `output/sbse_results/`

### Caso 2: Integração com RLMobTest (1 hora)

```bash
# 1. Treinar RL
python main.py --time 3600

# 2. Copiar módulos SBSE
cp sbse_prototype/*.py .

# 3. Adicionar ao main.py (ver INTEGRATION_GUIDE.md)
# ... editar main.py ...

# 4. Re-executar com SBSE
python main.py --time 3600 --enable-sbse
```

### Caso 3: Pesquisa/Artigo (1 semana)

1. Selecionar 10 apps do Google Play
2. Executar 30 runs independentes por app
3. Coletar métricas (ver `metrics_calculator.py`)
4. Análise estatística (ver `statistical_analysis.py`)
5. Gerar visualizações (ver `visualization.py`)
6. Escrever paper usando resultados

---

## 📊 Fluxo de Dados

### Pipeline Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                    RLMobTest (main.py)                          │
│  • DQN Training                                                 │
│  • TC Generation                                                │
└────────────────────┬────────────────────────────────────────────┘
                     │ output/test_cases/*.txt
                     │ output/metrics/*.json
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         test_case_representation.py                             │
│  • Parse TCs from files                                         │
│  • Create TestSuite                                             │
└────────────────────┬────────────────────────────────────────────┘
                     │ TestSuite object
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│            metrics_calculator.py                                │
│  • Calculate coverage, diversity, size, fault rate              │
│  • Compute ObjectiveMetrics                                     │
└────────────────────┬────────────────────────────────────────────┘
                     │ Metrics for each TC
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              sbse_optimizer.py                                  │
│  • Define optimization problem                                  │
│  • Run NSGA-II (100 individuals, 50 generations)               │
│  • Generate Pareto front                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │ Pareto front solutions
                     ├─────────────┬──────────────┐
                     ▼             ▼              ▼
            ┌─────────────┐ ┌──────────┐ ┌───────────────┐
            │ statistical │ │ visuali- │ │ Save results  │
            │ _analysis.py│ │ zation.py│ │ (JSON, plots) │
            └─────────────┘ └──────────┘ └───────────────┘
```

---

## 🛠️ Referência Rápida da API

### Criar Test Case

```python
from test_case_representation import TestCase, Action

tc = TestCase(
    id="TC_001",
    actions=[Action(0, "click", "button_1")],
    coverage={"Class.java:42"},
    crashes=0
)
```

### Calcular Métricas

```python
from metrics_calculator import MetricsCalculator

calc = MetricsCalculator()
metrics = calc.calculate_all_metrics(suite)
print(f"Coverage: {metrics.coverage}")
```

### Otimizar com SBSE

```python
from sbse_optimizer import SBSEOptimizer

optimizer = SBSEOptimizer(algorithm="nsga2", population_size=100, n_generations=50)
optimizer.setup_problem(test_cases)
result = optimizer.optimize()
best_suite, best_metrics = optimizer.select_best_solution(criterion="balanced")
```

### Análise Estatística

```python
from statistical_analysis import StatisticalAnalyzer

analyzer = StatisticalAnalyzer()
result = analyzer.mann_whitney_u_test(baseline_samples, optimized_samples, "coverage")
print(result.interpretation)
```

### Visualização

```python
from visualization import ParetoVisualizer

viz = ParetoVisualizer()
viz.plot_pareto_front_2d(pareto_front, objectives=("coverage", "suite_size"))
```

---

## 📖 Glossário

| Termo | Significado |
|-------|-------------|
| **TC** | Test Case (caso de teste) |
| **SBSE** | Search-Based Software Engineering |
| **NSGA-II** | Non-dominated Sorting Genetic Algorithm II |
| **Pareto Front** | Conjunto de soluções não-dominadas (trade-offs ótimos) |
| **A12** | Vargha-Delaney A12 (effect size não-paramétrico) |
| **Mann-Whitney U** | Teste estatístico não-paramétrico |
| **Diversity** | Jaccard distance entre casos de teste |
| **Coverage** | Linhas/métodos/activities cobertos |

---

## 🔍 FAQ

### Q: Qual arquivo devo apresentar ao professor?

**A**: [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) + demonstração do [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb)

### Q: Como executar o código sem o RLMobTest?

**A**: Use [`example_full_pipeline.py`](example_full_pipeline.py) que gera dados sintéticos

### Q: Preciso modificar o main.py?

**A**: Não inicialmente. Use pós-processamento (ver [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md))

### Q: Qual é o arquivo principal?

**A**: Para execução: [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb). Para leitura: [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md)

### Q: Os módulos têm dependências entre si?

**A**: Sim:
```
test_case_representation.py (base)
    ↓
metrics_calculator.py
    ↓
sbse_optimizer.py
    ↓
statistical_analysis.py, visualization.py
```

### Q: Onde estão os testes unitários?

**A**: Não implementados nesta versão. Cada módulo tem `if __name__ == "__main__":` com exemplos.

---

## 🎓 Para o Professor Revisar

### Checklist de Avaliação

- [ ] **Código completo**: 5 módulos Python (~2600 linhas)
- [ ] **Documentação**: 4 arquivos Markdown (README, guides, summary)
- [ ] **Notebook demonstrável**: Jupyter com pipeline completo
- [ ] **Integração SBSE+RL**: Arquitetura clara e modular
- [ ] **4 Objetivos multi-objetivo**: Coverage, diversity, size, faults
- [ ] **Validação estatística**: Mann-Whitney U, effect sizes
- [ ] **Visualizações**: Pareto 2D/3D, comparações, radar charts
- [ ] **Reprodutibilidade**: Script standalone executável

### Arquivos-Chave para Revisão

1. [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) - Entender o projeto
2. [`SBSE_RL_Integration.ipynb`](SBSE_RL_Integration.ipynb) - Ver código rodando
3. [`sbse_optimizer.py`](sbse_optimizer.py) - Core do SBSE
4. [`metrics_calculator.py`](metrics_calculator.py) - Definição dos objetivos

### Tempo Estimado de Revisão

- Leitura rápida: 30 minutos (EXECUTIVE_SUMMARY + README)
- Revisão completa: 2 horas (documentação + código)
- Executar notebook: 15 minutos

---

## 📞 Suporte

### Dúvidas?

1. Verifique [`README.md`](README.md) - Documentação completa
2. Veja [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) - Troubleshooting
3. Execute exemplos em `example_full_pipeline.py`
4. Contate: [seu-email]@[universidade].br

### Reportar Problemas

- GitHub Issues: [link-do-repo]
- Email: [seu-email]

---

## 🏆 Resumo

```
📂 sbse_prototype/
│
├── 📖 EXECUTIVE_SUMMARY.md      ← Comece aqui!
├── 📖 README.md                 ← Documentação completa
├── 📖 INTEGRATION_GUIDE.md      ← Como integrar
├── 📖 INDEX.md                  ← Este arquivo
│
├── 💻 test_case_representation.py
├── 💻 metrics_calculator.py
├── 💻 sbse_optimizer.py
├── 💻 statistical_analysis.py
├── 💻 visualization.py
│
├── 📓 SBSE_RL_Integration.ipynb  ← Execute isto!
├── 📓 example_full_pipeline.py
│
└── 📦 requirements_sbse.txt
```

**Total**: 9 arquivos Python + 4 Markdown + 1 Notebook + 1 Requirements = **15 arquivos**

---

**Boa sorte com seu projeto! 🎉**

*Última atualização: Dezembro 2025*
