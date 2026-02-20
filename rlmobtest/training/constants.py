from collections import namedtuple

import torch

# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Tensor types for compatibility
FloatTensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if torch.cuda.is_available() else torch.LongTensor
BoolTensor = torch.cuda.BoolTensor if torch.cuda.is_available() else torch.BoolTensor
Tensor = FloatTensor
Transition = namedtuple("Transition", ("state", "action", "next_state", "reward"))
