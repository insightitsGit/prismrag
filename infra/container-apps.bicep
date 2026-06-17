// PrismRAG — Azure Container Apps deployment
// Deploy: az deployment group create -g prismrag-rg -f infra/container-apps.bicep -p @infra/params.json
//
// Phase 1 (startup):  externalDb=true,  deployRedis=false  → ~$12-31/mo (Neon free + Container Apps)
// Phase 2 (growth):   externalDb=false, deployRedis=false  → ~$80-130/mo (Burstable Postgres)
// Phase 3 (scale):    externalDb=false, deployRedis=true   → ~$250+/mo   (General Purpose + Redis)

@description('Azure region')
param location string = resourceGroup().location

@description('Container registry login server (e.g. prismrag.azurecr.io)')
param acrLoginServer string

@description('Name of the ACR resource (must be in same subscription for role assignment)')
param acrName string = 'prismragacr'

@description('Container image tag')
param imageTag string = 'latest'

@description('Phase 1: use external DB (Neon/Supabase). Set false to deploy Azure Postgres.')
param externalDb bool = true

@description('Phase 3: deploy Azure Cache for Redis. False = in-process TTL cache (fine up to ~500 rps).')
param deployRedis bool = false

@description('Postgres SKU — only used when externalDb=false. Burstable for Phase 2, GeneralPurpose for Phase 3.')
@allowed(['Standard_B2s', 'Standard_D4s_v3'])
param postgresSku string = 'Standard_B2s'

@secure()
@description('DSN for external DB (Phase 1). Ignored when externalDb=false.')
param externalDbDsn string = ''

@secure()
param dbConnectionString string

@secure()
param jwtSecret string

@secure()
param geminiApiKey string

@secure()
param stripeSecretKey string

@secure()
param stripeWebhookSecret string

param stripePriceStarter    string
param stripePriceProf       string
param stripePriceEnterprise string

@secure()
@description('Azure Service Bus connection string (for large-file async worker queue).')
param serviceBusConnectionString string = ''

@secure()
@description('Azure Communication Services connection string (transactional email).')
param azureCommunicationConnectionString string = ''

@description('Verified ACS sender address (e.g. PrismRAG@insightits.com).')
param prismragEmailFrom string = 'PrismRAG@insightits.com'

@description('ACR admin username (for image pull when SP cannot assign AcrPull).')
param acrUsername string

@secure()
@description('ACR admin password.')
param acrPassword string

@description('Public base URL for password-reset links, Stripe redirects, OIDC callbacks.')
param prismragBaseUrl string = 'https://prismrag.insightits.com'


// ── Log Analytics workspace ────────────────────────────────────────────────
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'prismrag-logs'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

// ── User-assigned managed identity for ACR image pull ─────────────────────
resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'prismrag-pull-identity'
  location: location
}

// ── Reference the existing ACR ─────────────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

// AcrPull via managed identity requires roleAssignments/write on the deploy SP.
// Use ACR admin credentials (ACR_USERNAME / ACR_PASSWORD GitHub secrets) instead.

// ── Azure Postgres Flexible Server (Phase 2+, skipped in Phase 1) ─────────
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
    administratorLoginPassword: dbConnectionString
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: {
      mode: postgresSku == 'Standard_B2s' ? 'Disabled' : 'ZoneRedundant'
    }
  }
}

// pgvector extension must be enabled after server creation:
//   az postgres flexible-server parameter set --name azure.extensions --value vector ...

// ── Azure Cache for Redis (Phase 3, skipped in Phase 1+2) ────────────────
resource redisCache 'Microsoft.Cache/Redis@2023-08-01' = if (deployRedis) {
  name: 'prismrag-cache'
  location: location
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 1 }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

var resolvedDbDsn    = externalDb ? externalDbDsn : dbConnectionString
var resolvedRedisUrl = deployRedis ? 'rediss://:${redisCache.listKeys().primaryKey}@${redisCache.properties.hostName}:6380' : 'not-configured'

// ── Container Apps environment ─────────────────────────────────────────────
resource env 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: 'prismrag-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logWorkspace.properties.customerId
        sharedKey: logWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// ── Shared env vars & secrets ──────────────────────────────────────────────
var sharedEnv = [
  { name: 'PRISMRAG_DB_DSN',             secretRef: 'db-dsn' }
  { name: 'REDIS_URL',                   secretRef: 'redis-url' }
  { name: 'JWT_SECRET',                  secretRef: 'jwt-secret' }
  { name: 'GEMINI_API_KEY',              secretRef: 'gemini-key' }
  { name: 'STRIPE_SECRET_KEY',           secretRef: 'stripe-secret' }
  { name: 'STRIPE_WEBHOOK_SECRET',       secretRef: 'stripe-webhook' }
  { name: 'AZURE_SERVICE_BUS_CONNECTION_STRING', secretRef: 'servicebus-conn' }
  { name: 'STRIPE_PRICE_STARTER',        value: stripePriceStarter }
  { name: 'STRIPE_PRICE_PROFESSIONAL',   value: stripePriceProf }
  { name: 'STRIPE_PRICE_ENTERPRISE',     value: stripePriceEnterprise }
  { name: 'PRISMRAG_ENV',                value: 'production' }
  { name: 'AZURE_COMMUNICATION_CONNECTION_STRING', secretRef: 'acs-conn' }
  { name: 'PRISMRAG_EMAIL_FROM',         value: prismragEmailFrom }
  { name: 'PRISMRAG_EMAIL_ENABLED',      value: 'true' }
  { name: 'PRISMRAG_BASE_URL',           value: prismragBaseUrl }
]

var sharedSecrets = [
  { name: 'db-dsn',          value: empty(resolvedDbDsn)              ? 'not-configured' : resolvedDbDsn }
  { name: 'jwt-secret',      value: jwtSecret }
  { name: 'gemini-key',      value: geminiApiKey }
  { name: 'stripe-secret',   value: empty(stripeSecretKey)            ? 'not-configured' : stripeSecretKey }
  { name: 'stripe-webhook',  value: empty(stripeWebhookSecret)        ? 'not-configured' : stripeWebhookSecret }
  { name: 'redis-url',       value: resolvedRedisUrl }
  { name: 'servicebus-conn', value: empty(serviceBusConnectionString)  ? 'not-configured' : serviceBusConnectionString }
  { name: 'acs-conn',        value: empty(azureCommunicationConnectionString) ? 'not-configured' : azureCommunicationConnectionString }
  { name: 'acr-password',    value: acrPassword }
]

var registryConfig = [
  {
    server: acrLoginServer
    username: acrUsername
    passwordSecretRef: 'acr-password'
  }
]

// ── API service ────────────────────────────────────────────────────────────
resource apiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'prismrag-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${pullIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      secrets: sharedSecrets
      registries: registryConfig
      ingress: {
        external: true
        targetPort: 8001
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/prismrag-api:${imageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: sharedEnv
          probes: [
            {
              type: 'Readiness'
              httpGet: { path: '/api/prismrag/health', port: 8001 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Liveness'
              httpGet: { path: '/api/prismrag/health', port: 8001 }
              initialDelaySeconds: 15
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 20
        rules: [
          {
            name: 'http-scale'
            http: { metadata: { concurrentRequests: '50' } }
          }
        ]
      }
    }
  }
}

// ── Worker service (scale-to-zero) ────────────────────────────────────────
resource workerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'prismrag-worker'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${pullIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      secrets: sharedSecrets
      registries: registryConfig
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/prismrag-worker:${imageTag}'
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: sharedEnv
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 10
        rules: [
          {
            name: 'servicebus-scale'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'prismrag-jobs'
                messageCount: '5'
              }
            }
          }
        ]
      }
    }
  }
}

output apiUrl string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
