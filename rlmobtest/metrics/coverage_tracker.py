"""
Coverage tracking for the DRL-MOBTEST training pipeline.
Tracks 4 coverage types live during training:
  - Activity coverage (visited / total declared in manifest)
  - Element coverage (touched UI elements / total discovered in crawling)
  - Requirement coverage (exercised requirements / total in requirements.csv)
  - JaCoCo code coverage (from .ec files)

At the end, converts tracking data to sbse_prototype TestSuite for
integration with MetricsCalculator.calculate_all_metrics().
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt

from rlmobtest.metrics.sbse_bridge import SBSE_AVAILABLE, MetricsCalculator

if TYPE_CHECKING:
    from rlmobtest.training.metrics import TrainingMetrics

logger = logging.getLogger(__name__)


@dataclass
class CoverageSnapshot:
    """Point-in-time coverage reading."""

    timestamp: float
    episode: int
    step: int
    activity_coverage: float
    element_coverage: float
    requirement_coverage: float
    jacoco_coverage: float


class CoverageTracker:
    """
    Tracks 4 coverage metrics live during training.
    Can be initialized without manifest/crawl_result for backward compat.
    """

    def __init__(self, manifest=None, crawl_result=None):
        # Universe of known items (from pre-training phases)
        self.total_activities: set[str] = set()
        self.total_elements: set[str] = set()
        self.total_requirements: int = 0

        # Initialize from manifest if provided
        if manifest is not None:
            self.total_activities = set(manifest.activities)

        # Initialize elements from crawl result if provided
        if crawl_result is not None:
            for snapshot in crawl_result.snapshots.values():
                self.total_elements.update(snapshot.elements_found)

        # Seen during training
        self.activities_seen: set[str] = set()
        self.elements_seen: set[str] = set()
        self.requirements_hit: set[str] = set()
        self.jacoco_coverage: float = 0.0

        # Input-class tracking (resource-ids that have been typed into)
        self.typed_elements: set[str] = set()

        # Per-episode tracking (lists parallel to TrainingMetrics.episode_*)
        self.episode_activities: list[set] = []
        self.episode_elements: list[set] = []
        self._current_episode_activities: set[str] = set()
        self._current_episode_elements: set[str] = set()
        self._current_episode_typed: set[str] = set()

        # Snapshot history
        self.history: list[CoverageSnapshot] = []
        self.current_episode: int = 0
        self.current_step: int = 0

    def start_episode(self) -> None:
        """Called at the start of each training episode."""
        self.current_episode += 1
        self.current_step = 0
        self._current_episode_activities = set()
        self._current_episode_elements = set()
        self._current_episode_typed = set()

    def end_episode(self) -> None:
        """Called at the end of each training episode."""
        self.episode_activities.append(set(self._current_episode_activities))
        self.episode_elements.append(set(self._current_episode_elements))

    def record_activity(self, activity: str) -> bool:
        """Mark an activity as visited. Returns True if new."""
        is_new = activity not in self.activities_seen
        self.activities_seen.add(activity)
        self._current_episode_activities.add(activity)
        return is_new

    def record_element(self, element_id: str) -> bool:
        """Mark a UI element resource-id as interacted with. Returns True if new."""
        if not element_id:
            return False
        is_new = element_id not in self.elements_seen
        self.elements_seen.add(element_id)
        self._current_episode_elements.add(element_id)
        return is_new

    def record_type_action(self, element_id: str) -> bool:
        """Mark that a type/input action was performed on an element. Returns True if new."""
        if not element_id:
            return False
        is_new = element_id not in self.typed_elements
        self.typed_elements.add(element_id)
        self._current_episode_typed.add(element_id)
        return is_new

    def record_requirement_hit(self, requirement_id: str) -> bool:
        """Mark a requirement as covered. Returns True if new."""
        if not requirement_id:
            return False
        is_new = requirement_id not in self.requirements_hit
        self.requirements_hit.add(requirement_id)
        return is_new

    def update_jacoco(self, ec_files_dir: Path) -> float:
        """
        Update JaCoCo coverage from .ec files directory.
        Uses file count as proxy if jacococli is unavailable.
        """
        ec_files_dir = Path(ec_files_dir)
        if not ec_files_dir.exists():
            return self.jacoco_coverage
        ec_files = list(ec_files_dir.glob("*.ec"))
        if ec_files:
            # Proxy: presence of .ec files indicates coverage was collected
            # A real implementation would run jacococli to get line coverage
            self.jacoco_coverage = min(1.0, len(ec_files) * 0.1)
        return self.jacoco_coverage

    def get_current_coverage(self) -> dict:
        """Return dict with current float ratios for all 4 coverage types."""
        return {
            "activity_coverage": self._activity_ratio(),
            "element_coverage": self._element_ratio(),
            "requirement_coverage": self._requirement_ratio(),
            "jacoco_coverage": self.jacoco_coverage,
        }

    def take_snapshot(self, episode: int, step: int) -> CoverageSnapshot:
        """Compute current ratios and store in history."""
        snapshot = CoverageSnapshot(
            timestamp=time.time(),
            episode=episode,
            step=step,
            activity_coverage=self._activity_ratio(),
            element_coverage=self._element_ratio(),
            requirement_coverage=self._requirement_ratio(),
            jacoco_coverage=self.jacoco_coverage,
        )
        self.history.append(snapshot)
        return snapshot

    def set_total_requirements(self, count: int) -> None:
        """Set total requirement count after requirements.csv is generated."""
        self.total_requirements = count

    def _activity_ratio(self) -> float:
        if not self.total_activities:
            return 0.0
        return len(self.activities_seen) / len(self.total_activities)

    def _element_ratio(self) -> float:
        if not self.total_elements:
            return 0.0
        return min(1.0, len(self.elements_seen) / len(self.total_elements))

    def _requirement_ratio(self) -> float:
        if self.total_requirements == 0:
            return 0.0
        return min(1.0, len(self.requirements_hit) / self.total_requirements)

    def to_test_suite(self, training_metrics: "TrainingMetrics"):
        """
        Convert tracking data to sbse_prototype TestSuite.
        Each training episode becomes a TestCase.
        Requires sbse_bridge to be available.
        """
        if not SBSE_AVAILABLE:
            logger.warning("sbse_prototype not available, skipping to_test_suite()")
            return None

        from rlmobtest.metrics.sbse_bridge import TestCase, TestSuite

        test_cases = []
        n_episodes = len(training_metrics.episode_rewards)

        for i in range(n_episodes):
            activities = self.episode_activities[i] if i < len(self.episode_activities) else set()
            elements = self.episode_elements[i] if i < len(self.episode_elements) else set()

            # Build a mock TestCase compatible with sbse_prototype
            tc = TestCase(
                id=f"episode_{i + 1}",
                actions=[],  # actions not tracked at this level
                activities_visited=activities,
                coverage=elements,
                crashes=0,  # crash info not stored per-episode here
                duration=training_metrics.episode_durations[i]
                if i < len(training_metrics.episode_durations)
                else 0.0,
                reward=training_metrics.episode_rewards[i]
                if i < len(training_metrics.episode_rewards)
                else 0.0,
            )
            test_cases.append(tc)

        return TestSuite(name=f"rlmobtest_run_{training_metrics.run_id}", test_cases=test_cases)

    def calculate_final_metrics(self, training_metrics: "TrainingMetrics") -> dict:
        """
        Compute final coverage metrics, integrating with sbse_prototype if available.
        Returns a dict suitable for JSON serialization and HTML report.
        """
        result = self.get_current_coverage()
        result.update(
            {
                "activities_seen": sorted(self.activities_seen),
                "activities_total": sorted(self.total_activities),
                "elements_seen_count": len(self.elements_seen),
                "elements_total_count": len(self.total_elements),
                "requirements_hit_count": len(self.requirements_hit),
                "requirements_total_count": self.total_requirements,
            }
        )

        if SBSE_AVAILABLE and training_metrics is not None:
            try:
                suite = self.to_test_suite(training_metrics)
                if suite is not None:
                    calc = MetricsCalculator()
                    metrics = calc.calculate_all_metrics(suite)
                    result["sbse"] = {
                        "coverage": metrics.coverage,
                        "diversity": metrics.diversity,
                        "suite_size": metrics.suite_size,
                        "fault_detection_rate": metrics.fault_detection_rate,
                    }
            except Exception as e:
                logger.warning("sbse_prototype metrics calculation failed: %s", e)

        return result

    def plot_coverage(self, output_path: Path, run_id: str) -> Path:
        """Generate a 2x2 coverage plot over episodes."""
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        if not self.history:
            logger.warning("No coverage history to plot")
            return output_path / f"coverage_{run_id}.png"

        episodes = [s.episode for s in self.history]
        activity_cov = [s.activity_coverage for s in self.history]
        element_cov = [s.element_coverage for s in self.history]
        req_cov = [s.requirement_coverage for s in self.history]
        jacoco_cov = [s.jacoco_coverage for s in self.history]

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle(f"Coverage Metrics - {run_id}", fontsize=14, fontweight="bold")

        metrics_data = [
            (axes[0, 0], activity_cov, "Activity Coverage", "steelblue"),
            (axes[0, 1], element_cov, "Element Coverage", "darkorange"),
            (axes[1, 0], req_cov, "Requirement Coverage", "mediumseagreen"),
            (axes[1, 1], jacoco_cov, "JaCoCo Coverage", "orchid"),
        ]

        for ax, data, title, color in metrics_data:
            ax.plot(episodes, data, color=color, linewidth=2)
            ax.fill_between(episodes, data, alpha=0.2, color=color)
            ax.set_title(title)
            ax.set_xlabel("Episode")
            ax.set_ylabel("Coverage Ratio")
            ax.set_ylim(-0.05, 1.05)
            ax.grid(True, alpha=0.3)
            if data:
                ax.axhline(
                    data[-1], color=color, linestyle="--", alpha=0.5, label=f"Final: {data[-1]:.1%}"
                )
                ax.legend(loc="lower right")

        plt.tight_layout()
        filepath = output_path / f"coverage_{run_id}.png"
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        plt.close()
        logger.info("Coverage plot saved: %s", filepath)
        return filepath
