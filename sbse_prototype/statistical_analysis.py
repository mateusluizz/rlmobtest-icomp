#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Statistical Analysis Module
Análises estatísticas para validação de resultados SBSE
"""

import numpy as np
from typing import List, Dict, Tuple
from scipy import stats
from dataclasses import dataclass
import pandas as pd


@dataclass
class StatisticalTestResult:
    """Resultado de um teste estatístico."""

    test_name: str
    statistic: float
    p_value: float
    is_significant: bool  # p < 0.05
    effect_size: float
    interpretation: str

    def to_dict(self) -> dict:
        return {
            "test": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.is_significant,
            "effect_size": self.effect_size,
            "interpretation": self.interpretation,
        }


class StatisticalAnalyzer:
    """Análises estatísticas para comparação de suítes."""

    def __init__(self, alpha: float = 0.05):
        """
        Args:
            alpha: Nível de significância (default: 0.05)
        """
        self.alpha = alpha

    def mann_whitney_u_test(
        self, sample1: List[float], sample2: List[float], metric_name: str = "metric"
    ) -> StatisticalTestResult:
        """
        Teste de Mann-Whitney U (Wilcoxon rank-sum test).

        Teste não-paramétrico para comparar duas amostras independentes.
        Útil quando os dados não seguem distribuição normal.

        H0: As distribuições são iguais
        H1: As distribuições são diferentes

        Args:
            sample1: Primeira amostra (ex: baseline)
            sample2: Segunda amostra (ex: otimizada)
            metric_name: Nome da métrica sendo testada

        Returns:
            StatisticalTestResult
        """
        if len(sample1) < 3 or len(sample2) < 3:
            return StatisticalTestResult(
                test_name="Mann-Whitney U",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                interpretation="Insufficient data (n < 3)",
            )

        # Executar teste
        statistic, p_value = stats.mannwhitneyu(
            sample1, sample2, alternative="two-sided"
        )

        # Calcular effect size (rank-biserial correlation)
        n1, n2 = len(sample1), len(sample2)
        effect_size = 1 - (2 * statistic) / (n1 * n2)

        # Interpretar resultado
        is_significant = p_value < self.alpha

        if is_significant:
            if np.median(sample2) > np.median(sample1):
                interpretation = f"Sample 2 is significantly HIGHER than Sample 1 for {metric_name} (p={p_value:.4f})"
            else:
                interpretation = f"Sample 2 is significantly LOWER than Sample 1 for {metric_name} (p={p_value:.4f})"
        else:
            interpretation = (
                f"No significant difference for {metric_name} (p={p_value:.4f})"
            )

        return StatisticalTestResult(
            test_name="Mann-Whitney U",
            statistic=statistic,
            p_value=p_value,
            is_significant=is_significant,
            effect_size=effect_size,
            interpretation=interpretation,
        )

    def wilcoxon_signed_rank_test(
        self, sample1: List[float], sample2: List[float], metric_name: str = "metric"
    ) -> StatisticalTestResult:
        """
        Teste de Wilcoxon Signed-Rank.

        Teste não-paramétrico para comparar duas amostras PAREADAS.
        Útil para comparar antes/depois ou mesmas instâncias processadas diferentemente.

        H0: A diferença mediana é zero
        H1: A diferença mediana não é zero

        Args:
            sample1: Primeira amostra
            sample2: Segunda amostra (pareada com sample1)
            metric_name: Nome da métrica

        Returns:
            StatisticalTestResult
        """
        if len(sample1) != len(sample2):
            raise ValueError("Samples must have same length for paired test")

        if len(sample1) < 3:
            return StatisticalTestResult(
                test_name="Wilcoxon Signed-Rank",
                statistic=0.0,
                p_value=1.0,
                is_significant=False,
                effect_size=0.0,
                interpretation="Insufficient data (n < 3)",
            )

        # Executar teste
        statistic, p_value = stats.wilcoxon(sample1, sample2)

        # Effect size (r = Z / sqrt(N))
        n = len(sample1)
        z_score = stats.norm.ppf(1 - p_value / 2)  # Aproximação
        effect_size = z_score / np.sqrt(n)

        # Interpretar
        is_significant = p_value < self.alpha

        if is_significant:
            diff = np.median(np.array(sample2) - np.array(sample1))
            if diff > 0:
                interpretation = f"Sample 2 is significantly HIGHER than Sample 1 for {metric_name} (p={p_value:.4f})"
            else:
                interpretation = f"Sample 2 is significantly LOWER than Sample 1 for {metric_name} (p={p_value:.4f})"
        else:
            interpretation = (
                f"No significant difference for {metric_name} (p={p_value:.4f})"
            )

        return StatisticalTestResult(
            test_name="Wilcoxon Signed-Rank",
            statistic=statistic,
            p_value=p_value,
            is_significant=is_significant,
            effect_size=effect_size,
            interpretation=interpretation,
        )

    def vargha_delaney_a12(self, sample1: List[float], sample2: List[float]) -> float:
        """
        Calcula Vargha-Delaney A12 effect size.

        Medida não-paramétrica de effect size.
        Interpretação:
        - A12 = 0.5: Sem diferença
        - A12 > 0.5: Sample2 > Sample1
        - A12 < 0.5: Sample2 < Sample1
        - |A12 - 0.5| < 0.06: Negligible
        - |A12 - 0.5| < 0.14: Small
        - |A12 - 0.5| < 0.21: Medium
        - |A12 - 0.5| >= 0.21: Large

        Args:
            sample1: Primeira amostra
            sample2: Segunda amostra

        Returns:
            A12 value [0, 1]
        """
        n1, n2 = len(sample1), len(sample2)
        r1 = 0

        for x in sample1:
            r1 += sum(1 for y in sample2 if x > y)
            r1 += 0.5 * sum(1 for y in sample2 if x == y)

        a12 = r1 / (n1 * n2)
        return a12

    def cohen_d(self, sample1: List[float], sample2: List[float]) -> float:
        """
        Calcula Cohen's d effect size.

        Medida paramétrica de effect size.
        Interpretação:
        - |d| < 0.2: Small
        - |d| < 0.5: Medium
        - |d| >= 0.8: Large

        Args:
            sample1: Primeira amostra
            sample2: Segunda amostra

        Returns:
            Cohen's d value
        """
        n1, n2 = len(sample1), len(sample2)
        var1, var2 = np.var(sample1, ddof=1), np.var(sample2, ddof=1)

        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

        if pooled_std == 0:
            return 0.0

        return (np.mean(sample2) - np.mean(sample1)) / pooled_std

    def interpret_effect_size(
        self, effect_size: float, measure: str = "cohen_d"
    ) -> str:
        """
        Interpreta o tamanho do efeito.

        Args:
            effect_size: Valor do effect size
            measure: Tipo de medida ("cohen_d", "a12")

        Returns:
            Interpretação textual
        """
        if measure == "cohen_d":
            abs_d = abs(effect_size)
            if abs_d < 0.2:
                return "negligible"
            elif abs_d < 0.5:
                return "small"
            elif abs_d < 0.8:
                return "medium"
            else:
                return "large"

        elif measure == "a12":
            diff = abs(effect_size - 0.5)
            if diff < 0.06:
                return "negligible"
            elif diff < 0.14:
                return "small"
            elif diff < 0.21:
                return "medium"
            else:
                return "large"

        return "unknown"

    def comprehensive_comparison(
        self,
        baseline_samples: Dict[str, List[float]],
        optimized_samples: Dict[str, List[float]],
        paired: bool = False,
    ) -> Dict[str, StatisticalTestResult]:
        """
        Realiza comparação estatística abrangente entre baseline e otimizada.

        Args:
            baseline_samples: Dicionário {métrica: [valores]}
            optimized_samples: Dicionário {métrica: [valores]}
            paired: Se True, usa testes pareados

        Returns:
            Dicionário {métrica: StatisticalTestResult}
        """
        results = {}

        for metric_name in baseline_samples.keys():
            if metric_name not in optimized_samples:
                continue

            baseline = baseline_samples[metric_name]
            optimized = optimized_samples[metric_name]

            # Escolher teste apropriado
            if paired:
                result = self.wilcoxon_signed_rank_test(
                    baseline, optimized, metric_name
                )
            else:
                result = self.mann_whitney_u_test(baseline, optimized, metric_name)

            results[metric_name] = result

        return results

    def create_comparison_report(
        self,
        baseline_samples: Dict[str, List[float]],
        optimized_samples: Dict[str, List[float]],
        paired: bool = False,
    ) -> str:
        """
        Cria relatório textual de comparação estatística.

        Args:
            baseline_samples: Amostras baseline
            optimized_samples: Amostras otimizadas
            paired: Se True, usa testes pareados

        Returns:
            Relatório em texto formatado
        """
        results = self.comprehensive_comparison(
            baseline_samples, optimized_samples, paired
        )

        report = "=" * 70 + "\n"
        report += "STATISTICAL COMPARISON REPORT\n"
        report += "=" * 70 + "\n\n"

        report += f"Significance Level (α): {self.alpha}\n"
        report += f"Test Type: {'Paired' if paired else 'Independent'}\n\n"

        for metric_name, result in results.items():
            report += f"Metric: {metric_name.upper()}\n"
            report += "-" * 70 + "\n"

            baseline = baseline_samples[metric_name]
            optimized = optimized_samples[metric_name]

            # Estatísticas descritivas
            report += f"  Baseline:  mean={np.mean(baseline):.3f}, median={np.median(baseline):.3f}, std={np.std(baseline):.3f}\n"
            report += f"  Optimized: mean={np.mean(optimized):.3f}, median={np.median(optimized):.3f}, std={np.std(optimized):.3f}\n\n"

            # Teste estatístico
            report += f"  {result.test_name}:\n"
            report += f"    Statistic: {result.statistic:.4f}\n"
            report += f"    P-value: {result.p_value:.4f}\n"
            report += f"    Significant: {'YES' if result.is_significant else 'NO'}\n"

            # Effect size
            a12 = self.vargha_delaney_a12(baseline, optimized)
            cohen = self.cohen_d(baseline, optimized)

            report += f"    Effect Size (A12): {a12:.3f} ({self.interpret_effect_size(a12, 'a12')})\n"
            report += f"    Effect Size (Cohen's d): {cohen:.3f} ({self.interpret_effect_size(cohen, 'cohen_d')})\n\n"

            report += f"  Interpretation: {result.interpretation}\n\n"

        report += "=" * 70 + "\n"

        return report


class ResultValidator:
    """Validador de resultados para pesquisa SBSE."""

    @staticmethod
    def check_normality(sample: List[float]) -> Tuple[bool, float]:
        """
        Testa normalidade usando Shapiro-Wilk test.

        Args:
            sample: Amostra de dados

        Returns:
            Tupla (is_normal, p_value)
        """
        if len(sample) < 3:
            return False, 1.0

        statistic, p_value = stats.shapiro(sample)
        return p_value > 0.05, p_value

    @staticmethod
    def check_homoscedasticity(
        sample1: List[float], sample2: List[float]
    ) -> Tuple[bool, float]:
        """
        Testa homogeneidade de variâncias usando Levene's test.

        Args:
            sample1: Primeira amostra
            sample2: Segunda amostra

        Returns:
            Tupla (has_equal_variance, p_value)
        """
        if len(sample1) < 3 or len(sample2) < 3:
            return False, 1.0

        statistic, p_value = stats.levene(sample1, sample2)
        return p_value > 0.05, p_value

    @staticmethod
    def recommend_test(
        sample1: List[float], sample2: List[float], paired: bool = False
    ) -> str:
        """
        Recomenda o teste estatístico apropriado.

        Args:
            sample1: Primeira amostra
            sample2: Segunda amostra
            paired: Se as amostras são pareadas

        Returns:
            Nome do teste recomendado
        """
        # Verificar normalidade
        is_normal1, _ = ResultValidator.check_normality(sample1)
        is_normal2, _ = ResultValidator.check_normality(sample2)

        if paired:
            if is_normal1 and is_normal2:
                return "Paired t-test"
            else:
                return "Wilcoxon Signed-Rank Test"
        else:
            if is_normal1 and is_normal2:
                # Verificar homogeneidade de variâncias
                has_equal_var, _ = ResultValidator.check_homoscedasticity(
                    sample1, sample2
                )

                if has_equal_var:
                    return "Independent t-test"
                else:
                    return "Welch's t-test"
            else:
                return "Mann-Whitney U Test"


if __name__ == "__main__":
    # Exemplo de uso
    print("Statistical Analysis Module")
    print("=" * 70)

    # Dados exemplo
    np.random.seed(42)

    # Simular métricas de baseline vs otimizada
    baseline_coverage = np.random.normal(50, 10, 30)
    optimized_coverage = np.random.normal(65, 8, 30)  # Melhor

    baseline_diversity = np.random.normal(0.5, 0.1, 30)
    optimized_diversity = np.random.normal(0.7, 0.12, 30)  # Melhor

    baseline_size = np.random.normal(20, 5, 30)
    optimized_size = np.random.normal(15, 3, 30)  # Menor (melhor)

    # Criar analyzer
    analyzer = StatisticalAnalyzer(alpha=0.05)

    # Teste Mann-Whitney U
    print("\nMann-Whitney U Test - Coverage:")
    print("-" * 70)
    result = analyzer.mann_whitney_u_test(
        baseline_coverage.tolist(), optimized_coverage.tolist(), "coverage"
    )
    print(f"Statistic: {result.statistic:.4f}")
    print(f"P-value: {result.p_value:.4f}")
    print(f"Significant: {result.is_significant}")
    print(f"Interpretation: {result.interpretation}")

    # Effect sizes
    a12 = analyzer.vargha_delaney_a12(
        baseline_coverage.tolist(), optimized_coverage.tolist()
    )
    cohen = analyzer.cohen_d(baseline_coverage.tolist(), optimized_coverage.tolist())

    print(f"\nEffect Sizes:")
    print(f"A12: {a12:.3f} ({analyzer.interpret_effect_size(a12, 'a12')})")
    print(
        f"Cohen's d: {cohen:.3f} ({analyzer.interpret_effect_size(cohen, 'cohen_d')})"
    )

    # Relatório completo
    print("\n" + "=" * 70)
    print("COMPREHENSIVE REPORT")
    print("=" * 70)

    baseline_samples = {
        "coverage": baseline_coverage.tolist(),
        "diversity": baseline_diversity.tolist(),
        "size": baseline_size.tolist(),
    }

    optimized_samples = {
        "coverage": optimized_coverage.tolist(),
        "diversity": optimized_diversity.tolist(),
        "size": optimized_size.tolist(),
    }

    report = analyzer.create_comparison_report(baseline_samples, optimized_samples)
    print(report)
