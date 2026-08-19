#!/bin/bash
set -euo pipefail

# U Decision API v1.0 — Azure Container Apps Deployment
# Deploys alongside the existing U Brain at the same environment

RESOURCE_GROUP="lifeos-u-rg"
ACR_NAME="ujarvis318105"
ACR_LOGIN_SERVER="ujarvis318105.azurecr.io"
ENV_NAME="u-jarvis-env"
APP_NAME="u-decision-api"
IMAGE="${ACR_LOGIN_SERVER}/u-decision:1.0.0"

echo "=== U Decision API v1.0 — Azure Deployment ==="
echo ""

# ── 1. Build & push image ────────────────────────────────────────
echo "[1/5] Building and pushing container image..."
az acr build \
  --registry "$ACR_NAME" \
  --image u-decision:1.0.0 \
  --file Dockerfile.anchor \
  ./U

echo "[2/5] Deploying container app..."

# ── 2. Deploy container app ─────────────────────────────────────
az containerapp create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --image "$IMAGE" \
  --environment "$ENV_NAME" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-identity system \
  --ingress external \
  --target-port 8000 \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --env-vars \
    U_API_KEY=secretref:u-api-key \
    U_IDENTITY_SECRET=secretref:u-identity-secret \
    U_STATE_DB_PATH=/tmp/u_decision_v1.db

echo "[3/5] Setting secrets..."

# ── 3. Set secrets ──────────────────────────────────────────────
# Generate secure secrets if not provided
API_KEY=$(openssl rand -hex 32)
IDENTITY_SECRET=$(openssl rand -hex 32)

az containerapp secret set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --secrets \
    u-api-key="${API_KEY}" \
    u-identity-secret="${IDENTITY_SECRET}"

echo "[4/5] Getting endpoint URL..."

# ── 4. Get the endpoint ─────────────────────────────────────────
FQDN=$(az containerapp show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_NAME" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

ENDPOINT="https://${FQDN}"
echo "Endpoint: ${ENDPOINT}"

echo "[5/5] Verifying health..."

# ── 5. Health check ──────────────────────────────────────────────
sleep 10
HEALTH=$(curl -s "${ENDPOINT}/health" 2>/dev/null || echo "FAILED")
echo "Health: ${HEALTH}"

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "Endpoint:    ${ENDPOINT}"
echo "Health:      ${ENDPOINT}/health"
echo "Decision:    ${ENDPOINT}/v1/decisions/evaluate"
echo "Delete:      ${ENDPOINT}/v1/users/{user_id}/data"
echo ""
echo "Secrets to set in Base44:"
echo "  U_API_KEY=${API_KEY}"
echo "  U_IDENTITY_SECRET=${IDENTITY_SECRET}"
echo "  U_DECISION_API_URL=${ENDPOINT}"
