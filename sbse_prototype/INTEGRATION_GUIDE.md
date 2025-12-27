# 🔗 Guia de Integração SBSE + RLMobTest

## Como Integrar o Framework SBSE ao RLMobTest Existente

---

## 📋 Visão Geral da Integração

Este guia mostra como integrar o framework SBSE ao pipeline RLMobTest existente para criar um sistema completo de geração e otimização de casos de teste.

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   RLMobTest     │────>│  SBSE        │────>│  Suíte          │
│   (main.py)     │     │  Optimizer   │     │  Otimizada      │
│                 │     │              │     │                 │
│ • DQN Training  │     │ • NSGA-II    │     │ • 60% menor     │
│ • TC Generation │     │ • Multi-obj  │     │ • Mesma cobertu │
│ • Coverage      │     │ • Pareto     │     │ • Maior diversi │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

---

## 🚀 Opções de Integração

### Opção 1: Pós-Processamento (Recomendado para começar)

**Quando usar**: Primeiro projeto, validação de conceito

**Como funciona**:
1. Executar RLMobTest normalmente
2. Coletar casos de teste gerados
3. Aplicar SBSE para otimizar
4. Usar suíte otimizada

**Vantagens**:
- ✅ Não modifica código RL existente
- ✅ Fácil de implementar
- ✅ Pode testar diferentes configurações SBSE

**Código**:

```python
# 1. Treinar RL
python main.py --time 3600

# 2. Otimizar com SBSE
python sbse_prototype/optimize_rl_output.py \
    --rl-output output/test_cases \
    --metrics output/metrics/metrics_latest.json \
    --algorithm nsga2
```

### Opção 2: Integração Direta no main.py

**Quando usar**: Para uso em produção contínua

**Como funciona**:
- Adicionar chamada SBSE ao final do treinamento RL
- Automatizar todo o pipeline

**Modificação no main.py**:

```python
# No final da função run() em main.py
# Após linha 1140 (fim do treinamento)

def run(mode="improved", max_time=None, max_episodes=None):
    # ... código existente ...

    finally:
        # ... salvamento de checkpoint e métricas ...

        # NOVO: Otimização SBSE
        if ENABLE_SBSE_OPTIMIZATION:  # Flag configurável
            console.print("\n[cyan]🔬 Starting SBSE optimization...[/cyan]")
            from sbse_prototype.integration import optimize_test_suite

            optimized_suite = optimize_test_suite(
                test_cases_dir=TEST_CASES_PATH,
                metrics_file=METRICS_PATH / f"metrics_{run_id}.json",
                output_dir=Path("output/sbse_optimized"),
                algorithm="nsga2",
                population=100,
                generations=50
            )

            console.print(f"[green]✅ SBSE optimization complete![/green]")
            console.print(f"   Original: {len(test_cases)} TCs")
            console.print(f"   Optimized: {len(optimized_suite.test_cases)} TCs")
```

### Opção 3: Co-evolução (Avançado)

**Quando usar**: Pesquisa avançada, publicações

**Como funciona**:
- RL e SBSE rodam simultaneamente
- SBSE guia exploração do RL via reward shaping

**Complexidade**: Alta - requer modificação da reward function

---

## 📦 Arquivos Necessários

### 1. Copiar Módulos SBSE

```bash
# Copiar pasta sbse_prototype para o projeto
cp -r sbse_prototype /path/to/rlmobtest-icomp/

# Ou mover para dentro do projeto
mv sbse_prototype/* rlmobtest-icomp/sbse/
```

### 2. Instalar Dependências

```bash
cd rlmobtest-icomp
pip install -r sbse_prototype/requirements_sbse.txt
```

### 3. Criar Script de Integração

```python
# sbse_prototype/integration.py

from pathlib import Path
from test_case_representation import create_test_suite_from_rl_output
from sbse_optimizer import SBSEOptimizer

def optimize_test_suite(
    test_cases_dir: Path,
    metrics_file: Path,
    output_dir: Path,
    algorithm: str = "nsga2",
    population: int = 100,
    generations: int = 50
):
    """
    Otimiza suíte de teste gerada pelo RL.

    Args:
        test_cases_dir: Diretório com TCs do RL
        metrics_file: Arquivo JSON de métricas
        output_dir: Onde salvar resultados
        algorithm: Algoritmo SBSE
        population: Tamanho da população
        generations: Número de gerações

    Returns:
        TestSuite otimizada
    """
    # 1. Carregar TCs do RL
    suite = create_test_suite_from_rl_output(
        test_cases_dir,
        metrics_file,
        name="RL_Generated"
    )

    print(f"📥 Loaded {len(suite.test_cases)} test cases from RL")

    # 2. Otimizar com SBSE
    optimizer = SBSEOptimizer(
        algorithm=algorithm,
        population_size=population,
        n_generations=generations
    )

    optimizer.setup_problem(suite.test_cases)
    optimizer.optimize(verbose=True)

    # 3. Selecionar melhor solução
    best_suite, best_metrics = optimizer.select_best_solution(criterion="balanced")

    # 4. Salvar resultados
    output_dir.mkdir(parents=True, exist_ok=True)
    optimizer.save_results(output_dir, run_name="sbse_optimization")
    best_suite.save(output_dir / "optimized_suite.json")

    return best_suite
```

---

## 🔧 Configuração

### Adicionar ao settings.txt

```
# Existing settings
APK NAME:app.apk
PACKAGE:com.example.app
...

# Novo: SBSE Configuration
SBSE_ENABLED:yes
SBSE_ALGORITHM:nsga2
SBSE_POPULATION:100
SBSE_GENERATIONS:50
```

### Modificar utils/config_reader.py

```python
# Adicionar leitura das configurações SBSE
class ConfRead:
    def read_setting(self):
        # ... código existente ...

        # NOVO: Ler configurações SBSE
        sbse_enabled = lines[7] if len(lines) > 7 else "no"
        sbse_algorithm = lines[8] if len(lines) > 8 else "nsga2"
        sbse_population = int(lines[9]) if len(lines) > 9 else 100
        sbse_generations = int(lines[10]) if len(lines) > 10 else 50

        return {
            # ... existente ...
            "sbse_enabled": sbse_enabled == "yes",
            "sbse_algorithm": sbse_algorithm,
            "sbse_population": sbse_population,
            "sbse_generations": sbse_generations
        }
```

---

## 📊 Exemplo de Uso Completo

### Cenário: Testar App do Google Play

```bash
# 1. Configurar app
nano config/settings.txt
# Editar: APK, PACKAGE, etc.

# 2. Treinar RL
python main.py --time 3600  # 1 hora

# 3. Verificar TCs gerados
ls output/test_cases/
# Esperado: ~50-100 arquivos .txt

# 4. Otimizar com SBSE
python sbse_prototype/example_full_pipeline.py

# 5. Comparar resultados
python sbse_prototype/compare_suites.py \
    --baseline output/test_cases \
    --optimized output/sbse_results/best_suite.json

# 6. Visualizar Pareto front
jupyter notebook sbse_prototype/SBSE_RL_Integration.ipynb
```

---

## 📈 Métricas de Avaliação

### Para seu Artigo/Apresentação

**RQ1: A otimização SBSE melhora a qualidade da suíte?**

Métricas:
- Cobertura (linhas, métodos, activities)
- Diversidade (Jaccard distance)
- Tamanho da suíte
- Taxa de detecção de falhas

**RQ2: A redução de tamanho é estatisticamente significativa?**

Testes:
- Mann-Whitney U Test (p < 0.05)
- Vargha-Delaney A12 (effect size)
- Wilcoxon Signed-Rank (se pareado)

**RQ3: Como SBSE+RL compara com estado da arte?**

Baselines:
- Random sampling
- Greedy selection (por cobertura)
- Apenas RL (sem otimização)
- Sapienz/MOTSD (se disponível)

---

## 🐛 Troubleshooting

### Problema: "No module named 'pymoo'"

```bash
# Solução
pip install pymoo>=0.6.0
```

### Problema: "Optimization takes too long"

```python
# Reduzir população e gerações
optimizer = SBSEOptimizer(
    population_size=50,  # Era 100
    n_generations=25     # Era 50
)
```

### Problema: "Pareto front muito pequeno"

```python
# Aumentar população e gerações
optimizer = SBSEOptimizer(
    population_size=200,
    n_generations=100
)
```

### Problema: "Coverage sempre zero"

**Causa**: Parser de cobertura não implementado

**Solução**:
```python
# Em test_case_representation.py, ajustar _parse_test_case_file()
# para extrair cobertura do formato real do seu output
```

---

## 📝 Checklist de Validação

Antes de apresentar/publicar, verifique:

- [ ] RLMobTest roda sem erros
- [ ] Casos de teste são gerados corretamente
- [ ] SBSE otimiza com sucesso
- [ ] Fronteira de Pareto não está vazia
- [ ] Testes estatísticos mostram significância (p < 0.05)
- [ ] Visualizações estão corretas
- [ ] Redução de tamanho é substancial (>40%)
- [ ] Cobertura é mantida ou melhorada
- [ ] Diversidade aumenta
- [ ] Documentação está completa

---

## 🎓 Para Apresentação Acadêmica

### Estrutura Sugerida

1. **Introdução**
   - Problema: Testes Android são caros
   - Solução: RL gera TCs automaticamente
   - Gap: Muitos TCs redundantes

2. **Proposta**
   - Integrar SBSE para otimizar
   - 4 objetivos simultâneos
   - NSGA-II para Pareto front

3. **Implementação**
   - Framework modular
   - Pymoo + scipy
   - Integração com RLMobTest

4. **Experimentos**
   - N apps do Google Play
   - K execuções independentes
   - Comparação com baselines

5. **Resultados**
   - Redução média de X%
   - Cobertura mantida/melhorada
   - Significância estatística (p < 0.001)
   - Effect size = large

6. **Conclusões**
   - SBSE+RL > apenas RL
   - Framework aplicável a outras ferramentas
   - Código open-source disponível

---

## 🔗 Recursos Adicionais

### Código de Exemplo

- `example_full_pipeline.py`: Pipeline completo standalone
- `SBSE_RL_Integration.ipynb`: Notebook interativo
- `test_case_representation.py`: Estruturas de dados

### Documentação

- `README.md`: Guia geral
- `INTEGRATION_GUIDE.md`: Este arquivo
- Docstrings em todos os módulos

### Suporte

- Issues: [GitHub Issues](https://github.com/seu-usuario/rlmobtest/issues)
- Email: seu-email@universidade.br
- Paper: [Link quando publicado]

---

## 📄 Licença e Citação

### Como Citar

```bibtex
@inproceedings{seu2025sbse,
  title={SBSE+RL: Multi-Objective Test Suite Optimization for Android},
  author={Seu Nome and Coautores},
  booktitle={Conference Name},
  year={2025}
}
```

---

**Boa sorte com seu projeto! 🚀**

Em caso de dúvidas, consulte a documentação ou abra uma issue.

---

*Última atualização: Dezembro 2025*
