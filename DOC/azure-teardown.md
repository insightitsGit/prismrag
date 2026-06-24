# Azure teardown — zero cost

PrismRAG SaaS ran in Azure resource group **`prismrag-rg`** (eastus2). Deleting this group removes all billable PrismRAG SaaS resources.

## What gets deleted (prismrag-rg only)

| Resource | Typical cost |
|----------|----------------|
| Container Apps (`prismrag-api`, `prismrag-worker`) | ~$75+/mo when running |
| Container Apps Environment (`prismrag-env`) | Included in ACA billing |
| Log Analytics (`prismrag-logs`) | ~$80+/mo at high ingest |
| Azure Container Registry (`prismragacr`) | ~$5/mo Basic |
| Service Bus (`prismrag-bus`) | ~$0.05/mo Basic |
| Managed identities | Free |

## What is NOT deleted

- **Shared Postgres** (`psql-insight-hospital-prod`) — external DB, not in `prismrag-rg`
- **DNS** (Route53 / insightits.com) — update or remove CNAME manually if needed
- **GitHub secrets** — remove obsolete Azure secrets when convenient

## Delete (one command)

```powershell
az login
az group delete --name prismrag-rg --yes --no-wait
```

Or use the script:

```powershell
.\infra\teardown-azure.ps1
```

Verify deletion:

```powershell
az group exists --name prismrag-rg
# false
```

## After teardown

- `https://prismrag.insightits.com` will stop working (expected).
- Use the pip library: `pip install prismrag-patch`
- CI no longer deploys to Azure (see `.github/workflows/ci.yml`).
