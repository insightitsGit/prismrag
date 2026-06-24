"""Tier-2 MLP load/save (optional — requires torch)."""
from __future__ import annotations

import io

from prismrag_patch.config import EMBED_DIM_PERSONAL, EMBED_DIM_SEMANTIC


def _build_mlp(input_dim: int = EMBED_DIM_SEMANTIC, embed_dim: int = EMBED_DIM_PERSONAL):
    import torch
    import torch.nn as nn

    hidden = max(512, 2 * embed_dim)

    class _MLP(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.LayerNorm(hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.LayerNorm(hidden),
                nn.ReLU(),
                nn.Linear(hidden, embed_dim),
            )

        def forward(self, x):
            out = self.net(x)
            return out / (out.norm(dim=-1, keepdim=True).clamp(min=1e-8))

    return _MLP()


def load_mlp(blob: bytes, input_dim: int = EMBED_DIM_SEMANTIC, embed_dim: int = EMBED_DIM_PERSONAL):
    import torch
    model = _build_mlp(input_dim, embed_dim)
    buf = io.BytesIO(blob)
    state = torch.load(buf, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model


def serialize_mlp(model) -> bytes:
    import torch
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return buf.getvalue()
