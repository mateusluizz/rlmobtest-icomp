import torch
from rlmobtest.training.constants import Tensor


_TYPE_SUBTYPES = {
    "type",
    "tc_text",
    "text_start_size",
    "text_end_size",
    "number_start_size",
    "number_end_size",
}


def _short_resource_id(full_id: str) -> str:
    """Strip package prefix: 'pkg:id/foo' → 'foo'. Already short IDs pass through."""
    if ":id/" in full_id:
        return full_id.split(":id/", 1)[1]
    return full_id


def calculate_functional_reward(
    taken_action,
    coverage_tracker,
    elements_on_screen: list | None = None,
) -> float:
    """
    Coverage-based additive reward implementing the proposed reward table.

    Args:
        taken_action: Actual action object (has .action_subtype, .resourceid).
                      Pass None when coverage_tracker is unavailable.
        coverage_tracker: CoverageTracker instance. Returns 0.0 if None.
        elements_on_screen: resource-id strings visible on current screen
                            (extracted from XML hierarchy, full-form IDs).

    Reward table:
        +15  per interactive element (in total_elements) never seen before
        +20  per new input class: first time agent types into a specific element

    Note: total_elements stores short IDs from Phase 0b (e.g. "btn_save").
    XML dumps return full IDs (e.g. "com.pkg:id/btn_save").
    We normalize to short form before comparing.
    """
    if coverage_tracker is None:
        return 0.0

    known = coverage_tracker.total_elements  # short IDs from Phase 0b
    bonus = 0.0

    # +15 per newly-seen element that Phase 0b identified as interactive.
    # Normalize full XML IDs to short form before matching against known set.
    for full_id in elements_on_screen or []:
        if not full_id:
            continue
        short = _short_resource_id(full_id)
        if known and short not in known:
            continue  # ignore elements outside the Phase 0b universe
        if coverage_tracker.record_element(short):
            bonus += 15.0

    # +20 for first time the agent types into a specific element
    if taken_action is not None:
        subtype = getattr(taken_action, "action_subtype", "") or ""
        rid = getattr(taken_action, "resourceid", None)
        if rid:
            rid = _short_resource_id(rid)
        if subtype in _TYPE_SUBTYPES and rid and coverage_tracker.record_type_action(rid):
            bonus += 20.0

    return bonus


def calculate_reward(
    current_action,
    previous_action,
    activity,
    previous_activity,
    activities,
    crash,
    req_enabled,
    env,
    actions,
):
    """Calcula a recompensa baseada na transição."""
    reward = 0

    # Penalidade por repetir ação (mantida para desincentivar loops)
    if torch.equal(current_action, previous_action):
        reward = -2

    # Oráculo: +50 por requisito atendido (get_happypath), fallback verify_action
    if req_enabled:
        reward_path = env.get_happypath(actions[current_action[0][0]])
    else:
        reward_path = env.verify_action(actions[current_action[0][0]])

    if reward_path != 0:
        reward += reward_path

    # Penalidade por sair do app (home/outapp)
    if activity != previous_activity and activity in {"home", "outapp"}:
        reward -= 5

    # Nova activity descoberta: +10
    if activity not in activities:
        reward += 10

    # Crash
    if crash:
        reward = -5

    return reward
