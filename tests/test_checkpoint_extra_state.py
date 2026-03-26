"""Testes para ModelCheckpoint com extra_state — melhoria #6 (v0.1.15).

Prova que visited_activities (e qualquer outro estado adicional) é persistido
corretamente no checkpoint e restaurado na próxima run, implementando o
acúmulo de conhecimento entre runs.
"""

from unittest.mock import MagicMock

import pytest
import torch
import torch.nn as nn

from rlmobtest.training.checkpoint import ModelCheckpoint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _MinimalModel(nn.Module):
    """Modelo mínimo para testar save/load sem dependência de GPU/device real."""

    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2)

    def forward(self, x):
        return self.fc(x)


@pytest.fixture
def checkpoint_dir(tmp_path):
    return tmp_path / "checkpoints"


@pytest.fixture
def model():
    return _MinimalModel()


@pytest.fixture
def optimizer(model):
    return torch.optim.Adam(model.parameters())


@pytest.fixture
def mock_metrics():
    m = MagicMock()
    m.episode_rewards = [1.0, 2.0, 3.0]
    m.episode_lengths = [10, 20, 30]
    return m


# ---------------------------------------------------------------------------
# Testes de extra_state
# ---------------------------------------------------------------------------


class TestExtraStatePersistence:
    def test_visited_activities_roundtrip(self, checkpoint_dir, model, optimizer, mock_metrics):
        """Lista de activities visitadas deve sobreviver ao ciclo save → load."""
        mgr = ModelCheckpoint(checkpoint_dir)
        activities = ["MainActivity", "SettingsActivity", "LoginActivity"]

        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=5,
            steps_done=100,
            extra_state={"visited_activities": activities},
        )
        _, _, extra = mgr.load(path, model, optimizer)

        assert extra["visited_activities"] == activities

    def test_visited_activities_as_set_roundtrip(
        self, checkpoint_dir, model, optimizer, mock_metrics
    ):
        """Set serializado como list deve ser recuperável como set."""
        mgr = ModelCheckpoint(checkpoint_dir)
        activities = {"MainActivity", "ProfileActivity", "HomeActivity"}

        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=10,
            steps_done=500,
            extra_state={"visited_activities": list(activities)},
        )
        _, _, extra = mgr.load(path, model, optimizer)

        assert set(extra["visited_activities"]) == activities

    def test_empty_extra_state_returns_empty_dict(
        self, checkpoint_dir, model, optimizer, mock_metrics
    ):
        """Checkpoint salvo sem extra_state retorna {} no load (compatibilidade retroativa)."""
        mgr = ModelCheckpoint(checkpoint_dir)

        path = mgr.save(model, optimizer, mock_metrics, episode=1, steps_done=10)
        _, _, extra = mgr.load(path, model, optimizer)

        assert extra == {}

    def test_extra_state_none_treated_as_empty(
        self, checkpoint_dir, model, optimizer, mock_metrics
    ):
        mgr = ModelCheckpoint(checkpoint_dir)

        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=1,
            steps_done=10,
            extra_state=None,
        )
        _, _, extra = mgr.load(path, model, optimizer)

        assert extra == {}

    def test_arbitrary_extra_state_keys(self, checkpoint_dir, model, optimizer, mock_metrics):
        """extra_state pode conter quaisquer chaves serializáveis."""
        mgr = ModelCheckpoint(checkpoint_dir)
        state = {
            "visited_activities": ["A", "B"],
            "total_steps_across_runs": 9999,
            "notes": "run 2 of 3",
        }

        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=2,
            steps_done=200,
            extra_state=state,
        )
        _, _, extra = mgr.load(path, model, optimizer)

        assert extra == state


class TestLoadSignatureBackwardCompatibility:
    """load() agora retorna 3 valores — confirma que o unpacking funciona."""

    def test_load_returns_three_values(self, checkpoint_dir, model, optimizer, mock_metrics):
        mgr = ModelCheckpoint(checkpoint_dir)
        path = mgr.save(model, optimizer, mock_metrics, episode=7, steps_done=77)

        result = mgr.load(path, model, optimizer)

        assert len(result) == 3

    def test_episode_and_steps_preserved(self, checkpoint_dir, model, optimizer, mock_metrics):
        mgr = ModelCheckpoint(checkpoint_dir)
        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=42,
            steps_done=9999,
            extra_state={"visited_activities": ["X"]},
        )

        episode, steps, _ = mgr.load(path, model, optimizer)

        assert episode == 42
        assert steps == 9999

    def test_model_weights_preserved(self, checkpoint_dir, model, optimizer, mock_metrics):
        """Garantia básica: weights do modelo não mudam no ciclo save → load."""
        mgr = ModelCheckpoint(checkpoint_dir)
        original_weights = model.fc.weight.data.clone()

        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=1,
            steps_done=1,
            extra_state={"visited_activities": []},
        )

        # Modifica os pesos intencionalmente
        with torch.no_grad():
            model.fc.weight.fill_(0.0)

        mgr.load(path, model, optimizer)

        assert torch.allclose(model.fc.weight.data, original_weights)


class TestMultiRunScenario:
    """Simulação do fluxo multi-run: save no final da Run 1, load no início da Run 2."""

    def test_activities_accumulate_across_runs(
        self, checkpoint_dir, model, optimizer, mock_metrics
    ):
        mgr = ModelCheckpoint(checkpoint_dir)

        # Run 1: explora 3 activities
        run1_activities = {"MainActivity", "LoginActivity"}
        path = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=20,
            steps_done=1000,
            extra_state={"visited_activities": list(run1_activities)},
        )

        # Run 2: carrega checkpoint e adiciona nova activity
        _, _, extra = mgr.load(path, model, optimizer)
        loaded_activities = set(extra["visited_activities"])

        # Simula descoberta de nova activity na Run 2
        loaded_activities.add("SettingsActivity")

        # Salva Run 2
        path2 = mgr.save(
            model,
            optimizer,
            mock_metrics,
            episode=40,
            steps_done=2000,
            extra_state={"visited_activities": list(loaded_activities)},
        )

        _, _, extra2 = mgr.load(path2, model, optimizer)
        final_activities = set(extra2["visited_activities"])

        assert "MainActivity" in final_activities
        assert "LoginActivity" in final_activities
        assert "SettingsActivity" in final_activities
        assert len(final_activities) == 3
