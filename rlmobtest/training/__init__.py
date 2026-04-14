"""Training package for RLMobTest."""

__all__ = [
    "run",
    "run_all",
    "process_app",
    "generate_report",
    "ImprovedAgent",
    "OriginalAgent",
    "DuelingDQN",
    "OriginalDQN",
]


def __getattr__(name: str):
    if name in ("run", "run_all"):
        from rlmobtest.training.loop import run, run_all

        return {"run": run, "run_all": run_all}[name]
    if name == "process_app":
        from rlmobtest.training.generate_requirements import process_app

        return process_app
    if name == "generate_report":
        from rlmobtest.training.report import generate_report

        return generate_report
    if name in ("ImprovedAgent", "OriginalAgent"):
        from rlmobtest.training.agents import ImprovedAgent, OriginalAgent

        return {"ImprovedAgent": ImprovedAgent, "OriginalAgent": OriginalAgent}[name]
    if name in ("DuelingDQN", "OriginalDQN"):
        from rlmobtest.training.models import DuelingDQN, OriginalDQN

        return {"DuelingDQN": DuelingDQN, "OriginalDQN": OriginalDQN}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
