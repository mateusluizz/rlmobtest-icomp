#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SBSE Optimizer Module
Otimização multi-objetivo de casos de teste usando NSGA-II/SPEA2
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import json
import time

from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.algorithms.moo.spea2 import SPEA2
from pymoo.algorithms.moo.moead import MOEAD
from pymoo.core.problem import Problem
from pymoo.core.result import Result
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import IntegerRandomSampling
from pymoo.optimize import minimize
from pymoo.util.ref_dirs import get_reference_directions

from test_case_representation import TestCase, TestSuite
from metrics_calculator import MetricsCalculator, ObjectiveMetrics


class TestSuiteOptimizationProblem(Problem):
    """
    Define o problema de otimização multi-objetivo para suítes de teste.

    Objetivos (todos para MINIMIZAR após transformação):
    1. Cobertura (negada para maximizar)
    2. Diversidade (negada para maximizar)
    3. Tamanho da suíte (minimizar)
    4. Taxa de detecção de falhas (negada para maximizar)
    """

    def __init__(
        self,
        test_cases_pool: List[TestCase],
        min_suite_size: int = 1,
        max_suite_size: int = None
    ):
        """
        Args:
            test_cases_pool: Pool de casos de teste disponíveis
            min_suite_size: Tamanho mínimo da suíte
            max_suite_size: Tamanho máximo da suíte
        """
        self.test_cases_pool = test_cases_pool
        self.n_test_cases = len(test_cases_pool)

        if max_suite_size is None:
            max_suite_size = self.n_test_cases

        self.min_suite_size = min_suite_size
        self.max_suite_size = max_suite_size

        self.metrics_calculator = MetricsCalculator(normalize=False)

        # Cache para métricas já calculadas
        self._metrics_cache = {}

        # Definir problema:
        # - n_var: número de variáveis = número de TCs no pool (seleção binária)
        # - n_obj: número de objetivos = 4
        # - xl, xu: limites (0 ou 1 para cada TC)
        super().__init__(
            n_var=self.n_test_cases,
            n_obj=4,
            n_constr=0,
            xl=0,
            xu=1,
            vtype=int
        )

    def _evaluate(self, X, out, *args, **kwargs):
        """
        Avalia soluções.

        X: array (pop_size, n_var) onde cada linha é uma solução binária
           indicando quais TCs estão incluídos na suíte
        """
        objectives = []

        for solution in X:
            # Criar suíte a partir da solução
            suite = self._solution_to_suite(solution)

            # Calcular métricas
            metrics = self.metrics_calculator.calculate_all_metrics(suite)

            # Adicionar objetivos
            objectives.append(metrics.to_objectives_array())

        out["F"] = np.array(objectives)

    def _solution_to_suite(self, solution: np.ndarray) -> TestSuite:
        """
        Converte solução binária em TestSuite.

        Args:
            solution: Array binário indicando TCs selecionados

        Returns:
            TestSuite com TCs selecionados
        """
        # Criar hash da solução para cache
        solution_hash = hash(solution.tobytes())

        if solution_hash in self._metrics_cache:
            return self._metrics_cache[solution_hash]

        # Selecionar TCs onde solution[i] == 1
        selected_indices = np.where(solution == 1)[0]

        suite = TestSuite(name="OptimizedSuite")
        for idx in selected_indices:
            suite.add_test_case(self.test_cases_pool[idx])

        # Cachear
        self._metrics_cache[solution_hash] = suite

        return suite

    def clear_cache(self):
        """Limpa o cache de métricas."""
        self._metrics_cache.clear()


class SBSEOptimizer:
    """
    Otimizador SBSE para suítes de teste.

    Suporta múltiplos algoritmos:
    - NSGA-II (bi-objetivo e tri-objetivo)
    - NSGA-III (many-objective, 4+ objetivos)
    - SPEA2 (alternativa ao NSGA-II)
    - MOEA/D (decomposição)
    """

    def __init__(
        self,
        algorithm: str = "nsga2",
        population_size: int = 100,
        n_generations: int = 50,
        seed: int = 42
    ):
        """
        Args:
            algorithm: Algoritmo a usar ("nsga2", "nsga3", "spea2", "moead")
            population_size: Tamanho da população
            n_generations: Número de gerações
            seed: Seed para reprodutibilidade
        """
        self.algorithm_name = algorithm.lower()
        self.population_size = population_size
        self.n_generations = n_generations
        self.seed = seed

        self.problem = None
        self.algorithm = None
        self.result: Optional[Result] = None

        # Histórico de execução
        self.execution_time = 0.0
        self.convergence_history = []

    def setup_problem(
        self,
        test_cases: List[TestCase],
        min_suite_size: int = 1,
        max_suite_size: int = None
    ):
        """
        Configura o problema de otimização.

        Args:
            test_cases: Pool de casos de teste
            min_suite_size: Tamanho mínimo da suíte
            max_suite_size: Tamanho máximo da suíte
        """
        self.problem = TestSuiteOptimizationProblem(
            test_cases_pool=test_cases,
            min_suite_size=min_suite_size,
            max_suite_size=max_suite_size
        )

        # Configurar algoritmo
        self._setup_algorithm()

    def _setup_algorithm(self):
        """Configura o algoritmo de otimização."""
        # Operadores genéticos
        crossover = SBX(prob=0.9, eta=15)
        mutation = PM(prob=1.0/self.problem.n_var, eta=20)
        sampling = IntegerRandomSampling()

        if self.algorithm_name == "nsga2":
            self.algorithm = NSGA2(
                pop_size=self.population_size,
                sampling=sampling,
                crossover=crossover,
                mutation=mutation,
                eliminate_duplicates=True
            )

        elif self.algorithm_name == "nsga3":
            # NSGA-III requer direções de referência
            ref_dirs = get_reference_directions(
                "das-dennis",
                n_dim=self.problem.n_obj,
                n_partitions=12
            )
            self.algorithm = NSGA3(
                ref_dirs=ref_dirs,
                sampling=sampling,
                crossover=crossover,
                mutation=mutation,
                eliminate_duplicates=True
            )

        elif self.algorithm_name == "spea2":
            self.algorithm = SPEA2(
                pop_size=self.population_size,
                sampling=sampling,
                crossover=crossover,
                mutation=mutation,
                eliminate_duplicates=True
            )

        elif self.algorithm_name == "moead":
            ref_dirs = get_reference_directions(
                "das-dennis",
                n_dim=self.problem.n_obj,
                n_partitions=12
            )
            self.algorithm = MOEAD(
                ref_dirs=ref_dirs,
                n_neighbors=15,
                prob_neighbor_mating=0.7,
                sampling=sampling,
                crossover=crossover,
                mutation=mutation
            )

        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm_name}")

    def optimize(self, verbose: bool = True) -> Result:
        """
        Executa a otimização.

        Args:
            verbose: Se True, imprime progresso

        Returns:
            Resultado da otimização (Pymoo Result object)
        """
        if self.problem is None or self.algorithm is None:
            raise RuntimeError("Problem not set up. Call setup_problem() first.")

        if verbose:
            print(f"🚀 Starting {self.algorithm_name.upper()} optimization...")
            print(f"   Population: {self.population_size}")
            print(f"   Generations: {self.n_generations}")
            print(f"   Test cases in pool: {self.problem.n_test_cases}")
            print()

        start_time = time.time()

        # Executar otimização
        self.result = minimize(
            self.problem,
            self.algorithm,
            ('n_gen', self.n_generations),
            seed=self.seed,
            verbose=verbose,
            save_history=True
        )

        self.execution_time = time.time() - start_time

        if verbose:
            print(f"\n✅ Optimization complete in {self.execution_time:.2f}s")
            print(f"   Pareto front size: {len(self.result.F)}")
            print()

        return self.result

    def get_pareto_front(self) -> List[Tuple[TestSuite, ObjectiveMetrics]]:
        """
        Retorna a fronteira de Pareto com as suítes otimizadas.

        Returns:
            Lista de tuplas (TestSuite, ObjectiveMetrics)
        """
        if self.result is None:
            raise RuntimeError("No optimization result. Call optimize() first.")

        pareto_solutions = []
        calc = MetricsCalculator(normalize=False)

        for solution in self.result.X:
            # Converter solução para suíte
            suite = self.problem._solution_to_suite(solution)

            # Calcular métricas
            metrics = calc.calculate_all_metrics(suite)

            pareto_solutions.append((suite, metrics))

        return pareto_solutions

    def select_best_solution(
        self,
        criterion: str = "coverage"
    ) -> Tuple[TestSuite, ObjectiveMetrics]:
        """
        Seleciona a melhor solução da fronteira de Pareto.

        Args:
            criterion: Critério de seleção
                - "coverage": Maximizar cobertura
                - "diversity": Maximizar diversidade
                - "balanced": Solução mais equilibrada
                - "minimal": Menor suíte com boa cobertura

        Returns:
            Tupla (TestSuite, ObjectiveMetrics)
        """
        pareto_front = self.get_pareto_front()

        if criterion == "coverage":
            # Maior cobertura
            best = max(pareto_front, key=lambda x: x[1].coverage)

        elif criterion == "diversity":
            # Maior diversidade
            best = max(pareto_front, key=lambda x: x[1].diversity)

        elif criterion == "balanced":
            # Melhor trade-off (menor distância euclidiana ao ponto ideal)
            # Normalizar objetivos primeiro
            coverages = [m.coverage for s, m in pareto_front]
            diversities = [m.diversity for s, m in pareto_front]
            sizes = [m.suite_size for s, m in pareto_front]

            max_cov = max(coverages)
            max_div = max(diversities)
            min_size = min(sizes)

            def score(metrics):
                norm_cov = metrics.coverage / max_cov if max_cov > 0 else 0
                norm_div = metrics.diversity / max_div if max_div > 0 else 0
                norm_size = min_size / metrics.suite_size if metrics.suite_size > 0 else 0

                # Distância ao ideal (1, 1, 1)
                return np.sqrt(
                    (1 - norm_cov)**2 +
                    (1 - norm_div)**2 +
                    (1 - norm_size)**2
                )

            best = min(pareto_front, key=lambda x: score(x[1]))

        elif criterion == "minimal":
            # Menor suíte com cobertura >= 80% da máxima
            max_coverage = max(m.coverage for s, m in pareto_front)
            threshold = 0.8 * max_coverage

            candidates = [
                (s, m) for s, m in pareto_front
                if m.coverage >= threshold
            ]

            if candidates:
                best = min(candidates, key=lambda x: x[1].suite_size)
            else:
                best = pareto_front[0]

        else:
            raise ValueError(f"Unknown criterion: {criterion}")

        return best

    def get_optimization_summary(self) -> Dict:
        """
        Retorna resumo da otimização.

        Returns:
            Dicionário com estatísticas
        """
        if self.result is None:
            return {}

        pareto_front = self.get_pareto_front()

        # Estatísticas dos objetivos
        coverages = [m.coverage for s, m in pareto_front]
        diversities = [m.diversity for s, m in pareto_front]
        sizes = [m.suite_size for s, m in pareto_front]
        fault_rates = [m.fault_detection_rate for s, m in pareto_front]

        summary = {
            "algorithm": self.algorithm_name,
            "execution_time": self.execution_time,
            "population_size": self.population_size,
            "generations": self.n_generations,
            "pareto_front_size": len(pareto_front),
            "objectives": {
                "coverage": {
                    "min": min(coverages),
                    "max": max(coverages),
                    "mean": np.mean(coverages),
                    "std": np.std(coverages)
                },
                "diversity": {
                    "min": min(diversities),
                    "max": max(diversities),
                    "mean": np.mean(diversities),
                    "std": np.std(diversities)
                },
                "suite_size": {
                    "min": min(sizes),
                    "max": max(sizes),
                    "mean": np.mean(sizes),
                    "std": np.std(sizes)
                },
                "fault_detection_rate": {
                    "min": min(fault_rates),
                    "max": max(fault_rates),
                    "mean": np.mean(fault_rates),
                    "std": np.std(fault_rates)
                }
            }
        }

        return summary

    def save_results(self, output_dir: Path, run_name: str = "optimization"):
        """
        Salva resultados da otimização.

        Args:
            output_dir: Diretório de saída
            run_name: Nome da execução
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Salvar fronteira de Pareto
        pareto_front = self.get_pareto_front()

        pareto_data = []
        for idx, (suite, metrics) in enumerate(pareto_front):
            suite_dict = suite.to_dict()
            suite_dict['pareto_rank'] = idx
            suite_dict['objectives'] = metrics.to_dict()
            pareto_data.append(suite_dict)

        pareto_file = output_dir / f"{run_name}_pareto_front.json"
        with open(pareto_file, 'w') as f:
            json.dump(pareto_data, f, indent=2)

        print(f"✅ Pareto front saved: {pareto_file}")

        # Salvar resumo
        summary = self.get_optimization_summary()
        summary_file = output_dir / f"{run_name}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"✅ Summary saved: {summary_file}")

        # Salvar objetivos (para plotting)
        objectives_array = self.result.F
        objectives_file = output_dir / f"{run_name}_objectives.npy"
        np.save(objectives_file, objectives_array)

        print(f"✅ Objectives array saved: {objectives_file}")


if __name__ == "__main__":
    # Exemplo de uso
    from test_case_representation import TestCase, Action

    print("SBSE Optimizer Module")
    print("=" * 60)

    # Criar pool de test cases exemplo
    test_cases = []

    for i in range(20):
        tc = TestCase(
            id=f"TC_{i:03d}",
            actions=[
                Action(j, "click", f"button_{j}")
                for j in range(np.random.randint(5, 15))
            ],
            coverage={f"Class.java:{k}" for k in range(i*5, (i+1)*5)},
            activities_visited={f"Activity{k}" for k in range(i % 3 + 1)},
            crashes=np.random.randint(0, 2)
        )
        test_cases.append(tc)

    print(f"Created {len(test_cases)} test cases")
    print()

    # Criar otimizador
    optimizer = SBSEOptimizer(
        algorithm="nsga2",
        population_size=50,
        n_generations=30
    )

    # Configurar problema
    optimizer.setup_problem(test_cases, min_suite_size=5, max_suite_size=15)

    # Otimizar
    result = optimizer.optimize(verbose=True)

    # Resumo
    summary = optimizer.get_optimization_summary()
    print("Summary:")
    print(f"  Pareto front size: {summary['pareto_front_size']}")
    print(f"  Execution time: {summary['execution_time']:.2f}s")
    print(f"  Coverage range: {summary['objectives']['coverage']['min']:.1f} - {summary['objectives']['coverage']['max']:.1f}")
    print(f"  Suite size range: {summary['objectives']['suite_size']['min']} - {summary['objectives']['suite_size']['max']}")
    print()

    # Selecionar melhor solução
    best_suite, best_metrics = optimizer.select_best_solution(criterion="balanced")
    print(f"Best solution (balanced):")
    print(f"  Size: {best_metrics.suite_size}")
    print(f"  Coverage: {best_metrics.coverage:.2f}")
    print(f"  Diversity: {best_metrics.diversity:.2f}")
    print(f"  Fault rate: {best_metrics.fault_detection_rate:.2f}")
