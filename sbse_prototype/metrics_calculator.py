#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metrics Calculator Module
Calcula métricas para avaliação de suítes de teste
"""

import numpy as np
from typing import List, Set, Dict, Tuple
from dataclasses import dataclass
from test_case_representation import TestCase, TestSuite


@dataclass
class ObjectiveMetrics:
    """Métricas calculadas para otimização multi-objetivo."""

    coverage: float  # Maximizar
    diversity: float  # Maximizar
    suite_size: int  # Minimizar
    fault_detection_rate: float  # Maximizar (taxa de crashes)

    # Métricas adicionais
    total_actions: int = 0
    execution_time: float = 0.0
    redundancy: float = 0.0
    activities_covered: int = 0

    def to_objectives_array(self) -> np.ndarray:
        """
        Converte para array de objetivos para Pymoo.
        Formato: [coverage, diversity, size, fault_rate]

        IMPORTANTE: Pymoo minimiza por padrão, então:
        - Cobertura e diversidade são negadas (queremos maximizar)
        - Tamanho e redundância são mantidos (queremos minimizar)
        """
        return np.array(
            [
                -self.coverage,  # Negar para maximizar
                -self.diversity,  # Negar para maximizar
                self.suite_size,  # Minimizar
                -self.fault_detection_rate,  # Negar para maximizar
            ]
        )

    def to_dict(self) -> dict:
        return {
            "coverage": self.coverage,
            "diversity": self.diversity,
            "suite_size": self.suite_size,
            "fault_detection_rate": self.fault_detection_rate,
            "total_actions": self.total_actions,
            "execution_time": self.execution_time,
            "redundancy": self.redundancy,
            "activities_covered": self.activities_covered,
        }


class MetricsCalculator:
    """Calculadora de métricas para suítes de teste."""

    def __init__(self, normalize: bool = True):
        """
        Args:
            normalize: Se True, normaliza métricas para [0, 1]
        """
        self.normalize = normalize
        self.normalization_params = {}

    def calculate_coverage(self, suite: TestSuite) -> float:
        """
        Calcula cobertura da suíte.

        Métricas consideradas:
        - Número de linhas/métodos únicos cobertos
        - Número de activities visitadas
        """
        # Cobertura de código
        code_coverage = suite.get_coverage_size()

        # Cobertura de activities
        activity_coverage = len(suite.get_all_activities())

        # Score combinado (pode ajustar pesos)
        coverage_score = code_coverage + (
            activity_coverage * 10
        )  # Activities valem mais

        return float(coverage_score)

    def calculate_diversity(self, suite: TestSuite) -> float:
        """
        Calcula diversidade da suíte usando Jaccard Distance.

        Quanto maior, mais diversa é a suíte.
        """
        if len(suite.test_cases) < 2:
            return 0.0

        # Diversidade baseada em ações
        action_diversity = suite.calculate_diversity()

        # Diversidade baseada em activities
        activity_diversity = self._calculate_activity_diversity(suite)

        # Combinar métricas (média ponderada)
        total_diversity = (0.7 * action_diversity) + (0.3 * activity_diversity)

        return total_diversity

    def _calculate_activity_diversity(self, suite: TestSuite) -> float:
        """Calcula diversidade baseada em activities visitadas."""
        if len(suite.test_cases) < 2:
            return 0.0

        similarities = []
        for i, tc1 in enumerate(suite.test_cases):
            for tc2 in suite.test_cases[i + 1 :]:
                act1 = tc1.activities_visited
                act2 = tc2.activities_visited

                if not act1 or not act2:
                    continue

                intersection = len(act1 & act2)
                union = len(act1 | act2)

                if union > 0:
                    similarity = intersection / union
                    similarities.append(similarity)

        if not similarities:
            return 0.0

        avg_similarity = sum(similarities) / len(similarities)
        return 1.0 - avg_similarity

    def calculate_suite_size(self, suite: TestSuite) -> int:
        """
        Calcula tamanho da suíte.

        Pode ser:
        - Número de test cases (simples)
        - Número total de ações (mais preciso)
        """
        # Usando número de test cases
        return suite.get_size()

    def calculate_fault_detection_rate(self, suite: TestSuite) -> float:
        """
        Calcula taxa de detecção de falhas.

        Métricas:
        - Porcentagem de TCs que encontraram crashes
        - Número total de crashes
        """
        if not suite.test_cases:
            return 0.0

        # Taxa de TCs com crash
        crash_rate = suite.get_crash_detection_rate()

        # Número total de crashes (normalizado)
        total_crashes = suite.get_total_crashes()
        normalized_crashes = min(total_crashes / len(suite.test_cases), 1.0)

        # Combinar métricas
        fault_score = (0.6 * crash_rate) + (0.4 * normalized_crashes)

        return fault_score

    def calculate_all_metrics(self, suite: TestSuite) -> ObjectiveMetrics:
        """
        Calcula todas as métricas para uma suíte.

        Returns:
            ObjectiveMetrics com todos os valores calculados
        """
        coverage = self.calculate_coverage(suite)
        diversity = self.calculate_diversity(suite)
        suite_size = self.calculate_suite_size(suite)
        fault_rate = self.calculate_fault_detection_rate(suite)

        # Métricas adicionais
        total_actions = suite.get_total_actions()
        execution_time = suite.get_total_duration()
        redundancy = suite.calculate_redundancy()
        activities = len(suite.get_all_activities())

        metrics = ObjectiveMetrics(
            coverage=coverage,
            diversity=diversity,
            suite_size=suite_size,
            fault_detection_rate=fault_rate,
            total_actions=total_actions,
            execution_time=execution_time,
            redundancy=redundancy,
            activities_covered=activities,
        )

        if self.normalize:
            metrics = self._normalize_metrics(metrics)

        return metrics

    def _normalize_metrics(self, metrics: ObjectiveMetrics) -> ObjectiveMetrics:
        """Normaliza métricas para [0, 1] (se parâmetros disponíveis)."""
        # Implementação simplificada - pode ser expandida
        return metrics

    def calculate_hypervolume(
        self, pareto_front: List[ObjectiveMetrics], reference_point: np.ndarray
    ) -> float:
        """
        Calcula o hypervolume da fronteira de Pareto.

        O hypervolume mede a qualidade da fronteira: quanto maior, melhor.

        Args:
            pareto_front: Lista de soluções da fronteira de Pareto
            reference_point: Ponto de referência (pior caso)

        Returns:
            Valor do hypervolume
        """
        if not pareto_front:
            return 0.0

        # Converter para array numpy
        points = np.array([m.to_objectives_array() for m in pareto_front])

        # Usar biblioteca pygmo para cálculo preciso
        try:
            from pymoo.indicators.hv import HV

            hv = HV(ref_point=reference_point)
            return hv(points)
        except ImportError:
            # Fallback para cálculo aproximado
            return self._approximate_hypervolume(points, reference_point)

    def _approximate_hypervolume(
        self, points: np.ndarray, reference_point: np.ndarray
    ) -> float:
        """Cálculo aproximado de hypervolume (2D/3D)."""
        # Implementação simplificada para 2D
        if points.shape[1] == 2:
            # Ordenar pontos
            sorted_points = points[points[:, 0].argsort()]

            hv = 0.0
            for i, point in enumerate(sorted_points):
                if i == 0:
                    width = reference_point[0] - point[0]
                else:
                    width = sorted_points[i - 1][0] - point[0]

                height = reference_point[1] - point[1]
                hv += width * height

            return hv
        else:
            # Para 3D+, retornar volume da caixa delimitadora
            dominated_volume = np.prod(reference_point - points.min(axis=0))
            return float(dominated_volume)

    def calculate_spread(self, pareto_front: List[ObjectiveMetrics]) -> float:
        """
        Calcula o spread (espalhamento) da fronteira de Pareto.

        Mede quão uniformemente distribuídas estão as soluções.
        Valores menores indicam melhor distribuição.

        Returns:
            Valor de spread [0, inf), sendo 0 = distribuição perfeita
        """
        if len(pareto_front) < 2:
            return 0.0

        points = np.array([m.to_objectives_array() for m in pareto_front])

        # Calcular distâncias entre pontos consecutivos
        distances = []
        for i in range(len(points) - 1):
            dist = np.linalg.norm(points[i] - points[i + 1])
            distances.append(dist)

        if not distances:
            return 0.0

        # Spread = desvio padrão das distâncias / média
        mean_dist = np.mean(distances)
        std_dist = np.std(distances)

        if mean_dist == 0:
            return 0.0

        return std_dist / mean_dist

    def compare_suites(
        self, suite1: TestSuite, suite2: TestSuite
    ) -> Dict[str, Dict[str, float]]:
        """
        Compara duas suítes de teste.

        Args:
            suite1: Primeira suíte (ex: baseline)
            suite2: Segunda suíte (ex: otimizada)

        Returns:
            Dicionário com comparação de métricas
        """
        metrics1 = self.calculate_all_metrics(suite1)
        metrics2 = self.calculate_all_metrics(suite2)

        comparison = {}

        for metric_name in [
            "coverage",
            "diversity",
            "suite_size",
            "fault_detection_rate",
        ]:
            val1 = getattr(metrics1, metric_name)
            val2 = getattr(metrics2, metric_name)

            # Calcular diferença percentual
            if val1 != 0:
                improvement = ((val2 - val1) / val1) * 100
            else:
                improvement = 100 if val2 > 0 else 0

            comparison[metric_name] = {
                "suite1": val1,
                "suite2": val2,
                "difference": val2 - val1,
                "improvement_percent": improvement,
            }

        return comparison


# =============================================================================
# QUALITY INDICATORS
# =============================================================================


class QualityIndicators:
    """Indicadores de qualidade para avaliação de algoritmos multi-objetivo."""

    @staticmethod
    def calculate_generational_distance(
        approximation_set: np.ndarray, pareto_front: np.ndarray, p: int = 2
    ) -> float:
        """
        Calcula Generational Distance (GD).

        Mede a distância média da aproximação até a fronteira verdadeira.
        Valores menores são melhores.

        Args:
            approximation_set: Soluções aproximadas
            pareto_front: Fronteira de Pareto verdadeira
            p: Ordem da distância (default: 2 = Euclidiana)

        Returns:
            Valor de GD
        """
        if len(approximation_set) == 0 or len(pareto_front) == 0:
            return np.inf

        distances = []
        for point in approximation_set:
            # Encontrar ponto mais próximo na fronteira verdadeira
            min_dist = min(
                np.linalg.norm(point - pf_point, ord=p) for pf_point in pareto_front
            )
            distances.append(min_dist)

        gd = (sum(d**p for d in distances) / len(distances)) ** (1 / p)
        return gd

    @staticmethod
    def calculate_inverted_generational_distance(
        approximation_set: np.ndarray, pareto_front: np.ndarray, p: int = 2
    ) -> float:
        """
        Calcula Inverted Generational Distance (IGD).

        Mede tanto convergência quanto diversidade.
        Valores menores são melhores.

        Args:
            approximation_set: Soluções aproximadas
            pareto_front: Fronteira de Pareto verdadeira
            p: Ordem da distância

        Returns:
            Valor de IGD
        """
        if len(approximation_set) == 0 or len(pareto_front) == 0:
            return np.inf

        distances = []
        for pf_point in pareto_front:
            # Encontrar ponto mais próximo na aproximação
            min_dist = min(
                np.linalg.norm(pf_point - point, ord=p) for point in approximation_set
            )
            distances.append(min_dist)

        igd = (sum(d**p for d in distances) / len(distances)) ** (1 / p)
        return igd


if __name__ == "__main__":
    # Exemplo de uso
    from test_case_representation import TestCase, TestSuite, Action

    print("Metrics Calculator Module")
    print("=" * 60)

    # Criar suíte exemplo
    suite = TestSuite(name="Example")

    # TC 1 - Cobertura alta, muitas ações
    tc1 = TestCase(
        id="TC_001",
        actions=[Action(i, "click", f"button_{i}") for i in range(10)],
        coverage={f"Class.java:{i}" for i in range(20)},
        activities_visited={"Login", "Main", "Settings"},
        crashes=1,
    )

    # TC 2 - Cobertura média, poucas ações
    tc2 = TestCase(
        id="TC_002",
        actions=[Action(i, "swipe", f"screen_{i}") for i in range(5)],
        coverage={f"Class.java:{i}" for i in range(10, 25)},
        activities_visited={"Main", "Profile"},
        crashes=0,
    )

    suite.add_test_case(tc1)
    suite.add_test_case(tc2)

    # Calcular métricas
    calc = MetricsCalculator()
    metrics = calc.calculate_all_metrics(suite)

    print("Métricas calculadas:")
    print(f"  Coverage: {metrics.coverage:.2f}")
    print(f"  Diversity: {metrics.diversity:.2f}")
    print(f"  Suite Size: {metrics.suite_size}")
    print(f"  Fault Detection Rate: {metrics.fault_detection_rate:.2f}")
    print(f"  Total Actions: {metrics.total_actions}")
    print(f"  Activities Covered: {metrics.activities_covered}")
    print()

    print("Array de objetivos (para Pymoo):")
    print(metrics.to_objectives_array())
