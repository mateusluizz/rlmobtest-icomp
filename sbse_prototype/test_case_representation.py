#!/usr/bin/env python3
"""
Test Case Representation Module
Representa casos de teste para otimização SBSE
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Action:
    """Representa uma ação individual em um caso de teste."""

    step_number: int
    action_type: str  # click, scroll, swipe, back, etc.
    target: str | None = None  # Resource ID, xpath, ou coordenadas
    coordinates: tuple | None = None
    text_input: str | None = None
    activity: str = ""
    timestamp: float = 0.0
    screenshot_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "step": self.step_number,
            "type": self.action_type,
            "target": self.target,
            "coords": self.coordinates,
            "text": self.text_input,
            "activity": self.activity,
            "timestamp": self.timestamp,
            "screenshot": self.screenshot_path,
        }

    def get_signature(self) -> str:
        """Gera uma assinatura única para esta ação."""
        content = f"{self.action_type}_{self.target}_{self.coordinates}_{self.text_input}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


@dataclass
class TestCase:
    """Representa um caso de teste individual."""

    id: str
    actions: list[Action] = field(default_factory=list)
    coverage: set[str] = field(default_factory=set)  # Linhas/métodos cobertos
    activities_visited: set[str] = field(default_factory=set)
    crashes: int = 0
    duration: float = 0.0
    reward: float = 0.0
    episode_number: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # Extrair activities das ações
        if not self.activities_visited and self.actions:
            self.activities_visited = {a.activity for a in self.actions if a.activity}

    def get_length(self) -> int:
        """Retorna o número de ações no caso de teste."""
        return len(self.actions)

    def get_unique_actions(self) -> int:
        """Retorna o número de ações únicas."""
        signatures = {action.get_signature() for action in self.actions}
        return len(signatures)

    def get_coverage_size(self) -> int:
        """Retorna o tamanho da cobertura."""
        return len(self.coverage)

    def get_action_diversity(self) -> float:
        """Calcula diversidade de ações (unique/total)."""
        if not self.actions:
            return 0.0
        return self.get_unique_actions() / len(self.actions)

    def get_activity_diversity(self) -> int:
        """Retorna o número de activities únicas visitadas."""
        return len(self.activities_visited)

    def has_crash(self) -> bool:
        """Verifica se o teste detectou crash."""
        return self.crashes > 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actions": [a.to_dict() for a in self.actions],
            "coverage": list(self.coverage),
            "activities": list(self.activities_visited),
            "crashes": self.crashes,
            "duration": self.duration,
            "reward": self.reward,
            "episode": self.episode_number,
            "metadata": self.metadata,
            "metrics": {
                "length": self.get_length(),
                "unique_actions": self.get_unique_actions(),
                "coverage_size": self.get_coverage_size(),
                "action_diversity": self.get_action_diversity(),
                "activity_diversity": self.get_activity_diversity(),
            },
        }

    def save(self, filepath: Path):
        """Salva o caso de teste em JSON."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "TestCase":
        """Carrega caso de teste de arquivo JSON."""
        with open(filepath) as f:
            data = json.load(f)

        actions = [Action(**a) for a in data.get("actions", [])]
        return cls(
            id=data["id"],
            actions=actions,
            coverage=set(data.get("coverage", [])),
            activities_visited=set(data.get("activities", [])),
            crashes=data.get("crashes", 0),
            duration=data.get("duration", 0.0),
            reward=data.get("reward", 0.0),
            episode_number=data.get("episode", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TestSuite:
    """Representa uma suíte de casos de teste."""

    name: str
    test_cases: list[TestCase] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_test_case(self, tc: TestCase):
        """Adiciona um caso de teste à suíte."""
        self.test_cases.append(tc)

    def get_size(self) -> int:
        """Retorna o número de casos de teste."""
        return len(self.test_cases)

    def get_total_actions(self) -> int:
        """Retorna o número total de ações."""
        return sum(tc.get_length() for tc in self.test_cases)

    def get_total_coverage(self) -> set[str]:
        """Retorna a união de toda cobertura."""
        coverage = set()
        for tc in self.test_cases:
            coverage.update(tc.coverage)
        return coverage

    def get_coverage_size(self) -> int:
        """Retorna o tamanho total da cobertura."""
        return len(self.get_total_coverage())

    def get_total_crashes(self) -> int:
        """Retorna o número total de crashes detectados."""
        return sum(tc.crashes for tc in self.test_cases)

    def get_crash_detection_rate(self) -> float:
        """Retorna a taxa de detecção de crashes."""
        if not self.test_cases:
            return 0.0
        return sum(1 for tc in self.test_cases if tc.has_crash()) / len(self.test_cases)

    def get_total_duration(self) -> float:
        """Retorna a duração total de execução."""
        return sum(tc.duration for tc in self.test_cases)

    def get_all_activities(self) -> set[str]:
        """Retorna todas as activities visitadas."""
        activities = set()
        for tc in self.test_cases:
            activities.update(tc.activities_visited)
        return activities

    def calculate_diversity(self) -> float:
        """
        Calcula a diversidade da suíte usando Jaccard distance.
        Quanto maior, mais diversa é a suíte.
        """
        if len(self.test_cases) < 2:
            return 0.0

        similarities = []
        for i, tc1 in enumerate(self.test_cases):
            for tc2 in self.test_cases[i + 1 :]:
                # Jaccard similarity entre as ações
                actions1 = {a.get_signature() for a in tc1.actions}
                actions2 = {a.get_signature() for a in tc2.actions}

                if not actions1 or not actions2:
                    continue

                intersection = len(actions1 & actions2)
                union = len(actions1 | actions2)

                if union > 0:
                    similarity = intersection / union
                    similarities.append(similarity)

        if not similarities:
            return 0.0

        # Diversidade = 1 - média de similaridade
        avg_similarity = sum(similarities) / len(similarities)
        return 1.0 - avg_similarity

    def calculate_redundancy(self) -> float:
        """
        Calcula a redundância da suíte.
        Valor entre 0 (sem redundância) e 1 (totalmente redundante).
        """
        if len(self.test_cases) < 2:
            return 0.0

        return 1.0 - self.calculate_diversity()

    def get_summary(self) -> dict:
        """Retorna um resumo das métricas da suíte."""
        return {
            "name": self.name,
            "size": self.get_size(),
            "total_actions": self.get_total_actions(),
            "coverage": self.get_coverage_size(),
            "total_crashes": self.get_total_crashes(),
            "crash_detection_rate": self.get_crash_detection_rate(),
            "total_duration": self.get_total_duration(),
            "activities_covered": len(self.get_all_activities()),
            "diversity": self.calculate_diversity(),
            "redundancy": self.calculate_redundancy(),
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "metadata": self.metadata,
            "summary": self.get_summary(),
        }

    def save(self, filepath: Path):
        """Salva a suíte em JSON."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "TestSuite":
        """Carrega suíte de arquivo JSON."""
        with open(filepath) as f:
            data = json.load(f)

        test_cases = [
            TestCase(
                id=tc["id"],
                actions=[Action(**a) for a in tc.get("actions", [])],
                coverage=set(tc.get("coverage", [])),
                activities_visited=set(tc.get("activities", [])),
                crashes=tc.get("crashes", 0),
                duration=tc.get("duration", 0.0),
                reward=tc.get("reward", 0.0),
                episode_number=tc.get("episode", 0),
                metadata=tc.get("metadata", {}),
            )
            for tc in data.get("test_cases", [])
        ]

        return cls(name=data["name"], test_cases=test_cases, metadata=data.get("metadata", {}))


# =============================================================================
# UTILITIES
# =============================================================================


def create_test_suite_from_rl_output(
    test_cases_dir: Path, metrics_file: Path, name: str = "RL_Generated_Suite"
) -> TestSuite:
    """
    Cria uma TestSuite a partir dos outputs do RLMobTest.

    Args:
        test_cases_dir: Diretório contendo os casos de teste gerados
        metrics_file: Arquivo JSON com métricas do treinamento
        name: Nome da suíte

    Returns:
        TestSuite preenchida com os dados do RL
    """
    suite = TestSuite(name=name)

    # Carregar métricas do treinamento
    with open(metrics_file) as f:
        metrics_data = json.load(f)

    # Processar cada arquivo de caso de teste
    tc_files = sorted(test_cases_dir.glob("*.txt"))

    for idx, tc_file in enumerate(tc_files):
        # Parse do arquivo de caso de teste
        actions = _parse_test_case_file(tc_file)

        # Extrair métricas do episódio correspondente
        episode_reward = (
            metrics_data.get("episode_rewards", [0])[idx]
            if idx < len(metrics_data.get("episode_rewards", []))
            else 0
        )
        episode_duration = (
            metrics_data.get("episode_durations", [0])[idx]
            if idx < len(metrics_data.get("episode_durations", []))
            else 0
        )

        # Criar caso de teste
        tc = TestCase(
            id=f"TC_{idx + 1:03d}_{tc_file.stem}",
            actions=actions,
            duration=episode_duration,
            reward=episode_reward,
            episode_number=idx + 1,
        )

        suite.add_test_case(tc)

    return suite


def _parse_test_case_file(filepath: Path) -> list[Action]:
    """Parse de arquivo de caso de teste do formato do RLMobTest."""
    actions = []

    with open(filepath) as f:
        content = f.read()

    # Parse básico - pode ser refinado conforme formato real
    lines = content.split("\n")
    step = 0
    current_activity = "unknown"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detectar mudança de activity
        if line.startswith("Go to next activity:"):
            current_activity = line.split(":")[-1].strip()
            continue

        # Parse de ações (formato simplificado)
        # Você pode refinar isso conforme o formato real do seu output
        action = Action(
            step_number=step,
            action_type="click",  # Pode extrair do texto
            activity=current_activity,
        )
        actions.append(action)
        step += 1

    return actions


if __name__ == "__main__":
    # Exemplo de uso
    print("Test Case Representation Module")
    print("=" * 60)

    # Criar um caso de teste exemplo
    tc = TestCase(
        id="TC_001",
        actions=[
            Action(0, "click", target="button_login", activity="LoginActivity"),
            Action(1, "input", text_input="user@example.com", activity="LoginActivity"),
            Action(2, "click", target="submit", activity="LoginActivity"),
            Action(3, "click", target="menu", activity="MainActivity"),
        ],
        coverage={"LoginActivity.java:45", "MainActivity.java:23"},
        crashes=0,
        duration=12.5,
        reward=25.0,
    )

    print(f"Test Case: {tc.id}")
    print(f"Actions: {tc.get_length()}")
    print(f"Coverage: {tc.get_coverage_size()}")
    print(f"Diversity: {tc.get_action_diversity():.2f}")
    print()

    # Criar uma suíte
    suite = TestSuite(name="Example Suite")
    suite.add_test_case(tc)

    print(f"Suite: {suite.name}")
    print(f"Size: {suite.get_size()}")
    print(f"Total Coverage: {suite.get_coverage_size()}")
    print(f"Diversity: {suite.calculate_diversity():.2f}")
