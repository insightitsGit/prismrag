"""PrismRAG — Tier 2: MLPStrategy.

Builds on top of Tier-1 RulesStrategy:
  1. Use the explicit word→category rules to generate (anchor, word) training pairs
     (words in the same category should be close; words in different categories far apart).
  2. Train a 3-layer PyTorch MLP using InfoNCE + anchor repulsion loss.
  3. Project ALL records through the trained MLP for the final embeddings.

The MLP learns the *boundaries* between categories from the explicit rule set,
then generalises those boundaries to new vocabulary that wasn't in the rules.
"""
from __future__ import annotations

import io
import logging
from collections import defaultdict
from typing import Sequence

import numpy as np

from prismrag.config import (
    EMBED_DIM_PERSONAL,
    EMBED_DIM_SEMANTIC,
    MLP_HIDDEN_DIM,
    MLP_TEMPERATURE,
    MLP_REPULSION_WEIGHT,
    MLP_TRAIN_EPOCHS,
    MLP_TRAIN_LR,
    MLP_RECALL_TARGET,
    MLP_VAL_HOLDOUT,
)
from prismrag.embedding.gemini import embed_texts
from prismrag.mapping.base import MappingResult, MappingStrategy
from prismrag.models import MappingConfigIn

logger = logging.getLogger(__name__)


# ── PyTorch MLP ───────────────────────────────────────────────────────────────

def _build_mlp(input_dim: int = EMBED_DIM_SEMANTIC, embed_dim: int = EMBED_DIM_PERSONAL):
    try:
        import torch
        import torch.nn as nn

        hidden = max(MLP_HIDDEN_DIM, 2 * embed_dim)

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
    except ImportError:
        raise RuntimeError("PyTorch is required for Tier-2 MLP strategy: pip install torch")


def _encode(model, vecs: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        t = torch.tensor(vecs, dtype=torch.float32)
        return model(t).numpy()


# ── Loss functions ────────────────────────────────────────────────────────────

def _infonce_loss(model, pairs, all_vecs, all_words, temperature, device):
    import torch
    import torch.nn.functional as F

    anchors   = list({p[0] for p in pairs})
    anchor_idx = {w: i for i, w in enumerate(anchors)}
    vocab      = list(all_words)
    vocab_idx  = {w: i for i, w in enumerate(vocab)}

    anchor_embs = torch.tensor(all_vecs[[vocab_idx[a] for a in anchors]], dtype=torch.float32)
    anchor_out  = model(anchor_embs)   # (A, D)

    pos_mask = torch.zeros(len(anchors), len(vocab))
    for anc, pos in pairs:
        ai = anchor_idx.get(anc, -1)
        pi = vocab_idx.get(pos, -1)
        if ai >= 0 and pi >= 0:
            pos_mask[ai, pi] = 1.0

    all_out = model(torch.tensor(all_vecs, dtype=torch.float32))   # (V, D)
    logits  = anchor_out @ all_out.T / temperature                   # (A, V)

    loss = torch.tensor(0.0)
    for ai in range(len(anchors)):
        pos_indices = pos_mask[ai].nonzero(as_tuple=True)[0]
        if len(pos_indices) == 0:
            continue
        log_sum_exp = torch.logsumexp(logits[ai], dim=0)
        pos_sum     = logits[ai][pos_indices].sum() / len(pos_indices)
        loss        = loss + log_sum_exp - pos_sum

    # Anchor repulsion: push different-category anchors apart
    if len(anchors) > 1:
        norm_a = F.normalize(anchor_out, dim=-1)
        sim_aa = norm_a @ norm_a.T
        # Repel all pairs (they are different anchors = different categories)
        triu = torch.triu(sim_aa, diagonal=1)
        rep_loss = MLP_REPULSION_WEIGHT * triu.mean()
        loss = loss + rep_loss

    return loss / max(len(anchors), 1)


# ── Recall@k evaluation ───────────────────────────────────────────────────────

def _recall_at_k(model, val_pairs, vocab_words, vocab_vecs, k=10) -> float:
    if not val_pairs or not vocab_words:
        return 0.0
    vocab_out = _encode(model, vocab_vecs)                  # (V, D)
    vocab_idx = {w: i for i, w in enumerate(vocab_words)}
    hits = 0
    for anchor, target in val_pairs:
        if anchor not in vocab_idx:
            continue
        a_vec = vocab_out[vocab_idx[anchor]]
        sims  = vocab_out @ a_vec
        top_k = np.argsort(-sims)[:k]
        if vocab_idx.get(target, -1) in top_k:
            hits += 1
    return hits / len(val_pairs)


# ── Main training function ────────────────────────────────────────────────────

def train_mlp(
    mapping_config: MappingConfigIn,
    word_texts: dict[str, str],   # word → representative text
    embed_dim: int = EMBED_DIM_PERSONAL,
    epochs: int = MLP_TRAIN_EPOCHS,
    lr: float = MLP_TRAIN_LR,
    recall_target: float = MLP_RECALL_TARGET,
) -> tuple[object, float]:
    """
    Train the personal MLP from the Tier-1 rules.

    Returns (trained_model, val_recall).
    """
    import torch
    import torch.optim as optim
    from torch.optim.lr_scheduler import CosineAnnealingLR

    # Build training pairs from rules: same category → (anchor, word) positives
    by_cat: dict[str, list[str]] = defaultdict(list)
    for rule in mapping_config.rules:
        by_cat[rule.category_slug].append(rule.word.strip().lower())

    pairs: list[tuple[str, str]] = []
    for words in by_cat.values():
        for i, anchor in enumerate(words):
            for j, word in enumerate(words):
                if i != j:
                    pairs.append((anchor, word))

    if not pairs:
        raise ValueError("No training pairs could be derived from the mapping rules. "
                         "Ensure at least two words share a category.")

    # Val holdout: last N words per category
    train_pairs, val_pairs = [], []
    for words in by_cat.values():
        if len(words) > MLP_VAL_HOLDOUT:
            hold = set(words[-MLP_VAL_HOLDOUT:])
            for a, b in [(a, b) for a, b in pairs if a in words and b in words]:
                if a in hold or b in hold:
                    val_pairs.append((a, b))
                else:
                    train_pairs.append((a, b))
        else:
            train_pairs.extend((a, b) for a, b in pairs if a in words and b in words)

    if not train_pairs:
        train_pairs = pairs
        val_pairs   = pairs[:max(1, len(pairs)//5)]

    # Embed all unique words
    vocab = list({w for p in pairs for w in p} | set(word_texts.keys()))
    texts = [word_texts.get(w, w) for w in vocab]
    sem_vecs_raw = embed_texts(texts)
    sem_vecs = np.array([v if v is not None else [0.0] * 768 for v in sem_vecs_raw], dtype=float)

    model = _build_mlp(input_dim=sem_vecs.shape[1], embed_dim=embed_dim)
    optimiser = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimiser, T_max=epochs)

    best_recall = 0.0
    best_state  = None

    for epoch in range(epochs):
        model.train()
        optimiser.zero_grad()
        loss = _infonce_loss(model, train_pairs, sem_vecs, vocab, MLP_TEMPERATURE, device=None)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimiser.step()
        scheduler.step()

        if (epoch + 1) % 20 == 0:
            model.eval()
            recall = _recall_at_k(model, val_pairs, vocab, sem_vecs)
            logger.debug("Epoch %d/%d  loss=%.4f  val_recall=%.3f", epoch+1, epochs, loss.item(), recall)
            if recall > best_recall:
                best_recall = recall
                buf = io.BytesIO()
                torch.save(model.state_dict(), buf)
                best_state = buf.getvalue()
            if recall >= recall_target:
                logger.info("Recall target %.2f reached at epoch %d", recall_target, epoch + 1)
                break

    if best_state:
        model.load_state_dict(torch.load(io.BytesIO(best_state), weights_only=True))

    return model, best_recall


def serialize_mlp(model) -> bytes:
    import torch, io
    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return buf.getvalue()


def load_mlp(blob: bytes, input_dim: int = EMBED_DIM_SEMANTIC, embed_dim: int = EMBED_DIM_PERSONAL):
    import torch, io
    model = _build_mlp(input_dim=input_dim, embed_dim=embed_dim)
    model.load_state_dict(torch.load(io.BytesIO(blob), weights_only=True))
    model.eval()
    return model


# ── MLPStrategy class ─────────────────────────────────────────────────────────

class MLPStrategy(MappingStrategy):
    """
    Tier-2 strategy: trains a personal MLP on the Tier-1 rules,
    then projects all records through the MLP for final embeddings.

    Falls back to RulesStrategy if training fails or torch is unavailable.
    """

    def __init__(
        self,
        mapping_config: MappingConfigIn,
        embed_dim: int = EMBED_DIM_PERSONAL,
        word_texts: dict[str, str] | None = None,
        epochs: int = MLP_TRAIN_EPOCHS,
        recall_target: float = MLP_RECALL_TARGET,
    ):
        from prismrag.mapping.rules import RulesStrategy
        self._rules_strategy = RulesStrategy(mapping_config, embed_dim=embed_dim)
        self._mapping_config = mapping_config
        self._embed_dim      = embed_dim
        self._word_texts     = word_texts or {}
        self._epochs         = epochs
        self._recall_target  = recall_target
        self._model          = None
        self._recall: float  = 0.0
        self._weights_blob: bytes | None = None

    def train(self) -> float:
        """Train MLP. Returns val_recall. Call before assign_batch for Tier-2 results."""
        try:
            model, recall = train_mlp(
                self._mapping_config,
                self._word_texts,
                embed_dim=self._embed_dim,
                epochs=self._epochs,
                recall_target=self._recall_target,
            )
            self._model        = model
            self._recall       = recall
            self._weights_blob = serialize_mlp(model)
            logger.info("MLP trained — val_recall=%.3f", recall)
            return recall
        except Exception as exc:
            logger.warning("MLP training failed, falling back to RulesStrategy: %s", exc)
            return 0.0

    @property
    def weights_blob(self) -> bytes | None:
        return self._weights_blob

    @property
    def val_recall(self) -> float:
        return self._recall

    def assign_batch(
        self, records: list[tuple[str, str, str | None]]
    ) -> list[MappingResult]:
        # Get Tier-1 assignments for category slugs
        tier1 = self._rules_strategy.assign_batch(records)

        if self._model is None:
            # Not yet trained — return Tier-1 results
            return tier1

        # Override embeddings with MLP projections
        texts   = [r[1] for r in records]
        sem_raw = embed_texts(texts)
        sem_arr = np.array([v if v is not None else [0.0]*768 for v in sem_raw], dtype=float)
        mlp_out = _encode(self._model, sem_arr)   # (N, 256)

        results = []
        for i, t1 in enumerate(tier1):
            results.append(MappingResult(
                category_slug=t1.category_slug,
                embedding=mlp_out[i],
                sem_embedding=sem_arr[i],
            ))
        return results

    def assign(self, word: str, text: str, category_hint: str | None = None) -> MappingResult:
        return self.assign_batch([(word, text, category_hint)])[0]
