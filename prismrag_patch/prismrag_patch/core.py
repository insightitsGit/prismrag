"""
PrismRAGPatch — Tier-1 deterministic category projection (OSS, no license).

Uses the same RulesStrategy projection as the SaaS API when vectors are 768-d.
For other dimensions, falls back to category-token scoring + spherical blend.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from prismrag_patch.config import EMBED_DIM_SEMANTIC
from prismrag_patch.mapping.projection import project_sem_to_personal
from prismrag_patch.mapping.rules import RulesStrategy
from prismrag_patch.models import MappingConfig

log = logging.getLogger(__name__)


class PrismRAGPatch:
    def __init__(
        self,
        mapping: Dict[str, Any],
        license_key: str | None = None,
        blend_alpha: float = 0.35,
        embed_fn=None,
    ) -> None:
        if license_key:
            log.debug("license_key ignored — OSS build has no license gate")
        self.mapping = mapping
        self.blend_alpha = float(blend_alpha)
        self._strategy = RulesStrategy(MappingConfig.from_dict(mapping), embed_fn=embed_fn)

        self._categories: List[Dict] = mapping.get("categories", [])
        self._cat_slugs = [c["slug"] for c in self._categories]

        log.info(
            "prismrag-patch: initialized — %d categories, %d rules, alpha=%.2f",
            len(self._categories), len(self._strategy.rules), self.blend_alpha,
        )

    def remap_vector(self, vector: List[float], text: str = "") -> List[float]:
        v = np.array(vector, dtype=np.float32)
        if len(v) == EMBED_DIM_SEMANTIC and text:
            cat = self._strategy.infer_category_from_text(text)
            if cat:
                personal = project_sem_to_personal(v.astype(float), cat, self._cat_slugs)
                return personal.astype(np.float32).tolist()

        cat_slug = self._strategy.infer_category_from_text(text) if text else None
        if cat_slug is None:
            return vector

        cat_idx = self._cat_slugs.index(cat_slug) if cat_slug in self._cat_slugs else 0
        dim = len(v)
        direction = np.zeros(dim, dtype=np.float32)
        cluster_size = max(1, dim // max(1, len(self._categories)))
        start = (cat_idx * cluster_size) % dim
        end = min(start + cluster_size, dim)
        direction[start:end] = 1.0
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction /= norm

        v_norm = np.linalg.norm(v)
        remapped = (1.0 - self.blend_alpha) * v + self.blend_alpha * v_norm * direction
        r_norm = np.linalg.norm(remapped)
        if r_norm > 0:
            remapped /= r_norm
        return remapped.tolist()

    def project(self, text: str, vector: List[float]) -> Dict[str, Any]:
        cat_slug = self._strategy.infer_category_from_text(text)
        cat = next((c for c in self._categories if c["slug"] == cat_slug), None)
        remapped = self.remap_vector(vector, text)
        return {
            "vector": remapped,
            "category": cat,
            "original_vector": vector,
        }

    def category_for(self, text: str) -> Optional[Dict]:
        slug = self._strategy.infer_category_from_text(text)
        if slug is None:
            return None
        return next((c for c in self._categories if c["slug"] == slug), None)
