"""Reward calculation for RL training."""

import torch


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

    # Penalidade por repetir ação
    if torch.equal(current_action, previous_action):
        reward = -2
    else:
        reward += 1

    # Verificar happy path ou ação
    if req_enabled:
        reward_path = env.get_happypath(actions[current_action[0][0]])
    else:
        reward_path = env.verify_action(actions[current_action[0][0]])

    if reward_path != 0:
        reward += reward_path

    # Mudança de activity
    if activity != previous_activity:
        if activity not in {"home", "outapp"}:
            reward += 5
        else:
            reward -= 5

    # Nova activity descoberta
    if activity not in activities:
        reward += 10

    # Crash
    if crash:
        reward = -5

    return reward
