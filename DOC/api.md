# PrismRAG — API Reference

Base URL: `https://api.prismrag.io`  
Interactive docs: `https://api.prismrag.io/docs` (Swagger UI)

## Authentication

All endpoints (except `/api/auth/register` and `/api/auth/login`) require:

```
Authorization: Bearer <token>
```

Token can be either:
- **JWT** — obtained from `/api/auth/login`, expires after 72 hours
- **API key** — prefixed `prk_`, never expires, revocable via dashboard

---

## Auth endpoints

### POST /api/auth/register

Create a new account. Returns a JWT immediately — no email verification required for the free tier.

**Request**
```json
{
  "email":     "jane@acme.com",
  "password":  "min8chars",
  "full_name": "Jane Smith",
  "company":   "Acme Corp"
}
```

**Response 200**
```json
{
  "token":     "eyJ...",
  "user_id":   "uuid",
  "email":     "jane@acme.com",
  "plan":      "free",
  "full_name": "Jane Smith"
}
```

**Errors**: `409` email already registered.

---

### POST /api/auth/login

**Request**
```json
{ "email": "jane@acme.com", "password": "yourpassword" }
```

**Response 200** — same shape as `/register`.

---

### GET /api/auth/me

Returns current user profile. Refreshes plan status from DB.

**Response 200**
```json
{
  "id":                 "uuid",
  "email":              "jane@acme.com",
  "full_name":          "Jane Smith",
  "plan":               "professional",
  "subscriptionStatus": "active"
}
```

---

### POST /api/auth/api-keys

Generate a new API key. The `raw_key` is returned **once only** — store it immediately.

**Response 200**
```json
{
  "raw_key":    "prk_AbCdEf...",
  "key_prefix": "prk_AbCdEf12",
  "label":      "Default"
}
```

### GET /api/auth/api-keys

List all active API keys (prefix and metadata only — raw key never returned again).

### DELETE /api/auth/api-keys/{key_id}

Revoke an API key. Immediately invalidates it.

---

### GET /api/auth/usage

Current month usage and quota.

**Response 200**
```json
{
  "plan":            "starter",
  "chunks_used":     14200,
  "chunks_limit":    200000,
  "searches_used":   3100,
  "searches_limit":  20000,
  "tenants_count":   2
}
```

---

## Workspace (tenant) endpoints

### POST /api/prismrag/tenants

Create a new workspace (isolated vector space and knowledge graph).

**Request**
```json
{ "name": "Finance Q4 Corpus", "tier": "tier1" }
```

**Response 200**
```json
{
  "tenant_id":  "uuid",
  "name":       "Finance Q4 Corpus",
  "tier":       "tier1",
  "created_at": "2026-06-17T14:00:00Z"
}
```

**Errors**: `403` max workspaces for plan reached.

---

## Ingest endpoints

### POST /api/prismrag/jobs

Submit an ingest job via JSON body (for SQL, API, or chunk source types).

**Request**
```json
{
  "tenant_id":   "uuid",
  "source_type": "file",
  "strategy":    "rules",
  "mapping": {
    "categories": [
      { "slug": "risk",    "label": "Risk Factors" },
      { "slug": "revenue", "label": "Revenue Metrics" }
    ],
    "rules": [
      { "word": "exposure",  "category_slug": "risk" },
      { "word": "liability", "category_slug": "risk" },
      { "word": "revenue",   "category_slug": "revenue" },
      { "word": "EBITDA",    "category_slug": "revenue" }
    ]
  }
}
```

`strategy`: `"rules"` (Tier 1, always available) or `"mlp"` (Tier 2, Professional+).

**Response 200**
```json
{
  "job_id":     "uuid",
  "tenant_id":  "uuid",
  "status":     "queued",
  "status_url": "/api/prismrag/jobs/uuid",
  "sync":       false
}
```

---

### POST /api/prismrag/jobs/upload

Submit a file-based job (multipart/form-data). File must have `word` and `category` columns (CSV/Excel).

```bash
curl -X POST https://api.prismrag.io/api/prismrag/jobs/upload \
  -H "Authorization: Bearer YOUR_KEY" \
  -F "file=@mapping.csv" \
  -F "tenant_id=YOUR_TENANT_UUID" \
  -F "strategy=rules"
```

Files < 1 MB run synchronously and return `status: completed`. Larger files return `status: queued`.

---

### GET /api/prismrag/jobs/{job_id}

Poll job progress.

**Response 200**
```json
{
  "job_id":          "uuid",
  "tenant_id":       "uuid",
  "status":          "running",
  "records_total":   50000,
  "records_written": 12800,
  "progress_pct":    25,
  "error_message":   null,
  "started_at":      "2026-06-17T14:00:00Z",
  "finished_at":     null
}
```

`status` values: `queued` | `running` | `done` | `failed`

---

## Large file upload (> 1 MB)

For files > 1 MB, use the two-step SAS upload to avoid routing large payloads through the API server.

### Step 1 — POST /api/prismrag/upload/presign

```json
{
  "tenant_id":       "uuid",
  "original_name":   "corpus.csv",
  "file_size_bytes": 52428800
}
```

**Response 200**
```json
{
  "upload_id":      "uuid",
  "upload_url":     "https://prismrag.blob.core.windows.net/...?sas=...",
  "blob_name":      "tenant-id/uuid_corpus.csv",
  "expires_at":     "2026-06-17T18:00:00Z",
  "max_size_bytes": 500000000,
  "instructions":   "PUT your file to upload_url with Content-Type: application/octet-stream..."
}
```

### Step 2 — PUT {upload_url}

Client PUTs the file directly to Azure Blob Storage. The API server never touches the bytes.

```bash
curl -X PUT "{upload_url}" \
  -H "Content-Type: application/octet-stream" \
  -H "x-ms-blob-type: BlockBlob" \
  --data-binary @corpus.csv
```

### Step 3 — POST /api/prismrag/upload/confirm

```json
{
  "upload_id": "uuid",
  "tenant_id": "uuid",
  "strategy":  "rules"
}
```

**Response 200**
```json
{
  "job_id":     "uuid",
  "status":     "queued",
  "status_url": "/api/prismrag/jobs/uuid"
}
```

---

## Search endpoint

### POST /api/prismrag/search

Query your knowledge graph. Uses Graph RAG retrieval (community → BFS → re-rank) when communities are built, HNSW direct search otherwise.

**Request**
```json
{
  "tenant_id":      "uuid",
  "query":          "quarterly risk exposure in emerging markets",
  "mapping_id":     "uuid",
  "top_k":          10,
  "category_filter": "risk"
}
```

`mapping_id`: optional — defaults to the active mapping for the tenant.  
`category_filter`: optional — restricts results to one category slug.

**Response 200**
```json
{
  "query":          "quarterly risk exposure in emerging markets",
  "hits": [
    {
      "word":           "exposure",
      "text":           "Quarterly risk exposure in emerging market equities",
      "score":          0.921,
      "category":       "risk",
      "community_label": "Market Risk Factors",
      "mapping_id":     "uuid"
    }
  ],
  "retrieval_mode": "graph_rag",
  "latency_ms":     42
}
```

**Rate limits**: see plan table below.  
**Errors**: `402` quota exceeded (with overage pricing in body), `429` rate limit.

---

## Bridge vector endpoint (Professional+)

### POST /api/prismrag/bridge

Create a synthetic connector vector between two communities. Lets the LLM traverse from one domain cluster to another.

**Request**
```json
{
  "tenant_id":   "uuid",
  "mapping_id":  "uuid",
  "community_a": 3,
  "community_b": 7,
  "label":       "Risk-Revenue Intersection"
}
```

**Response 200**
```json
{
  "bridge_id":   "uuid",
  "label":       "Bridge: Risk-Revenue Intersection",
  "community_a": 3,
  "community_b": 7,
  "edges_added": 12
}
```

### GET /api/prismrag/bridge/{tenant_id}/{mapping_id}

List all bridge vectors for a tenant/mapping.

---

## Billing endpoints

### GET /api/billing/plans

Returns plan details and the Stripe publishable key for frontend checkout.

**Response 200**
```json
{
  "publishable_key": "pk_live_...",
  "plans": [
    {
      "id":            "free",
      "name":          "Free",
      "price_display": "$0",
      "description":   "Explore PrismRAG — no credit card required",
      "features":      ["5,000 chunks/month", "500 searches/month", "1 workspace"]
    },
    {
      "id":            "starter",
      "name":          "Starter",
      "price_display": "$49",
      "description":   "Small teams and pilots",
      "features":      ["200,000 chunks/month", "20,000 searches/month", "Graph RAG", "3 workspaces"]
    }
  ]
}
```

### POST /api/billing/checkout

Initiate Stripe Checkout for a plan upgrade.

**Request**: `{ "plan": "professional" }`  
**Response**: `{ "redirect": "https://checkout.stripe.com/..." }`

### POST /api/billing/portal

Open Stripe Billing Portal (cancel, update card, view invoices).

**Response**: `{ "redirect": "https://billing.stripe.com/..." }`

### POST /api/billing/webhook

Stripe webhook endpoint. Verify signature with `STRIPE_WEBHOOK_SECRET`. Handles: `customer.subscription.created/updated/deleted`, `invoice.payment_failed`.

---

## Plan limits

| | Free | Starter | Professional | Enterprise |
|---|---|---|---|---|
| Price | $0 | $49/mo | $199/mo | Custom |
| Chunks/month | 5,000 | 200,000 | 2,000,000 | Unlimited |
| Searches/month | 500 | 20,000 | 150,000 | Unlimited |
| Req/minute | 20 | 120 | 600 | Unlimited |
| Workspaces | 1 | 3 | 20 | Unlimited |
| Tier 2 MLP | ✗ | ✗ | ✓ | ✓ |
| Bridge vectors | ✗ | ✗ | ✓ | ✓ |
| Graph RAG | ✗ | ✓ | ✓ | ✓ |
| Log retention | 7 days | 30 days | 30 days | 90 days |
| Support | Community | Email | Priority | Dedicated |

## Overage pricing (Starter / Professional only)

| Event | Price |
|---|---|
| Ingest chunks | $0.80 / 1,000 |
| Searches | $1.50 / 1,000 |
| MLP training runs | $5.00 / run |
| Bridge vectors | $2.00 / bridge |

---

## Error codes

| HTTP | Code | Meaning |
|---|---|---|
| 400 | — | Validation error (see `detail`) |
| 401 | — | Missing or invalid token/API key |
| 402 | `quota_exceeded` | Monthly limit reached; detail includes overage price |
| 403 | — | Feature not in plan, or max workspaces reached |
| 404 | — | Resource not found |
| 409 | — | Conflict (e.g. email already registered) |
| 413 | — | File too large for plan |
| 422 | — | Invalid request body |
| 429 | — | Rate limit exceeded; `Retry-After: 60` header set |
| 500 | — | Internal error |
