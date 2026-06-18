# Embedding Strategy — PrismRAG

## Why we don't depend on Google or OpenAI for embeddings

PrismRAG and prismrag-patch are designed to be embedding-model agnostic.
The remapping math operates on any float vector regardless of origin.
This document explains the standard we follow and why.

---

## The open standard: ONNX

**ONNX** (Open Neural Network Exchange) is an open format for neural network
models maintained by Microsoft, Meta, and the Linux Foundation (ISO/IEC 22989).

Every major embedding model (BERT, MiniLM, E5, BGE) can be exported to ONNX
and run locally with `onnxruntime` — a single pip package, no API keys, no
external calls, no cost per token.

### How it works

```
Text
 │
 ▼
Tokenizer (HuggingFace tokenizers — Apache 2.0)
 │  Splits text into token IDs using a vocabulary file
 │
 ▼
ONNX Runtime (Microsoft — MIT license)
 │  Runs the neural network locally on CPU or GPU
 │  Same engine used inside Edge browser, Windows, Xbox
 │
 ▼
ONNX model file (.onnx)
 │  Exported from PyTorch/TensorFlow
 │  Available free on HuggingFace model hub
 │
 ▼
float[] vector — same quality as Gemini/OpenAI output
 │
 ▼
prismrag-patch → your database
```

### Code example (zero external dependencies)

```python
from onnxruntime import InferenceSession
from tokenizers import Tokenizer
import numpy as np

session   = InferenceSession("model.onnx")
tokenizer = Tokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

def embed(text: str) -> list[float]:
    enc    = tokenizer.encode(text)
    inputs = {
        "input_ids":      np.array([enc.ids],            dtype=np.int64),
        "attention_mask": np.array([enc.attention_mask],  dtype=np.int64),
    }
    output = session.run(None, inputs)[0][0]   # (384,)
    norm   = np.linalg.norm(output)
    return (output / norm).tolist()            # unit vector, ready for pgvector
```

---

## Recommended ONNX models

| Model | Dims | Size | Licence | Best for |
|-------|------|------|---------|----------|
| `all-MiniLM-L6-v2` | 384 | 80 MB | Apache 2.0 | General purpose, fastest CPU |
| `BGE-small-en-v1.5` | 384 | 130 MB | MIT | Better retrieval quality |
| `E5-small-v2` | 384 | 130 MB | MIT | Query/document asymmetric tasks |
| `BGE-large-en-v1.5` | 1024 | 1.3 GB | MIT | Highest quality, GPU recommended |

All available on [HuggingFace](https://huggingface.co/models?library=onnx).

---

## Why not Gemini / OpenAI?

| | ONNX local | Gemini / OpenAI |
|--|--|--|
| Cost | Free forever | Pay per chunk |
| Data privacy | Stays on your server | Sent to third party |
| Latency | 2–5 ms/chunk | 100–300 ms + network |
| Rate limits | None | Yes |
| Offline | Yes | No |
| Vendor lock-in | None | Yes |
| Standard | Open (ISO/IEC 22989) | Proprietary |

---

## Current production usage

The PrismRAG backend (`prismrag/embedding/gemini.py`) currently calls
`gemini-embedding-001` with `outputDimensionality=768` because Gemini was
the first model integrated. This is a configuration choice, not a requirement.

The `prismrag-patch` pip library has no embedding dependency at all —
callers pass in whatever vector they produce.

### Planned: built-in local embedder

`pip install "prismrag-patch[local]"` will ship a `LocalEmbedder` class
backed by ONNX Runtime so library users can embed without any external API:

```python
from prismrag_patch.embedder import LocalEmbedder

embedder = LocalEmbedder()          # downloads model once to ~/.cache
vec      = embedder.embed("text")   # 384-dim, runs on CPU, no API key
adapter.insert(text, vec, metadata={...})
```

---

## Replacing Gemini in the production backend

To switch the production backend from Gemini to a local ONNX model:

1. Install: `pip install onnxruntime tokenizers`
2. Download model: `python -c "from tokenizers import Tokenizer; Tokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')"`
3. Replace `prismrag/embedding/gemini.py` with an ONNX implementation
4. Update `EMBED_DIM_SEMANTIC` in `prismrag/config.py` from `768` to `384`
5. Re-run `ensure_table(dim=384)` — existing chunks need re-ingestion

---

## References

- ONNX spec: https://onnx.ai
- ONNX Runtime: https://onnxruntime.ai
- HuggingFace ONNX models: https://huggingface.co/models?library=onnx
- ISO/IEC 22989 (AI concepts and terminology): https://www.iso.org/standard/74296.html
- sentence-transformers benchmarks: https://www.sbert.net/docs/pretrained_models.html
