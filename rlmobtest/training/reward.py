"""Reward calculation for RL training."""

import torch


def coverage_reward(prev_coverage: dict, curr_coverage: dict) -> float:
    """Bônus de recompensa por novos caminhos de código cobertos desde a última verificação.

    Args:
        prev_coverage: Métricas de cobertura anteriores {line_pct, branch_pct, method_pct}.
        curr_coverage: Métricas de cobertura atuais {line_pct, branch_pct, method_pct}.

    Returns:
        Recompensa incremental positiva quando há aumento de cobertura, 0 caso contrário.
    """
    if not prev_coverage or not curr_coverage:
        return 0.0

    delta_lines = curr_coverage.get("line_pct", 0.0) - prev_coverage.get("line_pct", 0.0)
    delta_branches = curr_coverage.get("branch_pct", 0.0) - prev_coverage.get("branch_pct", 0.0)

    reward = 0.0
    if delta_lines > 0:
        reward += delta_lines * 5      # +5 por cada 1% de linha nova coberta
    if delta_branches > 0:
        reward += delta_branches * 10  # +10 por cada 1% de branch novo (mais raro, mais valioso)
    return reward


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
