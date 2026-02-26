"""Device configuration and tensor type aliases for PyTorch."""

import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

FloatTensor = torch.cuda.FloatTensor if torch.cuda.is_available() else torch.FloatTensor
LongTensor = torch.cuda.LongTensor if torch.cuda.is_available() else torch.LongTensor
BoolTensor = torch.cuda.BoolTensor if torch.cuda.is_available() else torch.BoolTensor
Tensor = FloatTensor
