"""LipNet architecture (3D-CNN + Bi-GRU + CTC).

Adapted from Fengdalu/LipNet-PyTorch (MIT License), which implements the model
from Assael et al. 2016. The checkpoint layout matches this module exactly:
input (B, C=3, T, H=64, W=128), output (B, T, 28) over [blank, space, A-Z].
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.init as init

# CTC label set: index 0 is the CTC blank; 1..27 map to these characters.
GRID_LETTERS = [" ", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
                "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]


class LipNet(nn.Module):
    def __init__(self, dropout_p: float = 0.5) -> None:
        super().__init__()
        self.conv1 = nn.Conv3d(3, 32, (3, 5, 5), (1, 2, 2), (1, 2, 2))
        self.pool1 = nn.MaxPool3d((1, 2, 2), (1, 2, 2))
        self.conv2 = nn.Conv3d(32, 64, (3, 5, 5), (1, 1, 1), (1, 2, 2))
        self.pool2 = nn.MaxPool3d((1, 2, 2), (1, 2, 2))
        self.conv3 = nn.Conv3d(64, 96, (3, 3, 3), (1, 1, 1), (1, 1, 1))
        self.pool3 = nn.MaxPool3d((1, 2, 2), (1, 2, 2))

        self.gru1 = nn.GRU(96 * 4 * 8, 256, 1, bidirectional=True)
        self.gru2 = nn.GRU(512, 256, 1, bidirectional=True)
        self.FC = nn.Linear(512, len(GRID_LETTERS) + 1)  # +1 for CTC blank

        self.dropout_p = dropout_p
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(dropout_p)
        self.dropout3d = nn.Dropout3d(dropout_p)
        self._init()

    def _init(self) -> None:
        for conv in (self.conv1, self.conv2, self.conv3):
            init.kaiming_normal_(conv.weight, nonlinearity="relu")
            init.constant_(conv.bias, 0)
        init.kaiming_normal_(self.FC.weight, nonlinearity="sigmoid")
        init.constant_(self.FC.bias, 0)
        for m in (self.gru1, self.gru2):
            stdv = math.sqrt(2 / (96 * 3 * 6 + 256))
            for i in range(0, 256 * 3, 256):
                init.uniform_(m.weight_ih_l0[i:i + 256], -math.sqrt(3) * stdv, math.sqrt(3) * stdv)
                init.orthogonal_(m.weight_hh_l0[i:i + 256])
                init.constant_(m.bias_ih_l0[i:i + 256], 0)
                init.uniform_(m.weight_ih_l0_reverse[i:i + 256], -math.sqrt(3) * stdv, math.sqrt(3) * stdv)
                init.orthogonal_(m.weight_hh_l0_reverse[i:i + 256])
                init.constant_(m.bias_ih_l0_reverse[i:i + 256], 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool1(self.dropout3d(self.relu(self.conv1(x))))
        x = self.pool2(self.dropout3d(self.relu(self.conv2(x))))
        x = self.pool3(self.dropout3d(self.relu(self.conv3(x))))
        # (B, C, T, H, W) -> (T, B, C*H*W)
        x = x.permute(2, 0, 1, 3, 4).contiguous()
        x = x.view(x.size(0), x.size(1), -1)
        self.gru1.flatten_parameters()
        self.gru2.flatten_parameters()
        x, _ = self.gru1(x)
        x = self.dropout(x)
        x, _ = self.gru2(x)
        x = self.dropout(x)
        x = self.FC(x)
        return x.permute(1, 0, 2).contiguous()  # (B, T, 28)
