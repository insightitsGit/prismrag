# Performance notes

Honest scope: this package does not yet publish large-scale latency/throughput SLOs in-repo.

## What is measured today

| Signal | Source | Notes |
|--------|--------|-------|
| Demo / verification run | `examples/demo_app` | Small mapping; end-to-end demo + 13 tests typically &lt; 1–2s locally |
| Search latency test | `tests/test_lib_step04_search.py` | Asserts search under ~3s on fixture data |
| INFO.md benchmark | Product notes | Tiny healthcare demo mapping on MemoryStore |

These are **functional** benches, not production capacity claims.

## What dominates runtime in practice

1. Your **`embed_fn`** (API or local model)  
2. Store I/O (Postgres / remote vector DB)  
3. Graph build size (rules × records) on ingest  

## Guidance

- Prototype on `MemoryStore` with deterministic embeds.  
- Production: real embedder + PostgresStore or adapters; size mappings deliberately.  
- Use `category_filter` to reduce candidate sets when product allows.  

## What we do not claim

- Guaranteed p99 latency  
- Million-chunk HNSW numbers for MemoryStore  
- Parity with every commercial GraphRAG SaaS scale profile  

Contributions with reproducible benchmarks are welcome.
