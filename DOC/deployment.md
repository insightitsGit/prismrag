# PrismRAG — Deployment Guide

## Prerequisites

- Azure CLI (`az`) logged in
- Docker Desktop running
- Azure subscription with Contributor role on the resource group

## Phase 1 — Local / Neon (Day 1, ~$12/mo)

### 1. Neon database

1. Sign up at [console.neon.tech](https://console.neon.tech)
2. Create project `prismrag`, database `prismrag`
3. Enable pgvector: **Extensions → Add → vector**
4. Copy the connection string

### 2. Run the schema

```bash
psql "postgresql://user:pass@ep-xyz.neon.tech/prismrag?sslmode=require" \
  -f prismrag/schema.sql \
  -f prismrag/auth_schema.sql \
  -f prismrag/audit_schema.sql
```

### 3. Environment

```bash
cp .env.example .env
# Edit .env with your actual values
```

Required for local dev:
```
PRISMRAG_DB_DSN=postgresql://...neon.tech/prismrag?sslmode=require
JWT_SECRET=<64 random chars>
GEMINI_API_KEY=AIza...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 4. Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
# Open http://localhost:8001
```

### 5. Stripe webhook (local)

```bash
stripe listen --forward-to localhost:8001/api/billing/webhook
```

---

## Phase 1 — Azure Container Apps (still using Neon)

### 1. Create resource group and ACR

```bash
az group create -n prismrag-rg -l eastus2
az acr create -n prismrag -g prismrag-rg --sku Basic --admin-enabled true
az acr login -n prismrag
```

### 2. Deploy

```bash
# Copy params template
cp infra/params.example.json infra/params.json
# Edit infra/params.json:
#   externalDb = true
#   externalDbDsn = your Neon DSN
#   deployRedis = false

./infra/deploy.sh v0.1.0
```

This builds and pushes both Docker images then deploys Container Apps via Bicep.

---

## Phase 2 — Azure Postgres Burstable (~$80/mo)

When Neon free tier is full (>0.5 GB) or you need consistent latency:

```bash
# In infra/params.json:
#   externalDb = false
#   postgresSku = Standard_B2s

./infra/deploy.sh v0.2.0

# Enable pgvector on the new Azure Postgres server
az postgres flexible-server parameter set \
  -g prismrag-rg -s prismrag-pg \
  -n azure.extensions --value vector

# Migrate data from Neon (takes seconds for small DBs)
pg_dump "postgresql://neon-dsn..." | psql "postgresql://azure-dsn..."
```

---

## Phase 3 — Full production (~$250+/mo)

```bash
# In infra/params.json:
#   postgresSku = Standard_D4s_v3   (zone-redundant HA)
#   deployRedis = true

./infra/deploy.sh v1.0.0
```

---

## Cleanup cron job

Set up nightly cleanup as a Container Apps scheduled job:

```bash
az containerapp job create \
  --name prismrag-cleanup \
  --resource-group prismrag-rg \
  --environment prismrag-env \
  --trigger-type Schedule \
  --cron-expression "0 2 * * *" \
  --image prismrag.azurecr.io/prismrag-api:latest \
  --command "python" "-m" "prismrag.worker.cleanup" \
  --cpu 0.25 --memory 0.5Gi
```

## MCP server (optional add-on)

```bash
# Run alongside the API (separate process or container)
python -m prismrag.mcp.server

# Or add to docker-compose for local dev:
# See DOC/mcp.md
```
