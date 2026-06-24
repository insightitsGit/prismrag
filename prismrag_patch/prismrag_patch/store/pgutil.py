"""Postgres / pgvector helpers for the library store."""
from __future__ import annotations

import json
from typing import Any

import numpy as np


def vector_to_pg(vec: Any) -> str:
    """Convert a python list/array to pgvector literal '[x,y,...]'."""
    return "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"


def parse_vector(raw: str | None) -> np.ndarray | None:
    if not raw:
        return None
    return np.array(json.loads(raw), dtype=float)
