#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 29 17:21:08 2023

@author: eliane
"""


#import pandas as pd

import torch

from collections import namedtuple


import math
import random

#import timeit
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
#from torch.utils.tensorboard import SummaryWriter
#writer = SummaryWriter()

from torch.autograd import Variable
import logging


USE_CUDA = torch.cuda.is_available()
FloatTensor = torch.cuda.FloatTensor if USE_CUDA else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if USE_CUDA else torch.LongTensor
ByteTensor = torch.cuda.ByteTensor if USE_CUDA else torch.ByteTensor
BoolTensor = torch.cuda.BoolTensor if USE_CUDA else torch.BoolTensor
Tensor = FloatTensor
Transition = namedtuple('Transition', ('state', 'action', 'next_state', 'reward'))

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
       # img = x.view(x.size(0), -1)
        x = x.view(x.size(0), -1)
        return self.head(x)
#Experience Class   
Transition = namedtuple('Transition', ('state', 'action', 'next_state', 'reward'))

class ReplayMemory(object):

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

BATCH_SIZE = 256
GAMMA = 0.999
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 500
dtype = FloatTensor

model = DQN()
if USE_CUDA:
    model.cuda()

memory = ReplayMemory(10000)
optimizer = optim.RMSprop(model.parameters())
model.type(dtype)

steps_done = 0
def select_action(state, actions):
    global steps_done
    #random.seed(123) #fixed random by iteration
    sample = random.random()
    eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(-1. * steps_done / EPS_DECAY) #exploration rate
    steps_done += 1
    if sample > eps_threshold:
        with torch.no_grad():
            vals = model(Variable(state.type(dtype))).data[0] #exploit
            #logging.debug(vals.shape)
            max_idx = vals[:len(actions)].max(0)[1]
            #logging.debug(torch.LongTensor([[max_idx]]))
            return LongTensor([[max_idx]])
    else:
        if len(actions) >=30:
            tensor_random = LongTensor([[random.randrange(29)]])
        else:
            tensor_random = LongTensor([[random.randrange(len(actions))]])
           # logging.debug(LongTensor(LongTensor([[random.randrange(len(actions))]])))
        return tensor_random

#d = Device()
#d = torch.device("cuda" if torch.cuda.is_available() else "cpu")


last_sync = 0
def optimize_model():
    global last_sync
    if len(memory) < BATCH_SIZE:
        return
    transitions = memory.sample(BATCH_SIZE)
    # Transpose the batch (see http://stackoverflow.com/a/19343/3343043 for detailed explanation).
    batch = Transition(*zip(*transitions))
    
     # Compute a mask of non-final states and concatenate the batch elements
    non_final_mask = BoolTensor(tuple(map(lambda s: s is not None, batch.next_state)))
    # We don't want to backprop through the expected action values and volatile will save us
    # on temporarily changing the model parameters' requires_grad to False!
    non_final_next_states_t = torch.cat(tuple(s for s in batch.next_state if s is not None)).type(dtype)
    
    
    with torch.no_grad():
        
        non_final_next_states = Variable(non_final_next_states_t)
        # non_final_next_states = Variable(torch.cat([s for s in batch.next_state
        #                                         if s is not None]))
        state_batch = Variable(torch.cat(batch.state))
        action_batch = Variable(torch.cat(batch.action))
        reward_batch = Variable(torch.cat(batch.reward))

        if USE_CUDA:
            state_batch = state_batch.cuda()
            action_batch = action_batch.cuda()
    # Compute Q(s_t, a) - the model computes Q(s_t), then we select the columns of actions taken
    state_action_values = model(state_batch).gather(1, action_batch)

    # Compute V(s_{t+1}) for all next states.
    next_state_values = Variable(torch.zeros(BATCH_SIZE).type(Tensor))
    next_state_values[non_final_mask] = model(non_final_next_states).max(1)[0]
    # Now, we don't want to mess up the loss with a volatile flag, so let's clear it.
    # After this, we'll just end up with a Variable that has requires_grad=False
    with torch.no_grad():
        next_state_values
    # Compute the expected Q values
    expected_state_action_values = (next_state_values * GAMMA) + reward_batch

    expected_state_len = len(expected_state_action_values)
    state_action_values = state_action_values.view(expected_state_len)
    
    # Compute Huber loss
    loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)

    # Optimize the model
    optimizer.zero_grad()
    loss.backward()
    for param in model.parameters():
        param.grad.data.clamp_(-1, 1)
    optimizer.step()