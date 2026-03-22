"""Testes para coverage_reward() — melhoria #1 (v0.1.11).

Prova que a função calcula corretamente o bônus de recompensa
por novas linhas/branches cobertas, sem depender de dispositivo Android.
"""

import pytest

from rlmobtest.training.reward import coverage_reward


class TestCoverageRewardPositive:
    """Cenários onde a recompensa deve ser positiva."""

    def test_line_increase_only(self):
        prev = {"line_pct": 40.0, "branch_pct": 20.0}
        curr = {"line_pct": 45.0, "branch_pct": 20.0}
        # delta_lines = 5.0  → 5.0 * 5 = 25.0
        assert coverage_reward(prev, curr) == pytest.approx(25.0)

    def test_branch_increase_only(self):
        prev = {"line_pct": 40.0, "branch_pct": 20.0}
        curr = {"line_pct": 40.0, "branch_pct": 25.0}
        # delta_branches = 5.0  → 5.0 * 10 = 50.0
        assert coverage_reward(prev, curr) == pytest.approx(50.0)

    def test_combined_line_and_branch(self):
        prev = {"line_pct": 40.0, "branch_pct": 20.0}
        curr = {"line_pct": 45.0, "branch_pct": 25.0}
        # 5*5 + 5*10 = 75.0
        assert coverage_reward(prev, curr) == pytest.approx(75.0)

    def test_small_delta_still_rewarded(self):
        prev = {"line_pct": 40.0, "branch_pct": 20.0}
        curr = {"line_pct": 40.1, "branch_pct": 20.0}
        assert coverage_reward(prev, curr) == pytest.approx(0.1 * 5)

    def test_branches_weighted_higher_than_lines(self):
        """Branches são mais valiosos (+10/%) que linhas (+5/%)."""
        prev = {"line_pct": 0.0, "branch_pct": 0.0}
        curr_lines = {"line_pct": 1.0, "branch_pct": 0.0}
        curr_branches = {"line_pct": 0.0, "branch_pct": 1.0}
        assert coverage_reward(prev, curr_branches) > coverage_reward(prev, curr_lines)


class TestCoverageRewardZero:
    """Cenários onde a recompensa deve ser zero."""

    def test_no_change(self):
        cov = {"line_pct": 40.0, "branch_pct": 20.0}
        assert coverage_reward(cov, cov) == 0.0

    def test_line_decrease(self):
        prev = {"line_pct": 45.0, "branch_pct": 20.0}
        curr = {"line_pct": 40.0, "branch_pct": 20.0}
        assert coverage_reward(prev, curr) == 0.0

    def test_branch_decrease(self):
        prev = {"line_pct": 40.0, "branch_pct": 25.0}
        curr = {"line_pct": 40.0, "branch_pct": 20.0}
        assert coverage_reward(prev, curr) == 0.0

    def test_both_decrease(self):
        prev = {"line_pct": 50.0, "branch_pct": 30.0}
        curr = {"line_pct": 40.0, "branch_pct": 20.0}
        assert coverage_reward(prev, curr) == 0.0

    def test_empty_prev_returns_zero(self):
        curr = {"line_pct": 50.0, "branch_pct": 30.0}
        assert coverage_reward({}, curr) == 0.0

    def test_empty_curr_returns_zero(self):
        prev = {"line_pct": 50.0, "branch_pct": 30.0}
        assert coverage_reward(prev, {}) == 0.0

    def test_both_empty_returns_zero(self):
        assert coverage_reward({}, {}) == 0.0

    def test_missing_branch_key(self):
        """Chave ausente é tratada como 0 — sem crash."""
        prev = {"line_pct": 40.0}
        curr = {"line_pct": 45.0}
        assert coverage_reward(prev, curr) == pytest.approx(25.0)

    def test_missing_line_key(self):
        prev = {"branch_pct": 20.0}
        curr = {"branch_pct": 25.0}
        assert coverage_reward(prev, curr) == pytest.approx(50.0)


class TestCoverageRewardReturnType:
    def test_always_returns_float(self):
        prev = {"line_pct": 40.0, "branch_pct": 20.0}
        curr = {"line_pct": 45.0, "branch_pct": 25.0}
        assert isinstance(coverage_reward(prev, curr), float)

    def test_zero_is_float(self):
        cov = {"line_pct": 40.0, "branch_pct": 20.0}
        assert isinstance(coverage_reward(cov, cov), float)

    def test_result_is_non_negative(self):
        """A recompensa nunca é negativa — penalidades já são tratadas em calculate_reward."""
        prev = {"line_pct": 50.0, "branch_pct": 30.0}
        curr = {"line_pct": 30.0, "branch_pct": 10.0}
        assert coverage_reward(prev, curr) >= 0.0
