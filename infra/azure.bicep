// U + JARVIS — Azure Container Apps Bicep template
// Creator: Jenny Kluth | Version 2026.07.29
// Deploy with: az deployment group create --resource-group <rg> --template-file infra/azure.bicep --parameters appName=<name> location=<region>

param location string = resourceGroup().location
param appName string = 'u-jarvis-api'

// ── Log Analytics ───────────────────────────────────────────────────
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  properties: {
    retentionInDays: 30
  }
}

// ── Managed Environment ──────────────────────────────────────────────
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// ── Container App ────────────────────────────────────────────────────
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      registries: [
        {
          server: 'ujarvis318105.azurecr.io'
          username: 'PLACEHOLDER_ACR_USER'
          passwordSecretRef: 'acr-password'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
        }
      }
      secrets: [
        {
          name: 'u-shared-secret'
          value: 'PLACEHOLDER_SECRET'
        }
        {
          name: 'acr-password'
          value: 'PLACEHOLDER_ACR_PASS'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'u-jarvis'
          image: 'ujarvis318105.azurecr.io/u-jarvis:latest'
          env: [
            {
              name: 'U_REASONER'
              value: 'deterministic'
            }
            {
              name: 'U_TOOL_MODE'
              value: 'demo'
            }
            {
              name: 'U_ENV'
              value: 'production'
            }
            {
              name: 'U_DATABASE_PATH'
              value: '/tmp/u.db'
            }
            {
              name: 'U_REQUIRE_SIGNED_REQUESTS'
              value: 'true'
            }
            {
              name: 'U_SHARED_SECRET'
              secretRef: 'u-shared-secret'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output url string = 'https://${app.properties.configuration.ingress.fqdn}'
output appName string = app.name
output resourceGroup string = resourceGroup().name
