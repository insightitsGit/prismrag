# Delete all PrismRAG SaaS Azure resources (prismrag-rg)
# Usage: .\infra\teardown-azure.ps1 [-Force]

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Rg = "prismrag-rg"

Write-Host "==> Checking Azure login..."
az account show *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Run 'az login' first."
}

$exists = az group exists --name $Rg -o tsv
if ($exists -ne "true") {
    Write-Host "Resource group '$Rg' does not exist — nothing to delete."
    exit 0
}

Write-Host "==> Resources in $Rg:"
az resource list -g $Rg --query "[].{name:name, type:type}" -o table

if (-not $Force) {
    $confirm = Read-Host "Delete entire resource group '$Rg'? This cannot be undone. Type YES"
    if ($confirm -ne "YES") {
        Write-Host "Aborted."
        exit 1
    }
}

Write-Host "==> Deleting $Rg (async)..."
az group delete --name $Rg --yes --no-wait
Write-Host "Delete initiated. Check status: az group exists --name $Rg"
Write-Host "Expected monthly Azure cost from PrismRAG SaaS: `$0 after deletion completes."
