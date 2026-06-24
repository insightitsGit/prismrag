// PrismRAG — Infrastructure only (Log Analytics + Container Apps environment)
// Container apps are deployed separately via az containerapp CLI for reliable ACR auth.

@description('Azure region')
param location string = resourceGroup().location

@description('Phase 1: use external DB. Set false to deploy Azure Postgres.')
param externalDb bool = true

@description('Phase 3: deploy Azure Cache for Redis.')
param deployRedis bool = false

@description('Postgres SKU (only when externalDb=false).')
@allowed(['Standard_B2s', 'Standard_D4s_v3'])
param postgresSku string = 'Standard_B2s'

@secure()
param dbAdminPassword string = 'not-needed-for-phase1'

// ── Log Analytics workspace (kept for optional queries; capped — not ACA log sink) ──
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'prismrag-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: 0.1
    }
  }
}

// ── Azure Postgres (Phase 2+) ──────────────────────────────────────────────
resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-03-01-preview' = if (!externalDb) {
  name: 'prismrag-pg'
  location: location
  sku: {
    name: postgresSku
    tier: postgresSku == 'Standard_B2s' ? 'Burstable' : 'GeneralPurpose'
  }
  properties: {
    version: '15'
    administratorLogin: 'prismrag'
    administratorLoginPassword: dbAdminPassword
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

// ── Azure Cache for Redis (Phase 3) ───────────────────────────────────────
resource redisCache 'Microsoft.Cache/Redis@2023-08-01' = if (deployRedis) {
  name: 'prismrag-cache'
  location: location
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 1 }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

// ── Container Apps managed environment ───────────────────────────────────
resource env 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'prismrag-env'
  location: location
  properties: {
    appLogsConfiguration: {
      // azure-monitor: stop shipping every stdout line to Log Analytics (~$2.76/GB).
      // App logs go to Blob via PRISMRAG_LOG_BLOB_ENABLED; errors → email.
      destination: 'azure-monitor'
    }
  }
}

output environmentId   string = env.id
output environmentName string = env.name
