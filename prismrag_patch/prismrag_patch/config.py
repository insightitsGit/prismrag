"""PrismRAG library — configuration defaults (mirrors SaaS prismrag.config)."""
from __future__ import annotations

EMBED_DIM_SEMANTIC = 768
EMBED_DIM_PERSONAL = 256

SEM_EDGE_THRESHOLD = 0.70
RETRIEVAL_TOP_K = 32
RETRIEVAL_TOP_COMMUNITIES = 3
BFS_MAX_HOPS = 2
BFS_MAX_WORDS = 200
INGEST_BATCH_SIZE = 256
LOW_QUALITY_THRESHOLD = 0.45
