#!/usr/bin/env bash
# PrismRAG — Azure deployment script
# Usage: ./infra/deploy.sh [image-tag]
#
# Prerequisites:
#   az login                         — Azure CLI authenticated
#   docker login prismrag.azurecr.io — or use: az acr login -n prismrag
#   cp infra/params.example.json infra/params.json && edit params.json
#
# Phase flags in params.json:
#   Phase 1  externalDb=true,  deployRedis=false  → Neon free tier,  ~$12-31/mo
#   Phase 2  externalDb=false, deployRedis=false  → Azure Postgres B2s, ~$80-130/mo
#   Phase 3  externalDb=false, deployRedis=true   → Postgres D4s + Redis, ~$250+/mo

set -euo pipefail

TAG=${1:-latest}
RG=prismrag-rg
LOCATION=eastus2
ACR=prismragacr
ACR_SERVER=${ACR}.azurecr.io
SB_NS=prismrag-bus        # Service Bus namespace
KV_NAME=prismrag-kv       # Key Vault name (must be globally unique — append suffix if needed)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}==>${NC} $*"; }
warn()    { echo -e "${YELLOW}WARN${NC} $*"; }
die()     { echo -e "${RED}ERROR${NC} $*"; exit 1; }

# ── Pre-flight checks ──────────────────────────────────────────────────────────
info "Pre-flight checks"
command -v az     >/dev/null 2>&1 || die "Azure CLI not installed. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
command -v docker >/dev/null 2>&1 || die "Docker not installed."
az account show   >/dev/null 2>&1 || die "Not logged in to Azure. Run: az login"

[[ -f infra/params.json ]] || die "infra/params.json not found. Copy from infra/params.example.json and fill in your values."

SUBSCRIPTION=$(az account show --query id -o tsv)
info "Subscription: $SUBSCRIPTION"

# ── Resource group ─────────────────────────────────────────────────────────────
info "Creating resource group $RG in $LOCATION (idempotent)"
az group create --name $RG --location $LOCATION --output none

# ── Azure Container Registry ───────────────────────────────────────────────────
info "Ensuring ACR: $ACR"
if ! az acr show --name $ACR --resource-group $RG &>/dev/null; then
  az acr create --name $ACR --resource-group $RG --sku Basic --admin-enabled true --output none
  info "ACR created: $ACR_SERVER"
else
  info "ACR already exists: $ACR_SERVER"
fi

info "Logging in to ACR"
az acr login --name $ACR

# ── Service Bus (for large-file async worker) ──────────────────────────────────
info "Ensuring Service Bus namespace: $SB_NS"
if ! az servicebus namespace show --name $SB_NS --resource-group $RG &>/dev/null; then
  az servicebus namespace create --name $SB_NS --resource-group $RG \
    --location $LOCATION --sku Basic --output none
  az servicebus queue create --name prismrag-jobs --namespace-name $SB_NS \
    --resource-group $RG --output none
  info "Service Bus created with queue: prismrag-jobs"
else
  info "Service Bus already exists: $SB_NS"
fi

SB_CONN=$(az servicebus namespace authorization-rule keys list \
  --resource-group $RG --namespace-name $SB_NS --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv)

# ── Key Vault ─────────────────────────────────────────────────────────────────
info "Ensuring Key Vault: $KV_NAME"
if ! az keyvault show --name $KV_NAME --resource-group $RG &>/dev/null; then
  az keyvault create --name $KV_NAME --resource-group $RG \
    --location $LOCATION --sku standard --output none
  info "Key Vault created: $KV_NAME"
else
  info "Key Vault already exists: $KV_NAME"
fi

# ── Build and push Docker images ───────────────────────────────────────────────
info "Building API image: $ACR_SERVER/prismrag-api:$TAG"
docker build -t $ACR_SERVER/prismrag-api:$TAG -f Dockerfile . --platform linux/amd64

info "Building Worker image: $ACR_SERVER/prismrag-worker:$TAG"
docker build -t $ACR_SERVER/prismrag-worker:$TAG -f Dockerfile.worker . --platform linux/amd64

info "Pushing images to ACR"
docker push $ACR_SERVER/prismrag-api:$TAG
docker push $ACR_SERVER/prismrag-worker:$TAG

# ── Inject Service Bus connection string into params ──────────────────────────
TMP_PARAMS=$(mktemp /tmp/params.XXXXXX.json)
python3 -c "
import json, sys
with open('infra/params.json') as f:
    p = json.load(f)
p['parameters']['serviceBusConnectionString'] = {'value': sys.argv[1]}
p['parameters']['imageTag'] = {'value': sys.argv[2]}
p['parameters']['acrLoginServer'] = {'value': sys.argv[3]}
with open(sys.argv[4], 'w') as f:
    json.dump(p, f)
" "$SB_CONN" "$TAG" "$ACR_SERVER" "$TMP_PARAMS"

# ── Deploy Container Apps ──────────────────────────────────────────────────────
info "Deploying Container Apps (this takes 3-5 minutes)"
API_URL=$(az deployment group create \
  --resource-group $RG \
  --template-file infra/container-apps.bicep \
  --parameters @$TMP_PARAMS \
  --query "properties.outputs.apiUrl.value" \
  --output tsv 2>&1 | tail -1)

rm -f $TMP_PARAMS

# ── Health check ───────────────────────────────────────────────────────────────
info "Waiting for API to become healthy at $API_URL"
for i in {1..20}; do
  STATUS=$(curl -sf "$API_URL/api/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "down")
  if [[ "$STATUS" == "ok" ]]; then
    info "API is healthy at $API_URL"
    break
  fi
  echo "  attempt $i/20 — status=$STATUS, waiting 15s..."
  sleep 15
done

# ── Print summary ───────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  PrismRAG deployed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo "  API URL:     $API_URL"
echo "  Swagger:     $API_URL/docs"
echo "  ReDoc:       $API_URL/redoc"
echo "  Dashboard:   $API_URL/dashboard.html"
echo "  ACR:         $ACR_SERVER"
echo "  Service Bus: $SB_NS"
echo ""
echo "  Next steps:"
echo "  1. Set DNS CNAME for your subdomain → ${API_URL#https://}"
echo "  2. Run QA suite: pytest tests/ --base-url=$API_URL -v"
echo "  3. Monitor logs: az containerapp logs show -n prismrag-api -g $RG --follow"
echo ""
