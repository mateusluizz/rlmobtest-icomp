"""Testes para _fuzzy_match_id() e _compute_requirements_coverage() — melhoria #2 (v0.1.12).

Prova que o fuzzy matching recupera requisitos que o match exato perderia
(ex: mesmo resource-id local com prefixo de package diferente), aumentando
a cobertura de requisitos calculada.
"""

import pandas as pd
import pytest

from rlmobtest.training.report import _compute_requirements_coverage, _fuzzy_match_id


# ---------------------------------------------------------------------------
# Testes unitários de _fuzzy_match_id
# ---------------------------------------------------------------------------


class TestFuzzyMatchIdExact:
    def test_identical_ids_match(self):
        assert _fuzzy_match_id("com.foo:id/btn_save", "com.foo:id/btn_save") is True

    def test_na_matches_na(self):
        assert _fuzzy_match_id("N/A", "N/A") is True

    def test_na_does_not_match_real_id(self):
        assert _fuzzy_match_id("N/A", "com.foo:id/btn_save") is False

    def test_real_id_does_not_match_na(self):
        assert _fuzzy_match_id("com.foo:id/btn_save", "N/A") is False


class TestFuzzyMatchIdPackagePrefix:
    """Cenário central da melhoria: mesmo local ID, package diferente."""

    def test_same_local_id_different_package(self):
        # "btn_submit" == "btn_submit" mesmo que packages difiram
        assert _fuzzy_match_id("com.app1:id/btn_submit", "com.app2:id/btn_submit") is True

    def test_same_local_id_completely_different_package(self):
        assert _fuzzy_match_id("org.secuso:id/btn_login", "com.example:id/btn_login") is True

    def test_different_local_ids_not_matched(self):
        assert _fuzzy_match_id("com.foo:id/btn_save", "com.foo:id/tv_title") is False

    def test_completely_unrelated_ids_not_matched(self):
        assert _fuzzy_match_id("com.foo:id/btn_save", "com.bar:id/img_logo") is False


class TestFuzzyMatchIdThreshold:
    def test_default_threshold_08(self):
        # "btn_save" vs "btn_saves" — similar mas não idêntico
        result = _fuzzy_match_id("com.foo:id/btn_save", "com.foo:id/btn_saves")
        assert isinstance(result, bool)

    def test_custom_threshold_strict(self):
        # Com threshold 1.0 só aceita ids locais idênticos
        assert _fuzzy_match_id("com.foo:id/btn_save", "com.bar:id/btn_save", threshold=1.0) is True
        assert (
            _fuzzy_match_id("com.foo:id/btn_save", "com.bar:id/btn_save2", threshold=1.0) is False
        )

    def test_custom_threshold_lenient(self):
        # Com threshold 0.5, ids parecidos também são aceitos
        assert _fuzzy_match_id("com.foo:id/save", "com.bar:id/save_btn", threshold=0.5) is True


# ---------------------------------------------------------------------------
# Testes de _compute_requirements_coverage — demonstração do impacto real
# ---------------------------------------------------------------------------


def _make_run_with_tc(tmp_path, activity_class: str, tc_content: str) -> "Path":
    """Helper: cria uma run_path com um único arquivo de test case."""
    run_path = tmp_path
    tc_dir = run_path / "test_cases"
    tc_dir.mkdir(parents=True, exist_ok=True)
    tc_file = tc_dir / f"TC_.{activity_class}_20260101-120000.txt"
    tc_file.write_text(tc_content, encoding="utf-8")
    return run_path


def _make_requirements(activity: str, rid: str, action_type: str = "click") -> pd.DataFrame:
    return pd.DataFrame(
        [{"activity": activity, "field": "f", "id": rid, "action_type": action_type, "value": ""}]
    )


class TestRequirementsCoverageExactMatch:
    """Comportamento existente antes do fuzzy: match exato continua funcionando."""

    def test_exact_id_match_counted(self, tmp_path):
        run = _make_run_with_tc(
            tmp_path,
            "MainActivity",
            "Clicked android.widget.Button com.example:id/btn_save bounds:[0,100]",
        )
        reqs = _make_requirements("MainActivity", "com.example:id/btn_save")
        covered, total = _compute_requirements_coverage([run], reqs)
        assert total == 1
        assert covered == 1

    def test_wrong_action_type_not_counted(self, tmp_path):
        run = _make_run_with_tc(
            tmp_path,
            "MainActivity",
            "Scroll down android.widget.ScrollView com.example:id/btn_save bounds:[0,100]",
        )
        reqs = _make_requirements("MainActivity", "com.example:id/btn_save", action_type="click")
        covered, total = _compute_requirements_coverage([run], reqs)
        assert total == 1
        assert covered == 0

    def test_unrelated_id_not_counted(self, tmp_path):
        run = _make_run_with_tc(
            tmp_path,
            "MainActivity",
            "Clicked android.widget.Button com.example:id/tv_title bounds:[0,100]",
        )
        reqs = _make_requirements("MainActivity", "com.example:id/btn_save")
        covered, total = _compute_requirements_coverage([run], reqs)
        assert total == 1
        assert covered == 0


class TestRequirementsCoverageFuzzyMatch:
    """Cenários que SÓ funcionam com fuzzy matching (a melhoria de v0.1.12).

    Antes da melhoria: covered == 0 (match exato falhava).
    Depois da melhoria: covered == 1 (fuzzy match detecta mesmo ID local).
    """

    def test_different_package_prefix_is_covered(self, tmp_path):
        """TC logou com.app2:id/btn_submit, requisito espera com.app1:id/btn_submit.

        O ID local 'btn_submit' é idêntico — fuzzy match deve reconhecer como coberto.
        """
        run = _make_run_with_tc(
            tmp_path,
            "MainActivity",
            "Clicked android.widget.Button com.app2:id/btn_submit bounds:[0,100]",
        )
        reqs = _make_requirements("MainActivity", "com.app1:id/btn_submit")

        covered, total = _compute_requirements_coverage([run], reqs)

        assert total == 1
        assert covered == 1, (
            "Fuzzy matching deve contar como coberto: IDs locais idênticos "
            "('btn_submit'), apenas o prefixo de package difere."
        )

    def test_org_vs_com_package_covered(self, tmp_path):
        run = _make_run_with_tc(
            tmp_path,
            "LoginActivity",
            "Clicked android.widget.Button org.secuso:id/btn_login bounds:[0,100]",
        )
        reqs = _make_requirements("LoginActivity", "com.example:id/btn_login")

        covered, total = _compute_requirements_coverage([run], reqs)

        assert total == 1
        assert covered == 1

    def test_multiple_reqs_fuzzy_recovers_all(self, tmp_path):
        """Múltiplos requisitos todos com package diferente, mas todos cobertos."""
        run_path = tmp_path
        tc_dir = run_path / "test_cases"
        tc_dir.mkdir(parents=True, exist_ok=True)
        tc_content = (
            "Clicked android.widget.Button com.app2:id/btn_save bounds:[0,100]\n"
            "Clicked android.widget.Button com.app2:id/btn_cancel bounds:[0,100]"
        )
        (tc_dir / "TC_.MainActivity_20260101-120000.txt").write_text(tc_content)

        reqs = pd.DataFrame(
            [
                {
                    "activity": "MainActivity",
                    "field": "a",
                    "id": "com.app1:id/btn_save",
                    "action_type": "click",
                    "value": "",
                },
                {
                    "activity": "MainActivity",
                    "field": "b",
                    "id": "com.app1:id/btn_cancel",
                    "action_type": "click",
                    "value": "",
                },
            ]
        )

        covered, total = _compute_requirements_coverage([run_path], reqs)

        assert total == 2
        assert covered == 2

    def test_completely_different_ids_not_covered_by_fuzzy(self, tmp_path):
        """Fuzzy não faz milagre — IDs sem relação não devem ser contados."""
        run = _make_run_with_tc(
            tmp_path,
            "MainActivity",
            "Clicked android.widget.Button com.app2:id/img_logo bounds:[0,100]",
        )
        reqs = _make_requirements("MainActivity", "com.app1:id/btn_save")

        covered, total = _compute_requirements_coverage([run], reqs)

        assert total == 1
        assert covered == 0
