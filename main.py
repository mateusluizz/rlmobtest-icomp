#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 29 17:23:03 2023

@author: eliane
"""

import logging
import sys
import time
from itertools import count

import torch

import transcription_module as tm
from constants import TEST_CASES_PATH, TRANSCRIPTIONS_PATH

# Importar funções dos scripts existentes
from rlmobtest_elianecollins import conf as conf
from rlmobtest_elianecollins import deeprl as d
from rlmobtest_elianecollins import mobtest_env as mob

# Configuração do logger
logging.basicConfig(
    filename="tmp.log",
    filemode="a",
    format="%(levelname)s  %(asctime)s  %(message)s",
    level=logging.DEBUG,
)

# Abrir arquivo de configurações
settings_reader = conf.ConfRead("settings.txt")
lines = settings_reader.read_setting()
apk = lines[0]
app_package = lines[1]
wid = lines[2]
hei = lines[3]
cov = lines[4]
req = lines[5]
time_exec = lines[6]

# Inicializar ambiente Android
env = mob.AndroidEnv(apk, app_package)


# Função para executar o treinamento do agente de RL
def run():
    env.install_app()
    episode_durations = []
    max_time = int(time_exec)
    start_time = time.time()  # remember when we started
    for i_episode in count(1):
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
                # Verifica se largura é maior que altura (modo landscape)
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
                    file = open(TEST_CASES_PATH.as_posix() + f"{env.nametc}/", mode="a")
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
                    # Executar transcrição de test cases
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


# Função principal
def main():
    # Executar treinamento do agente RL
    run()


if __name__ == "__main__":
    main()
