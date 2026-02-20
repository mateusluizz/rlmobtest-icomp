#!/usr/bin/env python3
"""
Main entry point for RLMobTest - RL-based Android mobile app testing.

All training logic has been moved to rlmobtest/training/:
  - training/constants.py   : device, tensor types, Transition
  - training/metrics.py     : TrainingMetrics, setup_logging
  - training/checkpoint.py  : ModelCheckpoint
  - training/memory.py      : ReplayMemory, PrioritizedReplayMemory
  - training/models.py      : OriginalDQN, DuelingDQN
  - training/agents.py      : OriginalAgent, ImprovedAgent
  - training/reward.py      : calculate_reward
  - training/progress.py    : TrainingProgress
  - training/runner.py      : run, run_all, run_with_phases
"""

from rlmobtest.training.runner import main

if __name__ == "__main__":
    main()
