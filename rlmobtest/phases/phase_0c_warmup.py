"""
Phase 0c: Replay Memory Warm-up
Populates the agent's replay memory with transitions collected during Phase 0b
crawling, so training starts with real app interactions instead of an empty buffer.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rlmobtest.metrics.phase_observer import PhaseObserver
    from rlmobtest.phases.phase_0b_crawl import CrawlResult

logger = logging.getLogger(__name__)


@dataclass
class WarmupResult:
    """Result of the replay memory warm-up phase."""

    transitions_pushed: int = 0
    activities_covered: set = field(default_factory=set)
    warmup_duration: float = 0.0


def warmup_replay_memory(
    env,
    agent,
    crawl_result: "CrawlResult",
    observer: "PhaseObserver",
    steps_per_activity: int = 10,
) -> WarmupResult:
    """
    Execute random steps in each crawled activity and push transitions
    to agent.memory (ReplayMemory or PrioritizedReplayMemory).

    Uses the same env.step() / env._get_screen() calls as the training loop.
    Transitions are pushed via agent.memory.push(state, action, next_state, reward).

    Args:
        env: AndroidEnv instance
        agent: OriginalAgent or ImprovedAgent (must have .memory attribute)
        crawl_result: CrawlResult from Phase 0b
        observer: PhaseObserver for recording events
        steps_per_activity: Number of random steps to execute per activity

    Returns:
        WarmupResult with count of transitions pushed and activities covered
    """
    from rlmobtest.training.constants import Tensor

    start_time = time.time()
    result = WarmupResult()
    package = ""

    # Infer package from activity names
    for act in crawl_result.activities_reached:
        parts = act.rsplit(".", 1)
        if len(parts) == 2:
            package = parts[0]
            break

    observer.record_event(
        "0c",
        "warmup_started",
        {
            "activities": crawl_result.activities_reached,
            "steps_per_activity": steps_per_activity,
        },
    )

    for activity_name in crawl_result.activities_reached:
        try:
            transitions = _collect_warmup_transitions(
                env, agent, activity_name, package, steps_per_activity, Tensor
            )
            for state, action, next_state, reward_tensor in transitions:
                agent.memory.push(state, action, next_state, reward_tensor)
                result.transitions_pushed += 1
            result.activities_covered.add(activity_name)

            observer.record_event(
                "0c",
                "activity_warmed",
                {
                    "activity": activity_name,
                    "transitions": len(transitions),
                },
            )
        except Exception as e:
            logger.warning("Warmup failed for %s: %s", activity_name, e)
            observer.record_event(
                "0c", "activity_warmup_failed", {"activity": activity_name, "error": str(e)}
            )

    result.warmup_duration = time.time() - start_time
    observer.record_event(
        "0c",
        "warmup_completed",
        {
            "total_transitions": result.transitions_pushed,
            "duration": result.warmup_duration,
        },
    )
    return result


def _collect_warmup_transitions(
    env,
    agent,
    activity_name: str,
    package: str,
    steps: int,
    Tensor,
) -> list:
    """
    Execute random steps in the given activity and collect transitions.
    Returns list of (state, action, next_state, reward_tensor) tuples.
    """
    import subprocess

    from rlmobtest.training.constants import LongTensor

    transitions = []

    # Navigate to activity
    try:
        short_name = activity_name
        if activity_name.startswith(package):
            short_name = activity_name[len(package) :]
        subprocess.run(
            f"adb shell am start -n {package}/{short_name}".split(), capture_output=True, timeout=10
        )
        time.sleep(1.0)
    except Exception:
        return transitions

    try:
        state = env._get_screen()
        actions = env._get_actions(env._get_activity())

        for _ in range(steps):
            if not actions:
                break

            # Random action selection — cap at agent's num_actions (same as select_action)
            max_idx = min(len(actions), agent.num_actions) - 1
            action_idx = random.randint(0, max_idx)
            action_tensor = LongTensor([[action_idx]])

            try:
                next_state, next_actions, crash, activity = env.step(actions[action_idx])
                reward = 1.0  # Small positive reward for exploration
                reward_tensor = Tensor([reward])
                transitions.append((state, action_tensor, next_state, reward_tensor))

                state = next_state
                actions = next_actions

                if crash or not actions:
                    break
            except Exception:
                break

    except Exception as e:
        logger.warning("Transition collection failed: %s", e)

    return transitions
