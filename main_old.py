#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main entry point for RLMobTest - RL-based Android mobile app testing.
"""

import logging
import sys
import time
from itertools import count

import torch

from agent import dqn_model as d
from environment import AndroidEnv
from transcription import transcriber as tm
from utils.config_reader import ConfRead
from utils.constants import CONFIG_PATH, LOGS_PATH, TEST_CASES_PATH, TRANSCRIPTIONS_PATH

# Ensure logs directory exists
LOGS_PATH.mkdir(parents=True, exist_ok=True)

# Logger configuration
logging.basicConfig(
    filename=str(LOGS_PATH / "app.log"),
    filemode="a",
    format="%(levelname)s  %(asctime)s  %(message)s",
    level=logging.DEBUG,
)

# Read settings from config file
settings_reader = ConfRead(str(CONFIG_PATH / "settings.txt"))
lines = settings_reader.read_setting()
apk = lines[0]
app_package = lines[1]
wid = lines[2]
hei = lines[3]
cov = lines[4]
req = lines[5]
time_exec = lines[6]

# Initialize Android environment
env = AndroidEnv(apk, app_package, coverage_enabled=cov)


def run():
    """Execute the RL agent training loop."""
    env.install_app()
    episode_durations = []
    max_time = int(time_exec)
    start_time = time.time()

    for _ in count(1):
        # Initialize the environment and state
        previous_selected_action = d.LongTensor([[0]])
        activities = []
        state, actions = env.reset()
        previous_activity = "home"
        activities.append(previous_activity)
        activity_actual = activities[-1]
        env.nametc = env._create_tcfile(activity_actual)
        reward = 0

        if req == "yes":
            env.get_requirements()

        for t in count():
            if len(actions) > 0:
                # Check if width > height (landscape mode)
                if state.shape[3] > state.shape[2]:
                    state = state.permute(0, 1, 3, 2)

                # Select action
                action = d.select_action(state, actions)

                if torch.equal(action, previous_selected_action):
                    reward = -2
                else:
                    reward = reward + 1
                previous_selected_action = action

                if req == "yes":
                    reward_path = env.get_happypath(actions[action[0][0]])
                    if reward_path != 0:
                        reward = reward + reward_path
                    else:
                        reward = 0
                else:
                    reward_path = env.verify_action(actions[action[0][0]])
                    if reward_path != 0:
                        reward = reward + reward_path
                    else:
                        reward = 0

                next_state, actions, crash, activity = env.step(actions[action[0][0]])

                if next_state.shape[3] > next_state.shape[2]:
                    next_state = next_state.permute(0, 1, 3, 2)

                logging.debug("activity actual: " + activity_actual)
                print("activity actual: " + activity_actual)

                if activity_actual != activity:
                    activity_actual = activity
                    env.copy_coverage()
                    if (activity != "home") or (activity != "outapp"):
                        reward = reward
                    else:
                        env.device.press.back()
                        env._get_foreground()
                        reward = -5
                    with open(
                        f"{TEST_CASES_PATH.as_posix()}/{env.nametc}", mode="a"
                    ) as file:
                        file.write(f"\n\nGo to next activity: {activity}")
                    env.nametc = env._create_tcfile(activity)
                    env.tc_action = []

                if activity not in activities:
                    reward = reward + 10
                    activities.append(activity)

                if crash:
                    reward = -5
                    next_state = None

                reward_tensor = d.Tensor([reward])

                d.memory.push(state, action, next_state, reward_tensor)

                state = next_state

                d.optimize_model()

                if crash:
                    print(f"Epoch complete in {t + 1} steps")
                    logging.debug(f"Epoch complete in {t + 1} steps")
                    episode_durations.append(t + 1)
                    break

                if (time.time() - start_time) > max_time:
                    logging.debug("Time finished")
                    # Execute test case transcription
                    input_folder = TEST_CASES_PATH
                    output_folder = TRANSCRIPTIONS_PATH
                    tm.the_world_is_our(
                        input_folder=input_folder, output_folder=output_folder
                    )
                    sys.exit()

            else:
                print(f"Empty actions Epoch interrupted in {t + 1} steps")
                logging.debug(f"Empty actions Epoch interrupted in {t + 1} steps")
                episode_durations.append(t + 1)
                env.tc_action = []
                break


def main():
    """Main entry point."""
    run()


if __name__ == "__main__":
    main()
