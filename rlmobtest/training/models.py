import torch.nn as nn
import torch.nn.functional as F

from rlmobtest.training.constants import device


class OriginalDQN(nn.Module):
    """DQN original do projeto."""

    def __init__(self, num_actions=30):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=5, stride=2)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=5, stride=2)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 32, kernel_size=5, stride=2)
        self.bn3 = nn.BatchNorm2d(32)
        self.head = nn.Linear(448, num_actions)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = x.view(x.size(0), -1)
        return self.head(x)


class DuelingDQN(nn.Module):
    """Dueling DQN - separa Value e Advantage streams."""

    def __init__(self, num_actions=30):
        super().__init__()

        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=8, stride=4),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1),
            nn.ReLU(),
        )

        self._feature_size = None
        self.num_actions = num_actions
        self.value_stream = None
        self.advantage_stream = None

    def _initialize_fc(self, feature_size):
        self.value_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, 1)
        ).to(device)

        self.advantage_stream = nn.Sequential(
            nn.Linear(feature_size, 512), nn.ReLU(), nn.Linear(512, self.num_actions)
        ).to(device)

    def forward(self, x):
        features = self.features(x)
        features = features.view(features.size(0), -1)

        if self.value_stream is None:
            self._feature_size = features.size(1)
            self._initialize_fc(self._feature_size)

        value = self.value_stream(features)
        advantage = self.advantage_stream(features)
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        return q_values
