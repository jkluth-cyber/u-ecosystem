#!/usr/bin/env bash
#
# U + JARVIS — Python U Brain deployment to Azure Container Apps
# Creator: Jenny Kluth
# Date: 2026-07-29
#
# Prerequisites:
#   - Azure CLI installed (https://aka.ms/azure-cli)
#   - Logged in via `az login`
#   - This script run from the u_jarvis_reference/ directory
#
# What this script does:
#   1. Creates a resource group (if needed)
#   2. Creates an Azure Container Registry (if needed)
#   3. Builds the Docker image and pushes to ACR
#   4. Deploys the Container App using the Bicep template
#   5. Sets all required environment variables / secrets
#   6. Outputs the live URL — paste it into U_BRAIN_API_URL in Base44
#

set -euo pipefail

# ── CONFIG — edit these before running ─────────────────────────────────

LOCATION="eastus"
RG_NAME="u-jarvis-rg"
ACR_NAME="ujarvis$(date +%s | tail -c 7)"
APP_NAME="u-jarvis-api"
IMAGE_TAG="u-jarvis:latest"

# ── SECRETS — paste your values here (or export as env vars before running) ─
U_SHARED_SECRET="${U_SHARED_SECRET:-}"
U_REQUIRE_SIGNED_REQUESTS="${U_REQUIRE_SIGNED_REQUESTS:-true}"

# Optional: Azure OpenAI for LLM features
AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-}"
AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-}"
AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-10-21}"

# Optional: Anthropic for SLO quality evaluation
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-20250514}"

# ─────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  U + JARVIS — Azure Container Apps Deploy   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Verify U_SHARED_SECRET
if [ -z "$U_SHARED_SECRET" ]; then
  echo "ERROR: U_SHARED_SECRET is not set."
  echo ""
  echo "Either:"
  echo "  1. Export it:  export U_SHARED_SECRET='your-32+char-secret'"
  echo "  2. Edit this script and paste it above"
  echo ""
  echo "It must match the U_SHARED_SECRET in Base44 secrets."
  exit 1
fi

if [ ${#U_SHARED_SECRET} -lt 32 ]; then
  echo "ERROR: U_SHARED_SECRET must be at least 32 characters."
  exit 1
fi

echo "✓ U_SHARED_SECRET set (${#U_SHARED_SECRET} chars)"
echo "✓ U_REQUIRE_SIGNED_REQUESTS=$U_REQUIRE_SIGNED_REQUESTS"
echo "✓ Location: $LOCATION"
echo "✓ Resource Group: $RG_NAME"
echo "✓ ACR: $ACR_NAME"
echo "✓ App: $APP_NAME"
echo ""

# ── Step 1: Create resource group ────────────────────────────────────
echo "── Step 1/6: Resource Group ──"
az group create --name "$RG_NAME" --location "$LOCATION" -o table
echo ""

# ── Step 2: Create container registry ────────────────────────────────
echo "── Step 2/6: Container Registry ──"
az acr create --resource-group "$RG_NAME" --name "$ACR_NAME" --sku Basic -o table
az acr login --name "$ACR_NAME"
echo ""

# ── Step 3: Build and push Docker image ──────────────────────────────
echo "── Step 3/6: Build & Push Image ──"
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
echo "Building image → $ACR_LOGIN_SERVER/$IMAGE_TAG"
az acr build --registry "$ACR_NAME" --image "$IMAGE_TAG" .
echo "✓ Image pushed"
echo ""

# ── Step 4: Deploy Container App (Bicep) ─────────────────────────────
echo "── Step 4/6: Deploy Container App ──"
az deployment group create \
  --resource-group "$RG_NAME" \
  --template-file infra/azure.bicep \
  --parameters \
    appName="$APP_NAME" \
    location="$LOCATION"

# Update the container image to point to ACR
az containerapp update \
  --resource-group "$RG_NAME" \
  --name "$APP_NAME" \
  --image "$ACR_LOGIN_SERVER/$IMAGE_TAG"

# Get the FQDN
APP_FQDN=$(az containerapp show \
  --resource-group "$RG_NAME" \
  --name "$APP_NAME" \
  --query properties.configuration.ingress.fqdn -o tsv)

APP_URL="https://$APP_FQDN"
echo "✓ Deployed: $APP_URL"
echo ""

# ── Step 5: Set secrets & env vars ───────────────────────────────────
echo "── Step 5/6: Configure Secrets ──"

SECRETS_STRING="U_SHARED_SECRET=$U_SHARED_SECRET"

if [ -n "$AZURE_OPENAI_API_KEY" ]; then
  SECRETS_STRING="$SECRETS_STRING,AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY"
fi
if [ -n "$AZURE_OPENAI_ENDPOINT" ]; then
  SECRETS_STRING="$SECRETS_STRING,AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT"
fi
if [ -n "$AZURE_OPENAI_DEPLOYMENT" ]; then
  SECRETS_STRING="$SECRETS_STRING,AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT"
fi
if [ -n "$ANTHROPIC_API_KEY" ]; then
  SECRETS_STRING="$SECRETS_STRING,ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
fi

ENV_STRING="U_REQUIRE_SIGNED_REQUESTS=$U_REQUIRE_SIGNED_REQUESTS,U_ENV=production,U_REASONER=deterministic,U_TOOL_MODE=demo,U_DATABASE_PATH=/tmp/u.db"

if [ -n "$AZURE_OPENAI_API_VERSION" ]; then
  ENV_STRING="$ENV_STRING,AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION"
fi
if [ -n "$CLAUDE_MODEL" ]; then
  ENV_STRING="$ENV_STRING,CLAUDE_MODEL=$CLAUDE_MODEL"
fi

az containerapp update \
  --resource-group "$RG_NAME" \
  --name "$APP_NAME" \
  --set-secrets "$SECRETS_STRING" \
  --set-env-vars "$ENV_STRING"

echo "✓ Secrets and env vars configured"
echo ""

# ── Step 6: Verify health ─────────────────────────────────────────────
echo "── Step 6/6: Health Check ──"
echo "Waiting for container to start..."
sleep 10

for i in 1 2 3 4 5; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/api/health" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Health check passed (HTTP 200)"
    break
  fi
  echo "  Attempt $i: HTTP $HTTP_CODE — retrying in 5s..."
  sleep 5
done

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                                                  ║"
echo "║  DEPLOYMENT COMPLETE                             ║"
echo "║                                                  ║"
echo "║  U Brain URL: $APP_URL"
echo "║                                                  ║"
echo "║  Next steps:                                      ║"
echo "║  1. Test: curl $APP_URL/api/health"
echo "║  2. Update U_BRAIN_API_URL in Base44 secrets      ║"
echo "║     → Set to: $APP_URL            ║"
echo "║  3. Test end-to-end from Base44                   ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
