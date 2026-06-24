# PrismRAG Deliberation — Multi-Domain Expert Synthesis

> **Note (2026):** Deliberation was a **hosted SaaS feature** (Azure retired). Code remains in `prismrag/` for self-host. Primary product: pip library — [INFO.md](../INFO.md).

## What it does

Deliberation answers complex questions that no single domain can fully address by running a structured three-phase pipeline:

```
User Question
     │
     ▼
Phase 1 — HORIZONTAL DISCOVERY (breadth)
  LLM + KB community search → top 7 relevant domains ranked by relevance
  e.g. "What are the risks of this merger?"
    → [Finance & Valuation, Antitrust Law, Organizational Psychology,
       Technology Integration, Market Strategy, HR & Culture, Regulatory Compliance]
     │
     ▼
Phase 2 — VERTICAL QUERIES (depth per domain, all in parallel)
  Each domain gets a targeted deep query as a domain expert
  Finance:    "From a DCF and synergy valuation perspective..."
  Antitrust:  "Under EU Regulation 139/2004 and US Hart-Scott-Rodino..."
  Psychology: "Merger integration research shows cognitive load and identity threat..."
  [4 more domains...]
     │
     ▼
Phase 3 — DELIBERATION SYNTHESIS
  Master Deliberator compares all findings:
  → AGREEMENTS: Finance + Strategy agree on synergy value
  → CONFLICTS: Finance sees upside; Antitrust sees 60% block probability
  → UNIQUE INSIGHTS: Psychology flagged culture clash not in financials
  → FINAL ANSWER: synthesized response weighted by confidence scores
```

---

## Why this is better than standard RAG

| Standard RAG | Deliberation |
|---|---|
| Single retrieval pass | 3-phase structured pipeline |
| One knowledge perspective | 7 domain specialists |
| Returns chunks | Returns reasoned synthesis |
| No conflict detection | Surfaces agreements AND conflicts |
| Static answer | Follow-up questions on existing session |

---

## Difference from original Delllusion

The original Delllusion used free-form expert panels where users manually picked Physics, Chemistry, Philosophy etc. and ran unstructured conversations.

The new Deliberation service:

| Original Delllusion | PrismRAG Deliberation |
|---|---|
| User picks experts | System discovers relevant domains automatically |
| Free-form conversation | Structured horizontal → vertical → synthesis pipeline |
| Flask + LangGraph | FastAPI + parallel async execution |
| Session-based UI | API-first, MCP-native |
| Per-session billing | Plan-based with monthly quotas |
| Separate product | Integrated into PrismRAG suite |
| No KB integration | Plugs into PrismRAG knowledge graphs |

---

## API reference

### POST /api/deliberation/sessions

Start a deliberation. Returns full result (sync) or session_id to poll (async).

**Request**
```json
{
  "question":     "What are the risks and opportunities of acquiring a competitor in Q4?",
  "title":        "Competitor acquisition analysis",
  "tenant_id":    "uuid",
  "mapping_id":   "uuid",
  "domain_count": 7,
  "async_mode":   false
}
```

`tenant_id` — optional. If set, Phase 2 vertical queries also search your PrismRAG knowledge graph for KB-grounded answers.  
`domain_count` — 3 to 10. Default 7. More domains = richer synthesis, slower response.  
`async_mode` — `false` (default): blocks until done (~20–60s). `true`: returns immediately, poll for results.

**Response (sync, status=done)**
```json
{
  "session_id": "uuid",
  "status":     "done",
  "question":   "What are the risks...",
  "domains": [
    {"rank": 1, "name": "Finance & Valuation", "relevance_score": 0.95, "source": "llm"},
    {"rank": 2, "name": "Antitrust Law",        "relevance_score": 0.88, "source": "hybrid"},
    ...
  ],
  "verticals": [
    {
      "domain":     "Finance & Valuation",
      "findings":   "DCF analysis suggests 3.2× revenue multiple...",
      "confidence": 0.88,
      "kb_hits":    [...],
      "latency_ms": 1240
    },
    ...
  ],
  "synthesis": {
    "synthesis_type":  "comparison",
    "agreements":      "Finance and Strategy both estimate 12–18% synergy uplift...",
    "conflicts":       "Finance models 70% deal probability; Antitrust assigns 40%...",
    "unique_insights": "HR research flagged cultural integration risk not in financial models",
    "final_answer":    "The acquisition presents a strong strategic fit but carries...",
    "confidence":      0.81,
    "contributing_domains": [
      {"name": "Finance & Valuation", "weight": 0.92, "agreement_score": 0.78},
      ...
    ]
  },
  "followups": []
}
```

**Response (async)**
```json
{
  "session_id": "uuid",
  "status":     "discovering",
  "async":      true,
  "poll_url":   "/api/deliberation/sessions/uuid"
}
```

Status progression: `created` → `discovering` → `querying` → `synthesizing` → `done` | `failed`

---

### GET /api/deliberation/sessions/{session_id}

Poll for results or retrieve a past session. Returns the same shape as the sync POST response.

---

### GET /api/deliberation/sessions/{session_id}/domains

Return only the horizontally-discovered domains (available once status=`querying`).

---

### POST /api/deliberation/sessions/{session_id}/followup

Ask a follow-up question against a completed session. The Master Deliberator answers using the existing panel findings without re-running the full pipeline.

**Request**: `{ "question": "Which risk should we address first?" }`  
**Response**: `{ "question": "...", "answer": "Based on the panel findings..." }`

Follow-ups are included in all plans — they don't consume a deliberation credit.

---

### GET /api/deliberation/sessions

List the current user's deliberation sessions (most recent 20).

---

## MCP tools

When connected via MCP, AI agents get three deliberation tools:

### `deliberate`
```
Input: question (required), domain_count (3-10, default 7), tenant_id (optional)
Output: Full synthesis — agreements, conflicts, unique insights, final answer
```

**Example agent prompt:**
> "Use the deliberate tool to analyse whether we should enter the Southeast Asian market."

The agent will automatically call `deliberate` with the question, discover 7 domains (Market Entry Strategy, Regulatory Environment, Cultural Factors, Supply Chain, Competitive Landscape, Financial Modeling, Political Risk), query each as a specialist, and return a synthesized recommendation.

### `get_deliberation_session`
```
Input: session_id
Output: Current session state and results
```

### `deliberation_followup`
```
Input: session_id, question
Output: Follow-up answer from the Master Deliberator
```

---

## Pricing

| Plan | Monthly deliberations | Price | Per-domain queries |
|---|---|---|---|
| **Free** | 5 | $0 | 7 per deliberation |
| **Starter** | 50 | $29/mo | 7 per deliberation |
| **Professional** | 500 | $99/mo | Up to 10 per deliberation |
| **Enterprise** | Unlimited | Custom | Unlimited |

**Overage**: $0.50 per deliberation on Starter/Professional.

**What counts as one deliberation**: one full pipeline run (1 horizontal + up to 10 vertical + 1 synthesis). Follow-up questions are free.

---

## Performance

Typical latency with 7 domains, no KB:
- Phase 1 (horizontal): 2–5 seconds (1 Gemini call)
- Phase 2 (vertical, parallel): 8–20 seconds (7 parallel Gemini calls)
- Phase 3 (synthesis): 5–12 seconds (1 Gemini call)
- **Total: 15–37 seconds**

With KB search enabled (tenant_id set): add ~200ms per domain for HNSW search.

For async_mode=true, the API returns in <100ms and all three phases run in the background.

---

## Cost model (your COGS)

**Gemini 2.0 Flash pricing (as of 2025):**
- Input tokens:  $0.075 per 1M tokens  ($0.000075 / 1K)
- Output tokens: $0.300 per 1M tokens  ($0.000300 / 1K)

**Per 7-domain deliberation:**

| Phase | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|
| Phase 1 — Horizontal discovery | 1 | ~600 | ~400 | $0.000165 |
| Phase 2 — Vertical expert queries | 7 (parallel) | ~8,400 | ~4,900 | $0.002100 |
| Phase 3 — Synthesis | 1 | ~6,000 | ~1,200 | $0.000810 |
| **Total** | **9 calls** | **~15,000** | **~6,500** | **~$0.003** |

- Follow-up question (optional): ~$0.0003 per call (not counted as a deliberation)
- With 10 domains: ~$0.005 per deliberation (+2 extra vertical calls)

**Margin analysis:**

| Plan | Price / deliberation | COGS | Gross margin |
|---|---|---|---|
| Starter overage | $0.50 | $0.003 | ~167× |
| Starter plan ($29 / 50) | $0.58 | $0.003 | ~193× |
| Professional plan ($99 / 500) | $0.20 | $0.003–0.005 | ~50–67× |
| Enterprise (custom) | negotiated | $0.003–0.005 | varies |

**Monthly COGS at scale:**

| Monthly deliberations | COGS | Revenue (Professional) | Gross profit |
|---|---|---|---|
| 50 (Starter) | $0.15 | $29 | $28.85 |
| 500 (Professional) | $1.50 | $99 | $97.50 |
| 5,000 (Enterprise est.) | $15 | ~$500+ | $485+ |
