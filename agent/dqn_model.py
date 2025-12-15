#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Q-Network (DQN) model for reinforcement learning agent.
"""

import logging
import math
import random
from collections import namedtuple

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable


USE_CUDA = torch.cuda.is_available()
FloatTensor = torch.cuda.FloatTensor if USE_CUDA else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if USE_CUDA else torch.LongTensor
ByteTensor = torch.cuda.ByteTensor if USE_CUDA else torch.ByteTensor
BoolTensor = torch.cuda.BoolTensor if USE_CUDA else torch.BoolTensor
Tensor = FloatTensor
Transition = namedtuple("Transition", ("state", "action", "next_state", "reward"))


class DQN(nn.Module):
    def __init__(self):
        super(DQN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, 30)

    def forward(self, x):
        print("Entrou na conv")
        logging.debug("Enter Convolution")
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = x.view(x.size(0), -1)
        return self.head(x)


class ReplayMemory:
    """Experience replay memory for storing transitions."""

    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, *args):
        """Saves a transition."""
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = Transition(*args)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


# Hyperparameters
BATCH_SIZE = 256
GAMMA = 0.999
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 500
dtype = FloatTensor

# Initialize model
model = DQN()
if USE_CUDA:
    model.cuda()

memory = ReplayMemory(10000)
optimizer = optim.RMSprop(model.parameters())
model.type(dtype)

steps_done = 0


def select_action(state, actions):
    """Select an action using epsilon-greedy policy."""
    global steps_done
    sample = random.random()
    eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(
        -1.0 * steps_done / EPS_DECAY
    )
    steps_done += 1
    if sample > eps_threshold:
        with torch.no_grad():
            vals = model(Variable(state.type(dtype))).data[0]
            max_idx = vals[: len(actions)].max(0)[1]
            return LongTensor([[max_idx]])
    else:
        if len(actions) >= 30:
            tensor_random = LongTensor([[random.randrange(29)]])
        else:
            tensor_random = LongTensor([[random.randrange(len(actions))]])
        return tensor_random


last_sync = 0


def optimize_model():
    """Perform one step of optimization on the DQN."""
    global last_sync
    if len(memory) < BATCH_SIZE:
        return
    transitions = memory.sample(BATCH_SIZE)
    batch = Transition(*zip(*transitions))

    non_final_mask = BoolTensor(
        tuple(map(lambda s: s is not None, batch.next_state))
    )
    non_final_next_states_t = torch.cat(
        tuple(s for s in batch.next_state if s is not None)
    ).type(dtype)

    with torch.no_grad():
        non_final_next_states = Variable(non_final_next_states_t)
        state_batch = Variable(torch.cat(batch.state))
        action_batch = Variable(torch.cat(batch.action))
        reward_batch = Variable(torch.cat(batch.reward))

        if USE_CUDA:
            state_batch = state_batch.cuda()
            action_batch = action_batch.cuda()

    state_action_values = model(state_batch).gather(1, action_batch)

    next_state_values = Variable(torch.zeros(BATCH_SIZE).type(Tensor))
    next_state_values[non_final_mask] = model(non_final_next_states).max(1)[0]

    with torch.no_grad():
        next_state_values

    expected_state_action_values = (next_state_values * GAMMA) + reward_batch

    expected_state_len = len(expected_state_action_values)
    state_action_values = state_action_values.view(expected_state_len)

    loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)

    optimizer.zero_grad()
    loss.backward()
    for param in model.parameters():
        param.grad.data.clamp_(-1, 1)
    optimizer.step()
