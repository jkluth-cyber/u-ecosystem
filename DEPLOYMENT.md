# U + JARVIS — Azure Container Apps Deployment Guide

## Prerequisites

1. **Azure CLI** — install from https://aka.ms/azure-cli
2. **Login** — run `az login` and select your subscription
3. **U_SHARED_SECRET** — you already set this in Base44. Use the same value here.

## Quick Deploy (5 commands)

```bash
# 1. Clone or copy the u_jarvis_reference directory to your machine
# 2. cd into it
cd u_jarvis_reference

# 3. Make the deploy script executable
chmod +x deploy.sh

# 4. Run it (export your shared secret first)
export U_SHARED_SECRET='your-48-char-secret-from-base44'
./deploy.sh

# 5. The script outputs a URL like https://u-jarvis-api.eastus.azurecontainerapps.io
#    Paste that URL into U_BRAIN_API_URL in Base44 secrets
```

## Manual Deploy (step by step)

If you prefer to run each command individually:

### 1. Create resource group
```bash
az group create --name u-jarvis-rg --location eastus
```

### 2. Create container registry
```bash
# ACR name must be globally unique, lowercase, 5-50 chars
ACR_NAME="ujarvis$(date +%s | tail -c 7)"
az acr create --resource-group u-jarvis-rg --name $ACR_NAME --sku Basic
az acr login --name $ACR_NAME
```

### 3. Build and push image
```bash
ACR_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
az acr build --registry $ACR_NAME --image u-jarvis:latest .
```

### 4. Deploy container app
```bash
az deployment group create \
  --resource-group u-jarvis-rg \
  --template-file infra/azure.bicep \
  --parameters appName=u-jarvis-api location=eastus

# Update the image to point to your ACR
az containerapp update \
  --resource-group u-jarvis-rg \
  --name u-jarvis-api \
  --image $ACR_SERVER/u-jarvis:latest
```

### 5. Set secrets
```bash
az containerapp update \
  --resource-group u-jarvis-rg \
  --name u-jarvis-api \
  --set-secrets "U_SHARED_SECRET=your-48-char-secret" \
  --set-env-vars "U_REQUIRE_SIGNED_REQUESTS=true,U_ENV=production"
```

### 6. Get the URL
```bash
APP_URL="https://$(az containerapp show --resource-group u-jarvis-rg --name u-jarvis-api --query properties.configuration.ingress.fqdn -o tsv)"
echo "U Brain URL: $APP_URL"

# Health check
curl $APP_URL/api/health
```

### 7. Update Base44
- Go to Base44 → Settings → Secrets
- Update `U_BRAIN_API_URL` to `$APP_URL` (no trailing slash)

## Optional: Enable LLM features

To enable Azure OpenAI for the intelligence engines:

```bash
az containerapp secret set \
  --resource-group u-jarvis-rg \
  --name u-jarvis-api \
  --secrets "AZURE_OPENAI_API_KEY=your-key" \
  --secrets "AZURE_OPENAI_ENDPOINT=your-endpoint" \
  --secrets "AZURE_OPENAI_DEPLOYMENT=your-deployment"

az containerapp update \
  --resource-group u-jarvis-rg \
  --name u-jarvis-api \
  --set-env-vars "AZURE_OPENAI_API_VERSION=2024-10-21,U_REASONER=langchain"
```

## Verify end-to-end

Once deployed and Base44 secrets updated:

1. **Health check**: `curl $APP_URL/api/health` → should return `{"status":"healthy",...}`
2. **Signing health**: `curl $APP_URL/api/health` → check `signing_enabled: true`
3. **End-to-end**: Call the `uDecisionResearch` backend function from Base44 with a test request

## Architecture

```
Base44 (TypeScript gateway)        Python U Brain (Container App)
┌─────────────────────────┐       ┌──────────────────────────┐
│ uDecisionResearch        │       │ FastAPI (uvicorn:8000)    │
│  → auth (user.me)        │──────→│  → verify HMAC-SHA256    │
│  → crisis gate           │  HTTPS│  → consent + safety gate  │
│  → consent recording     │signed │  → 18 engines             │
│  → audit logging         │ req   │  → Stay/Change/Pause     │
│  → session management    │       │  → trajectory + ripple   │
│  → HMAC-SHA256 signing   │       │  → SQLite persistence    │
└─────────────────────────┘       └──────────────────────────┘
```

## Troubleshooting

**Container won't start:**
```bash
az containerapp logs show --resource-group u-jarvis-rg --name u-jarvis-api
```

**Health check fails:**
- Wait 30s for cold start
- Check if port 8000 is exposed in the Bicep template
- Verify secrets are set (U_SHARED_SECRET is required)

**Signed requests rejected:**
- Verify U_SHARED_SECRET matches on both sides
- Verify U_REQUIRE_SIGNED_REQUESTS=true on Python side
- Check timestamp skew (max 5 minutes)

**Resource costs:**
- ACR Basic: ~$5/month
- Container App (1 replica, 0.5 CPU): ~$10-15/month
- Log Analytics: free for first 5GB/month
