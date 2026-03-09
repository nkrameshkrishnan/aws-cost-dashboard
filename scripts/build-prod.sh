#!/usr/bin/env bash
# =============================================================================
# build-prod.sh — Build production Docker images
#
# Usage:
#   ./scripts/build-prod.sh [--push]
#
# Reads ALL config from .env.production at the project root.
# Pass --push to push images to the registry after building.
#
# Architecture note:
#   The frontend is primarily served from GitHub Pages (free, static).
#   The frontend Docker image is built here for reference / self-hosted
#   deployments, but is NOT deployed to ECS.
#   For GitHub Pages deployment use: ./scripts/deploy-pages.sh
#
#   The backend Docker image IS deployed to ECS Fargate via Terraform.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env.production"

# ---- Validate env file -------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found."
  echo "Copy .env.example to .env.production and fill in real values first."
  exit 1
fi

# Load vars from .env.production (skip comments and blank lines)
set -a
# shellcheck disable=SC1090
source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
set +a

PUSH="${1:-}"

# ---- Validate required vars --------------------------------------------------
REQUIRED=(DOCKER_REGISTRY VERSION VITE_API_BASE_URL)
for var in "${REQUIRED[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set in $ENV_FILE"
    exit 1
  fi
done

echo "=== Building images for version: $VERSION ==="
echo "    Registry : $DOCKER_REGISTRY"
echo "    API URL  : $VITE_API_BASE_URL"
echo ""

# ---- Backend image -----------------------------------------------------------
echo "--- Building backend ---"
docker build \
  -f "$ROOT_DIR/backend/Dockerfile.prod" \
  -t "$DOCKER_REGISTRY/aws-cost-dashboard-backend:$VERSION" \
  -t "$DOCKER_REGISTRY/aws-cost-dashboard-backend:latest" \
  "$ROOT_DIR/backend"
echo "    ✓ Backend image built"

# ---- Frontend image ----------------------------------------------------------
# Note: The frontend is served from GitHub Pages in production.
#       This image is built for reference / alternative self-hosted deployments.
#       For GitHub Pages: ./scripts/deploy-pages.sh
echo ""
echo "--- Building frontend (baking VITE_* vars into bundle) ---"
docker build \
  --build-arg VITE_API_BASE_URL="$VITE_API_BASE_URL" \
  --build-arg VITE_API_VERSION="${VITE_API_VERSION:-v1}" \
  --build-arg VITE_APP_NAME="${VITE_APP_NAME:-AWS Cost Dashboard}" \
  --build-arg VITE_APP_VERSION="${VITE_APP_VERSION:-$VERSION}" \
  -f "$ROOT_DIR/frontend/Dockerfile.prod" \
  -t "$DOCKER_REGISTRY/aws-cost-dashboard-frontend:$VERSION" \
  -t "$DOCKER_REGISTRY/aws-cost-dashboard-frontend:latest" \
  "$ROOT_DIR/frontend"
echo "    ✓ Frontend image built"

echo ""
echo "=== Build complete ==="

# ---- Push (optional) ---------------------------------------------------------
if [[ "$PUSH" == "--push" ]]; then
  echo ""
  echo "--- Pushing images to $DOCKER_REGISTRY ---"
  docker push "$DOCKER_REGISTRY/aws-cost-dashboard-backend:$VERSION"
  docker push "$DOCKER_REGISTRY/aws-cost-dashboard-backend:latest"
  docker push "$DOCKER_REGISTRY/aws-cost-dashboard-frontend:$VERSION"
  docker push "$DOCKER_REGISTRY/aws-cost-dashboard-frontend:latest"
  echo "=== Push complete ==="
  echo ""
  echo "Next step — update terraform.tfvars:"
  echo "  backend_image = \"$DOCKER_REGISTRY/aws-cost-dashboard-backend:$VERSION\""
  echo "Then run: ./scripts/deploy.sh production apply"
else
  echo ""
  echo "Tips:"
  echo "  Run with --push to push images to the registry."
  echo "  Deploy backend to ECS : ./scripts/deploy.sh production apply"
  echo "  Deploy frontend pages  : ./scripts/deploy-pages.sh"
fi
