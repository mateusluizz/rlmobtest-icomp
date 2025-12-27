#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualization Module
Visualizações para resultados de otimização SBSE
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import seaborn as sns

from test_case_representation import TestSuite
from metrics_calculator import ObjectiveMetrics

# Configurações de estilo
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


class ParetoVisualizer:
    """Visualizador para fronteiras de Pareto."""

    def __init__(self, figsize=(12, 8), dpi=100):
        self.figsize = figsize
        self.dpi = dpi

    def plot_pareto_front_2d(
        self,
        pareto_front: List[Tuple[TestSuite, ObjectiveMetrics]],
        objectives: Tuple[str, str] = ("coverage", "suite_size"),
        highlight_best: Optional[str] = None,
        save_path: Optional[Path] = None,
        title: str = "Pareto Front"
    ):
        """
        Plota fronteira de Pareto em 2D.

        Args:
            pareto_front: Lista de tuplas (suite, metrics)
            objectives: Tupla com nomes dos objetivos para eixos X e Y
            highlight_best: Critério para destacar melhor solução
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        obj_x, obj_y = objectives

        # Extrair valores
        x_vals = [getattr(m, obj_x) for s, m in pareto_front]
        y_vals = [getattr(m, obj_y) for s, m in pareto_front]

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Plotar pontos
        scatter = ax.scatter(
            x_vals, y_vals,
            c=range(len(pareto_front)),
            cmap='viridis',
            s=100,
            alpha=0.6,
            edgecolors='black',
            linewidth=0.5
        )

        # Destacar melhor solução
        if highlight_best:
            from sbse_optimizer import SBSEOptimizer
            # Criar otimizador temporário para usar método select_best_solution
            # (simplificado aqui - em uso real, passar como parâmetro)
            best_idx = 0
            if highlight_best == "coverage":
                best_idx = np.argmax(x_vals)
            elif highlight_best == "minimal":
                best_idx = np.argmin(y_vals)

            ax.scatter(
                x_vals[best_idx], y_vals[best_idx],
                c='red', s=300, marker='*',
                edgecolors='black', linewidth=2,
                label='Best Solution', zorder=5
            )

        # Conectar pontos (linha da fronteira)
        sorted_indices = np.argsort(x_vals)
        sorted_x = [x_vals[i] for i in sorted_indices]
        sorted_y = [y_vals[i] for i in sorted_indices]
        ax.plot(sorted_x, sorted_y, 'k--', alpha=0.3, linewidth=1)

        # Labels e título
        ax.set_xlabel(obj_x.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_ylabel(obj_y.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold')

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Solution Index', fontsize=10)

        # Grid
        ax.grid(True, alpha=0.3)

        if highlight_best:
            ax.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Plot saved: {save_path}")

        plt.show()

    def plot_pareto_front_3d(
        self,
        pareto_front: List[Tuple[TestSuite, ObjectiveMetrics]],
        objectives: Tuple[str, str, str] = ("coverage", "diversity", "suite_size"),
        save_path: Optional[Path] = None,
        title: str = "3D Pareto Front"
    ):
        """
        Plota fronteira de Pareto em 3D.

        Args:
            pareto_front: Lista de tuplas (suite, metrics)
            objectives: Tupla com nomes dos 3 objetivos
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        obj_x, obj_y, obj_z = objectives

        # Extrair valores
        x_vals = [getattr(m, obj_x) for s, m in pareto_front]
        y_vals = [getattr(m, obj_y) for s, m in pareto_front]
        z_vals = [getattr(m, obj_z) for s, m in pareto_front]

        fig = plt.figure(figsize=self.figsize, dpi=self.dpi)
        ax = fig.add_subplot(111, projection='3d')

        # Plotar pontos
        scatter = ax.scatter(
            x_vals, y_vals, z_vals,
            c=range(len(pareto_front)),
            cmap='plasma',
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidth=0.5
        )

        # Labels
        ax.set_xlabel(obj_x.replace('_', ' ').title(), fontsize=10, fontweight='bold')
        ax.set_ylabel(obj_y.replace('_', ' ').title(), fontsize=10, fontweight='bold')
        ax.set_zlabel(obj_z.replace('_', ' ').title(), fontsize=10, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
        cbar.set_label('Solution Index', fontsize=10)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ 3D plot saved: {save_path}")

        plt.show()

    def plot_objectives_heatmap(
        self,
        pareto_front: List[Tuple[TestSuite, ObjectiveMetrics]],
        save_path: Optional[Path] = None,
        title: str = "Objectives Heatmap"
    ):
        """
        Plota heatmap de correlação entre objetivos.

        Args:
            pareto_front: Lista de tuplas (suite, metrics)
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        # Criar matriz de dados
        data = {
            'Coverage': [m.coverage for s, m in pareto_front],
            'Diversity': [m.diversity for s, m in pareto_front],
            'Size': [m.suite_size for s, m in pareto_front],
            'Fault Rate': [m.fault_detection_rate for s, m in pareto_front]
        }

        import pandas as pd
        df = pd.DataFrame(data)

        # Calcular correlação
        corr = df.corr()

        fig, ax = plt.subplots(figsize=(8, 6), dpi=self.dpi)

        # Heatmap
        sns.heatmap(
            corr,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            square=True,
            linewidths=1,
            cbar_kws={"shrink": 0.8},
            ax=ax
        )

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Heatmap saved: {save_path}")

        plt.show()

    def plot_objectives_distribution(
        self,
        pareto_front: List[Tuple[TestSuite, ObjectiveMetrics]],
        save_path: Optional[Path] = None,
        title: str = "Objectives Distribution"
    ):
        """
        Plota distribuição dos objetivos na fronteira de Pareto.

        Args:
            pareto_front: Lista de tuplas (suite, metrics)
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        # Extrair dados
        data = {
            'Coverage': [m.coverage for s, m in pareto_front],
            'Diversity': [m.diversity for s, m in pareto_front],
            'Size': [m.suite_size for s, m in pareto_front],
            'Fault Rate': [m.fault_detection_rate for s, m in pareto_front]
        }

        fig, axes = plt.subplots(2, 2, figsize=self.figsize, dpi=self.dpi)
        axes = axes.flatten()

        colors = ['skyblue', 'lightgreen', 'coral', 'plum']

        for idx, (obj_name, values) in enumerate(data.items()):
            ax = axes[idx]

            # Histograma
            ax.hist(values, bins=15, color=colors[idx], alpha=0.7, edgecolor='black')

            # Estatísticas
            mean_val = np.mean(values)
            median_val = np.median(values)

            ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.2f}')
            ax.axvline(median_val, color='blue', linestyle=':', linewidth=2, label=f'Median: {median_val:.2f}')

            ax.set_xlabel(obj_name, fontsize=10, fontweight='bold')
            ax.set_ylabel('Frequency', fontsize=10)
            ax.set_title(f'{obj_name} Distribution', fontsize=11, fontweight='bold')
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Distribution plot saved: {save_path}")

        plt.show()

    def plot_convergence(
        self,
        history_data: List[Dict],
        save_path: Optional[Path] = None,
        title: str = "Convergence Over Generations"
    ):
        """
        Plota convergência do algoritmo ao longo das gerações.

        Args:
            history_data: Lista de dicionários com métricas por geração
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        # Extrair dados
        generations = [h['generation'] for h in history_data]
        avg_coverage = [h['avg_coverage'] for h in history_data]
        avg_diversity = [h['avg_diversity'] for h in history_data]
        avg_size = [h['avg_size'] for h in history_data]

        fig, axes = plt.subplots(3, 1, figsize=(10, 10), dpi=self.dpi)

        # Coverage
        axes[0].plot(generations, avg_coverage, 'b-', linewidth=2, marker='o', markersize=4)
        axes[0].set_ylabel('Avg Coverage', fontsize=10, fontweight='bold')
        axes[0].set_title('Coverage Convergence', fontsize=11, fontweight='bold')
        axes[0].grid(True, alpha=0.3)

        # Diversity
        axes[1].plot(generations, avg_diversity, 'g-', linewidth=2, marker='s', markersize=4)
        axes[1].set_ylabel('Avg Diversity', fontsize=10, fontweight='bold')
        axes[1].set_title('Diversity Convergence', fontsize=11, fontweight='bold')
        axes[1].grid(True, alpha=0.3)

        # Size
        axes[2].plot(generations, avg_size, 'r-', linewidth=2, marker='^', markersize=4)
        axes[2].set_ylabel('Avg Suite Size', fontsize=10, fontweight='bold')
        axes[2].set_xlabel('Generation', fontsize=10, fontweight='bold')
        axes[2].set_title('Suite Size Convergence', fontsize=11, fontweight='bold')
        axes[2].grid(True, alpha=0.3)

        plt.suptitle(title, fontsize=14, fontweight='bold', y=0.995)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Convergence plot saved: {save_path}")

        plt.show()


class ComparisonVisualizer:
    """Visualizador para comparações entre suítes."""

    def __init__(self, figsize=(12, 6), dpi=100):
        self.figsize = figsize
        self.dpi = dpi

    def plot_suite_comparison(
        self,
        baseline_metrics: ObjectiveMetrics,
        optimized_metrics: ObjectiveMetrics,
        save_path: Optional[Path] = None,
        title: str = "Baseline vs Optimized Suite"
    ):
        """
        Compara métricas entre baseline e suíte otimizada.

        Args:
            baseline_metrics: Métricas da suíte baseline
            optimized_metrics: Métricas da suíte otimizada
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        # Dados
        objectives = ['Coverage', 'Diversity', 'Fault Rate']
        baseline_vals = [
            baseline_metrics.coverage,
            baseline_metrics.diversity,
            baseline_metrics.fault_detection_rate
        ]
        optimized_vals = [
            optimized_metrics.coverage,
            optimized_metrics.diversity,
            optimized_metrics.fault_detection_rate
        ]

        # Normalizar para comparação visual
        max_vals = [max(b, o) for b, o in zip(baseline_vals, optimized_vals)]
        baseline_norm = [b/m if m > 0 else 0 for b, m in zip(baseline_vals, max_vals)]
        optimized_norm = [o/m if m > 0 else 0 for o, m in zip(optimized_vals, max_vals)]

        x = np.arange(len(objectives))
        width = 0.35

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        bars1 = ax.bar(x - width/2, baseline_norm, width, label='Baseline',
                      color='coral', alpha=0.8, edgecolor='black')
        bars2 = ax.bar(x + width/2, optimized_norm, width, label='Optimized',
                      color='skyblue', alpha=0.8, edgecolor='black')

        # Adicionar valores nas barras
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.2f}',
                       ha='center', va='bottom', fontsize=9)

        ax.set_xlabel('Objectives', fontsize=12, fontweight='bold')
        ax.set_ylabel('Normalized Value', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(objectives)
        ax.legend(fontsize=10)
        ax.grid(True, axis='y', alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Comparison plot saved: {save_path}")

        plt.show()

    def plot_improvement_radar(
        self,
        baseline_metrics: ObjectiveMetrics,
        optimized_metrics: ObjectiveMetrics,
        save_path: Optional[Path] = None,
        title: str = "Improvement Radar Chart"
    ):
        """
        Plota radar chart comparando baseline e otimizada.

        Args:
            baseline_metrics: Métricas da suíte baseline
            optimized_metrics: Métricas da suíte otimizada
            save_path: Caminho para salvar figura
            title: Título do gráfico
        """
        categories = ['Coverage', 'Diversity', 'Fault\nRate', 'Efficiency']

        # Valores (normalizar para [0, 1])
        baseline_vals = [
            baseline_metrics.coverage,
            baseline_metrics.diversity,
            baseline_metrics.fault_detection_rate,
            1.0 / baseline_metrics.suite_size if baseline_metrics.suite_size > 0 else 0
        ]

        optimized_vals = [
            optimized_metrics.coverage,
            optimized_metrics.diversity,
            optimized_metrics.fault_detection_rate,
            1.0 / optimized_metrics.suite_size if optimized_metrics.suite_size > 0 else 0
        ]

        # Normalizar
        max_vals = [max(b, o) for b, o in zip(baseline_vals, optimized_vals)]
        baseline_norm = [b/m if m > 0 else 0 for b, m in zip(baseline_vals, max_vals)]
        optimized_norm = [o/m if m > 0 else 0 for o, m in zip(optimized_vals, max_vals)]

        # Criar radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        baseline_norm += baseline_norm[:1]
        optimized_norm += optimized_norm[:1]
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), dpi=self.dpi)

        ax.plot(angles, baseline_norm, 'o-', linewidth=2, label='Baseline', color='coral')
        ax.fill(angles, baseline_norm, alpha=0.25, color='coral')

        ax.plot(angles, optimized_norm, 'o-', linewidth=2, label='Optimized', color='skyblue')
        ax.fill(angles, optimized_norm, alpha=0.25, color='skyblue')

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_ylim(0, 1)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        ax.grid(True)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=self.dpi, bbox_inches='tight')
            print(f"✅ Radar chart saved: {save_path}")

        plt.show()


if __name__ == "__main__":
    # Exemplo de uso
    from test_case_representation import TestCase, Action, TestSuite
    from metrics_calculator import MetricsCalculator

    print("Visualization Module")
    print("=" * 60)

    # Criar dados exemplo
    pareto_front = []

    for i in range(20):
        tc = TestCase(
            id=f"TC_{i:03d}",
            actions=[Action(j, "click", f"btn_{j}") for j in range(5 + i)],
            coverage={f"C:{k}" for k in range(10 + i * 2)},
            crashes=np.random.randint(0, 2)
        )

        suite = TestSuite(name=f"Suite_{i}")
        suite.add_test_case(tc)

        calc = MetricsCalculator()
        metrics = calc.calculate_all_metrics(suite)

        pareto_front.append((suite, metrics))

    # Visualizar
    viz = ParetoVisualizer()
    viz.plot_pareto_front_2d(pareto_front, title="Example Pareto Front")
    viz.plot_objectives_distribution(pareto_front)
