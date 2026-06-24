"""Tier-1 rules mapping strategy (parity with SaaS prismrag.mapping.rules)."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np

from prismrag_patch.config import EMBED_DIM_PERSONAL
from prismrag_patch.embedding.deterministic import embed_texts
from prismrag_patch.mapping.base import MappingResult, MappingStrategy
from prismrag_patch.mapping.projection import project_sem_to_personal
from prismrag_patch.models import MappingConfig


class RulesStrategy(MappingStrategy):
    def __init__(
        self,
        mapping: MappingConfig | dict[str, Any],
        embed_fn: Callable[[list[str]], list[list[float] | None]] | None = None,
        embed_dim: int = EMBED_DIM_PERSONAL,
    ):
        if isinstance(mapping, dict):
            mapping = MappingConfig.from_dict(mapping)
        self._mapping = mapping
        self._embed_fn = embed_fn or embed_texts
        self._embed_dim = embed_dim

        self._rules: dict[str, str] = {}
        for r in mapping.rules:
            self._rules[r["word"].strip().lower()] = r["category_slug"]

        self._categories: list[str] = [c["slug"] for c in mapping.categories]
        self._cat_index: dict[str, int] = {slug: i for i, slug in enumerate(self._categories)}

    @property
    def categories(self) -> list[str]:
        return list(self._categories)

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self._mapping.rules)

    def assign(self, word: str, text: str, category_hint: str | None = None) -> MappingResult:
        return self.assign_batch([(word, text, category_hint)])[0]

    def assign_batch(
        self, records: list[tuple[str, str, str | None]]
    ) -> list[MappingResult]:
        words = [r[0].strip().lower() for r in records]
        texts = [r[1] for r in records]
        hints = [r[2] for r in records]
        cat_slugs = [self._lookup_category(w, h) for w, h in zip(words, hints)]

        sem_vecs = self._embed_fn(texts)
        failed = [texts[i] for i, v in enumerate(sem_vecs) if v is None]
        if failed:
            raise RuntimeError(
                f"Embedding failed for {len(failed)} chunk(s). "
                f"First failed text: {failed[0][:80]!r}"
            )

        results: list[MappingResult] = []
        for cat, sem_vec in zip(cat_slugs, sem_vecs):
            sem_arr = np.array(sem_vec, dtype=float)
            personal = project_sem_to_personal(sem_arr, cat, self._categories)
            results.append(MappingResult(
                category_slug=cat,
                embedding=personal,
                sem_embedding=sem_arr,
            ))
        return results

    def lookup_category(self, word: str, hint: str | None = None) -> str:
        return self._lookup_category(word.strip().lower(), hint)

    def infer_category_from_text(self, text: str) -> str | None:
        tokens = text.lower().split()
        scores: dict[str, float] = {}
        for token in tokens:
            slug = self._rules.get(token)
            if slug:
                weight = 1.0
                for r in self._mapping.rules:
                    if r["word"].strip().lower() == token:
                        weight = float(r.get("weight", 1.0))
                        break
                scores[slug] = scores.get(slug, 0.0) + weight
        if not scores:
            return None
        return max(scores, key=lambda k: scores[k])

    def _lookup_category(self, word: str, hint: str | None) -> str:
        if word in self._rules:
            return self._rules[word]
        if hint and hint in self._cat_index:
            return hint
        return self._categories[0] if self._categories else "default"
