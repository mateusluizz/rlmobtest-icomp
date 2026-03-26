"""DQN agent implementations (Original and Improved)."""

import math
import random

import torch
import torch.nn.functional as F
from torch import optim

from rlmobtest.training.device import BoolTensor, FloatTensor, LongTensor, Tensor, device
from rlmobtest.training.memory import PrioritizedReplayMemory, ReplayMemory
from rlmobtest.training.models import DuelingDQN, OriginalDQN


class OriginalAgent:
    """Agente DQN original (compatibilidade com código legado)."""

    def __init__(self, num_actions=30):
        self.num_actions = num_actions
        self.model = OriginalDQN(num_actions).to(device)
        self.model.type(FloatTensor)

        self.memory = ReplayMemory(50000)
        self.optimizer = optim.RMSprop(self.model.parameters())

        self.batch_size = 128
        self.gamma = 0.99
        self.eps_start = 0.9
        self.eps_end = 0.05
        self.eps_decay = 2000

        self.steps_done = 0

    def get_epsilon(self):
        return self.eps_end + (self.eps_start - self.eps_end) * math.exp(
            -1.0 * self.steps_done / self.eps_decay
        )

    def select_action(self, state, actions):
        epsilon = self.get_epsilon()
        self.steps_done += 1

        if random.random() > epsilon:
            with torch.no_grad():
                vals = self.model(state.type(FloatTensor)).data[0]
                max_idx = vals[: len(actions)].max(0)[1]
                return LongTensor([[max_idx]]), epsilon, vals.max().item()
        else:
            n = min(len(actions), 29)
            return LongTensor([[random.randrange(n)]]), epsilon, 0.0

    def optimize(self):
        if len(self.memory) < self.batch_size:
            return None

        transitions = self.memory.sample(self.batch_size)
        batch = list(zip(*transitions))

        non_final_mask = BoolTensor(tuple(map(lambda s: s is not None, batch[2])))
        non_final_next_states = torch.cat([s for s in batch[2] if s is not None]).type(FloatTensor)

        state_batch = torch.cat(batch[0]).type(FloatTensor)
        action_batch = torch.cat(batch[1])
        reward_batch = torch.cat(batch[3])

        if torch.cuda.is_available():
            state_batch = state_batch.cuda()
            action_batch = action_batch.cuda()

        state_action_values = self.model(state_batch).gather(1, action_batch)

        next_state_values = torch.zeros(self.batch_size).type(Tensor)
        next_state_values[non_final_mask] = self.model(non_final_next_states).max(1)[0]

        expected_state_action_values = (next_state_values * self.gamma) + reward_batch

        state_action_values = state_action_values.view(self.batch_size)
        loss = F.smooth_l1_loss(state_action_values, expected_state_action_values)

        self.optimizer.zero_grad()
        loss.backward()
        for param in self.model.parameters():
            param.grad.data.clamp_(-1, 1)
        self.optimizer.step()

        return loss.item()

    def reset_epsilon(self) -> None:
        """Reset epsilon to force more exploration (call when coverage stagnates)."""
        self.steps_done = 0


class ImprovedAgent:
    """Agente DQN melhorado com Double DQN, Target Network, Dueling e PER."""

    def __init__(self, num_actions=30, use_dueling=True, use_per=True):
        self.num_actions = num_actions
        self.use_per = use_per

        ModelClass = DuelingDQN if use_dueling else OriginalDQN
        self.policy_net = ModelClass(num_actions).to(device)
        self.target_net = ModelClass(num_actions).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=1e-4)

        if use_per:
            self.memory = PrioritizedReplayMemory(50000)
        else:
            self.memory = ReplayMemory(50000)

        self.batch_size = 128
        self.gamma = 0.99
        self.eps_start = 1.0
        self.eps_end = 0.01
        self.eps_decay = 10000
        self.target_update = 1000

        self.steps_done = 0

    def get_epsilon(self):
        return self.eps_end + (self.eps_start - self.eps_end) * math.exp(
            -1.0 * self.steps_done / self.eps_decay
        )

    def select_action(self, state, actions):
        epsilon = self.get_epsilon()
        self.steps_done += 1

        if random.random() > epsilon:
            with torch.no_grad():
                state = state.to(device)
                q_values = self.policy_net(state)
                q_values = q_values[0, : len(actions)]
                action_idx = q_values.argmax().item()
                return LongTensor([[action_idx]]), epsilon, q_values.max().item()
        else:
            n = min(len(actions), self.num_actions - 1)
            return LongTensor([[random.randrange(n)]]), epsilon, 0.0

    def optimize(self):
        if len(self.memory) < self.batch_size:
            return None

        if self.use_per:
            samples, indices, weights = self.memory.sample(self.batch_size)
            if not samples:
                return None
        else:
            samples = self.memory.sample(self.batch_size)
            indices = None
            weights = torch.ones(self.batch_size, device=device)

        batch = list(zip(*samples))

        state_batch = torch.cat([s for s in batch[0] if s is not None]).to(device)
        action_batch = torch.cat(batch[1]).to(device)
        reward_batch = torch.cat(batch[3]).to(device)

        non_final_mask = torch.tensor(
            [s is not None for s in batch[2]], device=device, dtype=torch.bool
        )
        non_final_next_states = (
            torch.cat([s for s in batch[2] if s is not None]).to(device)
            if any(non_final_mask)
            else None
        )

        state_action_values = self.policy_net(state_batch).gather(1, action_batch)

        next_state_values = torch.zeros(self.batch_size, device=device)
        if non_final_next_states is not None:
            with torch.no_grad():
                next_actions = self.policy_net(non_final_next_states).argmax(1).unsqueeze(1)
                next_state_values[non_final_mask] = (
                    self.target_net(non_final_next_states).gather(1, next_actions).squeeze()
                )

        expected_state_action_values = reward_batch + (self.gamma * next_state_values)

        td_errors = (
            (state_action_values.squeeze() - expected_state_action_values).detach().cpu().numpy()
        )

        loss = (
            weights
            * F.smooth_l1_loss(
                state_action_values.squeeze(),
                expected_state_action_values,
                reduction="none",
            )
        ).mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10)
        self.optimizer.step()

        if self.use_per and indices is not None:
            self.memory.update_priorities(indices, td_errors)

        if self.steps_done % self.target_update == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def reset_epsilon(self) -> None:
        """Reset epsilon to force more exploration (call when coverage stagnates)."""
        self.steps_done = 0
