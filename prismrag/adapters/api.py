"""PrismRAG — API adapter (paginated REST endpoint)."""
from __future__ import annotations

from typing import Iterator

import requests

from prismrag.adapters.base import Record, SourceAdapter
from prismrag.models import APISourceConfig


class APIAdapter(SourceAdapter):
    """
    Stream records from a paginated REST API.

    Expects JSON responses in the shape:
      { "data": [...], "next_page": 2 | null }
    or a plain list (single page).
    """

    def __init__(self, config: APISourceConfig):
        self._config = config

    def stream(self) -> Iterator[Record]:
        cfg   = self._config
        page  = 1
        total = 0

        while True:
            params = {cfg.page_param: page, "page_size": cfg.page_size}
            try:
                resp = requests.get(cfg.url, headers=cfg.headers, params=params, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                raise RuntimeError(f"APIAdapter fetch failed (page {page}): {exc}") from exc

            body = resp.json()

            # Support { "data": [...] } or plain list
            if isinstance(body, list):
                records = body
                has_next = False
            else:
                records  = body.get("data") or body.get("items") or body.get("results") or []
                has_next = bool(body.get("next_page") or body.get("next") or body.get("has_more"))

            if not records:
                break

            for i, item in enumerate(records):
                word = str(item.get(cfg.word_field) or "").strip().lower()
                text = str(item.get(cfg.text_field) or "").strip()
                if not word:
                    continue
                if not text:
                    text = word
                ref = str(item.get("id") or item.get("ref") or f"page{page}:{i}")
                yield Record(
                    word=word,
                    text=text,
                    ref=ref,
                    metadata={k: v for k, v in item.items()
                               if k not in (cfg.word_field, cfg.text_field)},
                )
                total += 1

            if not has_next:
                break
            page += 1
