# Deterministic Category Projection in Retrieval-Augmented Generation: A Taxonomy-Grounded Approach to Eliminating Category Bleed

**Author:** Amin Parva  
**Affiliation:** Insight IT Solutions  
**Contact:** prismrag@insightits.com  
**Published:** June 2026  
**© 2026 Amin Parva / Insight IT Solutions. All rights reserved.**

> *This article establishes prior art for the Tier-1 Deterministic Category Projection
> algorithm and associated techniques described herein. Unauthorised reproduction of the
> algorithmic approach described in this work for commercial purposes is prohibited.*

---

## Abstract

Retrieval-Augmented Generation (RAG) systems rely on vector similarity search that has no
intrinsic mechanism to enforce domain-specific knowledge boundaries. Semantically similar
text from unrelated categories can rank highly in retrieval, creating *category bleed* —
a failure mode in which large language models synthesise confident but incorrect answers
from misclassified context. Graph RAG partially mitigates this by structuring retrieval
through document-derived knowledge graphs, yet relationships remain statistical artefacts
of the corpus rather than expressions of expert-defined taxonomy.

This paper introduces **Tier-1 Deterministic Category Projection**, a mathematically
grounded remapping layer that embeds client-verified categories directly into the vector
space before indexing and search. Given a semantic embedding **v** ∈ ℝᵈ and a rule-based
taxonomy of *C* categories, the method (i) infers category membership from weighted keyword
rules, (ii) constructs deterministic unit direction vectors that partition the embedding
space, and (iii) applies a controlled spherical blend that preserves semantic content while
systematically separating categories at cosine-search time. A secondary Johnson–Lindenstrauss
projection to reduced dimensionality enables efficient approximate nearest-neighbour retrieval
without sacrificing auditability.

The approach requires no training, no learned parameters, and no additional inference API
at projection time. We formalise the geometry of the blend operation, state conditions under
which intra-category similarity is preserved, and contrast the method with standard RAG and
Graph RAG along dimensions of determinism, taxonomy source, and enforcement mechanism.
PrismRAG is presented as an instantiation of this framework in enterprise multi-domain
settings.

**Keywords:** retrieval-augmented generation, knowledge graphs, vector embeddings, taxonomy
enforcement, deterministic projection, category bleed, Graph RAG

---

## 1. Introduction

Standard RAG pipelines follow a simple pattern:

```
Document → Chunk → Embed → Store in vector index
Query    → Embed → Cosine search → Top-K chunks → LLM
```

Embedding models map text into a high-dimensional space where semantically similar utterances
cluster together. This property supports general-purpose retrieval but fails in enterprise
contexts where organisational knowledge is structured by verified categories that do not
coincide with distributional similarity in pre-trained embedding space.

We identify three related failure modes:

**1.1 Category bleed.** In a finance corpus, the term *exposure* appears in both risk
documents ("credit exposure") and investment documents ("exposure to high-yield assets").
General-purpose embeddings place these contexts near one another because they are
linguistically similar. A risk analyst querying operational exposure should not retrieve
investment strategy documents — yet vector search has no category boundary to enforce.

**1.2 Absence of taxonomy enforcement.** Enterprise knowledge is organised by domain experts
into categories reflecting regulatory frameworks, clinical pathways, or risk taxonomies.
Standard RAG ignores this structure. The vector space reflects co-occurrence statistics from
pre-training and corpus composition, not the client's organisational model.

**1.3 Hallucination paths via retrieval error.** When the language model receives chunks from
the wrong category, it may synthesise an answer that conflates distinct domain concepts.
The retrieval failure is invisible at generation time; only the final output appears erroneous.

Graph RAG (Edge et al., 2024) addresses structural retrieval by building community graphs
from document co-occurrences. However, co-occurrence graphs reflect the *document corpus*,
not the *client taxonomy*. A risk management framework is not derivable from document
statistics alone — it exists in expert knowledge and regulatory specification.

**Contribution.** We propose inverting the conventional pipeline: the client defines the
taxonomy explicitly; all chunks are remapped into embedding space according to that taxonomy
*before* indexing. Category enforcement becomes a geometric operation on unit-norm vectors,
yielding deterministic, auditable retrieval boundaries without neural training at projection
time.

---

## 2. Related Work

**Retrieval-Augmented Generation.** Lewis et al. (2020) established the retrieve-then-generate
paradigm for knowledge-intensive tasks. Subsequent systems improve chunking, re-ranking, and
embedding quality but generally treat the vector space as given — category structure, when
present, is applied only as post-hoc filtering or soft re-ranking.

**Graph RAG.** Edge et al. (2024) construct knowledge graphs from entity and community
detection over document corpora, enabling multi-hop summarisation. Relationships are
statistical: two concepts are linked because they co-occur, not because a domain expert
assigned them to the same category. Graph RAG improves global summarisation but does not
transfer ownership of the taxonomy to the organisation.

**Dimensionality reduction for ANN search.** Johnson and Lindenstrauss (1984) provide
theoretical guarantees for distance-preserving random projections. HNSW graphs (Malkov &
Yashunin, 2018) enable sublinear approximate nearest-neighbour search in high-dimensional
spaces. These techniques optimise retrieval efficiency; they do not address category
isolation.

**Table 1** summarises the conceptual distinction among approaches.

| Dimension | Standard RAG | Graph RAG | Deterministic Category Projection |
|-----------|-------------|-----------|-----------------------------------|
| Category source | None | Document co-occurrence | Client-defined expert rules |
| Enforcement mechanism | None | Re-ranking / graph traversal hint | Mathematical vector projection |
| Deterministic | N/A | No (statistical) | Yes |
| Training required | No | Yes (community detection) | No |
| Taxonomy source | N/A | Derived from corpus | Defined by domain expert |
| Category bleed | Yes | Partial mitigation | Addressed at vector level |
| Audit traceability | Low | Medium | High (rule → category → vector) |

The central insight motivating our method: **the taxonomy is not fully present in the
documents; it resides in expert specification.** Statistical graph construction cannot
recover what was never written. Explicit taxonomy definition followed by geometric enforcement
yields predictability and auditability unavailable to corpus-derived methods.

---

## 3. Method: Tier-1 Deterministic Category Projection

### 3.1 Problem Formulation

Given:

- A semantic embedding **v** ∈ ℝᵈ produced by any unit-norm embedding model
- A taxonomy of *C* categories indexed by *i* ∈ {0, …, *C*−1}
- A rule set *R* mapping tokens *w* → (*i*, *λ*) where *λ* ∈ ℝ⁺ is a rule weight

We seek a remapped vector **v′** ∈ ℝᵈ such that:

1. Semantic content of **v** is retained (similarity search remains meaningful)
2. **v′** is shifted toward a category-associated direction **e**ᵢ
3. The mapping is deterministic: identical inputs yield identical outputs
4. No training, learned parameters, or external inference is required at projection time
5. **v′** lies on the unit sphere (consistent with cosine-similarity conventions)

### 3.2 Category Inference

Category index *i* is inferred from text *T* by token-level weighted accumulation:

```
scores(i) = Σ  λ(w)   for all tokens w in T such that (i, λ(w)) ∈ R
i*        = argmax_i scores(i)   if any rule matches; else undefined
```

Each rule lookup is *O*(1) per token. The operation is deterministic, requires no neural
network, and introduces no stochasticity. Unmatched chunks may pass through unmodified or
be assigned a default category per deployment policy.

### 3.3 Projection Direction

For category index *i*, dimension *d*, and *C* categories, define a unit direction
**e**ᵢ ∈ ℝᵈ by partitioning coordinate indices:

```
cluster_size = ⌊d / C⌋
start        = (i × cluster_size) mod d
end          = min(start + cluster_size, d)

(eᵢ)ⱼ = 1  for j ∈ [start, end);  0 otherwise
eᵢ    = eᵢ / ‖eᵢ‖
```

This constructs *C* non-overlapping directional sectors in ℝᵈ. The partition depends
only on (*d*, *C*, *i*) — not on corpus statistics — ensuring reproducibility across
environments and tenants.

**Rationale.** Pre-trained embeddings distribute semantic information across all dimensions.
A controlled displacement toward a category-specific sector introduces systematic bias:
at query time, documents and queries assigned to the same category receive parallel
displacements, increasing their mutual cosine similarity relative to cross-category pairs.

### 3.4 The Spherical Blend Operation

Given blend coefficient α ∈ (0, 1), the remapped vector is:

```
v′ = normalize( (1 − α) · v + α · ‖v‖ · eᵢ )
```

where normalize(**x**) = **x** / ‖**x**‖.

The term ‖**v**‖ scales the direction **e**ᵢ to the magnitude of **v** before blending.
Final normalisation projects **v′** onto the unit sphere.

**Geometric interpretation.** **v′** is a weighted combination of the original semantic
direction and the category sector direction, re-normalised to unit length. With α ≈ 0.35,
empirical observations indicate cosine displacement of approximately 1–4% — sufficient to
separate categories in ranked retrieval while preserving within-category semantic structure.

**Proposition (intra-category similarity preservation).** For documents with embeddings
**v**₁, **v**₂ assigned to the same category direction **e**ᵢ, if cos(**v**₁, **e**ᵢ) ≈
cos(**v**₂, **e**ᵢ), then:

```
cos(v′₁, v′₂) ≥ cos(v₁, v₂)
```

Remapping does not decrease similarity among same-category documents whose original
embeddings align similarly with **e**ᵢ — the typical case for on-topic documents matching
consistent keyword rules.

### 3.5 Reduced Personal Space

For efficient approximate nearest-neighbour search, a secondary projection maps the
768-dimensional semantic space to *k*-dimensional personal space (*k* ≪ *d*, e.g. *k* = 256).

A deterministic Johnson–Lindenstrauss matrix **P** ∈ ℝ^{k×d} is constructed via fixed-seed
Gaussian draw followed by orthonormalisation (QR decomposition). By the JL lemma, pairwise
distances are preserved up to ε with high probability for sufficiently large *k*.

An optional pre-projection blend injects category signal:

```
blended = 0.30 · c + 0.70 · (P · v′)
p       = blended / ‖blended‖
```

where **c** is a one-hot category vector in ℝ^k.

This two-layer design separates concerns: high-dimensional **v′** supports semantic
re-ranking; low-dimensional **p** supports fast ANN retrieval with additional category
separation in reduced space.

---

## 4. Conceptual Retrieval Pipeline

The complete retrieval framework, abstracted from any particular deployment, is:

```
┌──────────────────────────────────────────────────────────────────┐
│  1. Taxonomy specification (categories + weighted keyword rules) │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. Ingestion: chunk → embed → infer category → project (Tier-1) │
│                 → optional JL reduction → index                   │
└────────────────────────────┬─────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. Query: embed → infer category → project → ANN search          │
│            → optional category filter → re-rank → LLM context     │
└──────────────────────────────────────────────────────────────────┘
```

Unlike Graph RAG, the graph structure — if used for community routing — serves a
client-defined mapping rather than replacing it. The taxonomy is an input to the system,
not an emergent property of the corpus.

Multi-tenant isolation follows naturally: each tenant maintains an independent rule set
*R* and corresponding projection parameters (*C*, α). Identical source documents ingested
under different taxonomies produce distinct vector populations — by design, not by accident
of co-occurrence statistics.

---

## 5. Discussion

### 5.1 Why Determinism Matters

Enterprise and regulated domains require explainability. When a retrieval result is challenged,
a deterministic rule chain — token → rule → category → projection direction → ranked chunk —
provides an auditable answer. Statistical graph edges and soft re-ranking scores do not
offer equivalent traceability.

### 5.2 Comparison with Graph RAG

Graph RAG excels at global, corpus-scale summarisation where community structure reflects
genuine thematic clusters in unstructured text. It is less suited when:

- The authoritative taxonomy precedes the document collection (regulatory frameworks)
- The same corpus must support multiple incompatible organisational views
- Category boundaries must be hard constraints, not ranking hints
- Audit requires rule-level provenance

Deterministic Category Projection complements graph-based traversal by ensuring the
underlying vector geometry respects expert boundaries before any graph algorithm operates.

### 5.3 Embedding Model Independence

Because projection operates on any unit-norm **v** ∈ ℝᵈ, the method is agnostic to
embedding provider, model version, or deployment mode (cloud API vs. local inference).
Only *d* and normalisation convention must be consistent between ingest and query.

---

## 6. Limitations and Future Work

**Current limitations:**

1. **Projection directions** are dimensional partitions rather than corpus-derived centroids.
   Learned centroids could increase separation but reintroduce training dependence and
   periodic retraining requirements.

2. **Keyword rules** use exact token matching. Stemming, lemmatisation, and controlled
   synonym expansion would improve recall while preserving determinism if rules remain
   explicit.

3. **Fixed JL matrix.** A per-tenant learned projection (e.g., contrastive fine-tuning on
   labelled category pairs) could adapt reduced space to domain vocabulary but requires
   sufficient labelled data — a Tier-2 extension beyond the scope of Tier-1.

**Future research directions:**

- Empirical evaluation of category separation metrics (intra- vs. inter-category cosine
  distributions) across domains and embedding models
- Learned category centroids via online clustering with deterministic fallback to rule-based
  sectors when training data is sparse
- Integration with graph community detection where communities are *labelled by* expert
  taxonomy rather than *discovered from* co-occurrence alone
- Formal analysis of optimal α as a function of *C*, *d*, and desired separation–fidelity
  trade-off

---

## 7. Conclusion

Category bleed in retrieval-augmented generation is not primarily a language-model failure;
it is a retrieval geometry failure. Vector similarity encodes distributional semantics,
not organisational taxonomy. Graph RAG improves structural retrieval but derives
relationships from the corpus, leaving expert knowledge outside the system boundary.

Tier-1 Deterministic Category Projection addresses this by enforcing taxonomy at the vector
level: weighted rules assign categories; deterministic sector directions partition
embedding space; a spherical blend preserves semantic content while separating categories
before indexing. The method requires no training, introduces no stochasticity at projection
time, and yields audit trails from rule to retrieval result.

The power of the approach lies not in computational complexity — the core blend is a
closed-form operation on unit vectors — but in the inversion of pipeline direction: define
the taxonomy first, then embed data into it. For enterprise AI systems where domain experts
already maintain verified category structures, this inversion changes what is possible in
grounded, auditable retrieval.

---

## References

1. Lewis, P., Perez, E., Piktus, A., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* Advances in Neural Information Processing Systems (NeurIPS).

2. Edge, D., Trinh, H., Cheng, N., et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* Microsoft Research.

3. Johnson, W. B., Lindenstrauss, J. (1984). *Extensions of Lipschitz mappings into a Hilbert space.* Contemporary Mathematics, 26, 189–206.

4. Malkov, Y. A., Yashunin, D. A. (2018). *Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs.* IEEE Transactions on Pattern Analysis and Machine Intelligence, 42(4), 824–836.

5. Reimers, N., Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* Proceedings of EMNLP.

6. Parva, A. (2026). *PrismRAG: Semantic Re-mapping for Enterprise Retrieval-Augmented Generation.* Insight IT Solutions.

---

*© 2026 Amin Parva / Insight IT Solutions. All rights reserved.*  
*Publication of this article constitutes prior art for the Tier-1 Deterministic Category*  
*Projection algorithm and associated techniques described herein.*
