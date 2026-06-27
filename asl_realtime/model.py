"""Small Transformer classifier for landmark sequences."""

from __future__ import annotations

import math

import torch
from torch import nn

from .constants import FEATURE_DIM


class PositionalEncoding(nn.Module):
    def __init__(self, dim: int, max_len: int = 512):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, dim, 2) * (-math.log(10000.0) / dim))
        pe = torch.zeros(max_len, dim)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class SignTransformer(nn.Module):
    def __init__(
        self,
        num_classes: int,
        input_dim: int = FEATURE_DIM,
        model_dim: int = 192,
        num_heads: int = 4,
        num_layers: int = 3,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.input_norm = nn.LayerNorm(input_dim)
        self.proj = nn.Linear(input_dim, model_dim)
        self.pos = PositionalEncoding(model_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=model_dim,
            nhead=num_heads,
            dim_feedforward=model_dim * 4,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.head = nn.Sequential(
            nn.LayerNorm(model_dim),
            nn.Linear(model_dim, model_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(model_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_norm(x)
        x = self.proj(x)
        x = self.pos(x)
        x = self.encoder(x)
        pooled = x.mean(dim=1)
        return self.head(pooled)


def build_model(num_classes: int, **kwargs) -> SignTransformer:
    return SignTransformer(num_classes=num_classes, **kwargs)

