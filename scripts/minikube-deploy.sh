#!/usr/bin/env bash
# =============================================================================
# minikube-deploy.sh — Local test deployment: Minikube + Docker Hub
# =============================================================================
#
# What this script does:
#   1. Checks prerequisites (minikube, kubectl, docker)
#   2. Starts minikube if not already running, enables required addons
#   3. Builds the backend Docker image and pushes it to Docker Hub
#      (use --load to skip Docker Hub and load directly into minikube instead)
#   4. Creates the namespace and generates random secrets
#   5. Applies the local kustomize overlay (kubernetes/overlays/local/)
#   6. Waits for all workloads to become ready
#   7. Prints access instructions
#
# Usage:
#   ./scripts/minikube-deploy.sh                    # full deploy
#   ./scripts/minikube-deploy.sh --skip-build       # skip docker build+push
#   ./scripts/minikube-deploy.sh --load             # load image into minikube instead of Docker Hub
#   ./scripts/minikube-deploy.sh --tag v1.2.3       # use a specific image tag
#
# Required environment variables:
#   DOCKERHUB_USERNAME   your Docker Hub username  (or set --load to skip)
#   DOCKERHUB_TOKEN      your Docker Hub token     (or set --load to skip)
#
# Optional environment variables:
#   AWS_ACCESS_KEY_ID        inject into the backend secret (for Cost Explorer)
#   AWS_SECRET_ACCESS_KEY    inject into the backend secret
#   TAG                      image tag (default: current git short SHA)
# =============================================================================

set -euo pipefail

# ─── Colour helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Defaults ────────────────────────────────────────────────────────────────
DOCKERHUB_USERNAME="${DOCKERHUB_USERNAME:-}"
DOCKERHUB_TOKEN="${DOCKERHUB_TOKEN:-}"
IMAGE_NAME="aws-cost-dashboard-backend"
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
NAMESPACE="aws-cost-dashboard"
OVERLAY_DIR="kubernetes/overlays/local"
SKIP_BUILD=false
LOAD_INTO_MINIKUBE=false    # --load: skip Docker Hub, use `minikube image load`
MINIKUBE_CPUS=2
MINIKUBE_MEMORY=4096        # MB
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ─── Argument parsing ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-build)    SKIP_BUILD=true      ; shift ;;
    --load)          LOAD_INTO_MINIKUBE=true ; shift ;;
    --tag)           TAG="$2"             ; shift 2 ;;
    --cpus)          MINIKUBE_CPUS="$2"   ; shift 2 ;;
    --memory)        MINIKUBE_MEMORY="$2" ; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | grep -v '#!/' | sed 's/^# \{0,2\}//'
      exit 0
      ;;
    *) error "Unknown argument: $1. Run with --help for usage." ;;
  esac
done

# Work from repo root so relative paths are consistent
cd "$REPO_ROOT"

# ─── Step 1: Prerequisites ───────────────────────────────────────────────────
check_prerequisites() {
  info "Checking prerequisites..."
  local missing=()

  for cmd in minikube kubectl docker python3; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Missing required tools: ${missing[*]}\n\nInstall guides:\n  minikube: https://minikube.sigs.k8s.io/docs/start/\n  kubectl:  https://kubernetes.io/docs/tasks/tools/\n  docker:   https://docs.docker.com/get-docker/"
  fi

  if [[ "$LOAD_INTO_MINIKUBE" == "false" && "$SKIP_BUILD" == "false" ]]; then
    [[ -z "$DOCKERHUB_USERNAME" ]] && error "DOCKERHUB_USERNAME is not set.\nSet it or use --load to skip Docker Hub:\n  export DOCKERHUB_USERNAME=your-username"
    [[ -z "$DOCKERHUB_TOKEN"    ]] && error "DOCKERHUB_TOKEN is not set.\nSet it or use --load to skip Docker Hub:\n  export DOCKERHUB_TOKEN=your-token"
  fi

  success "Prerequisites OK"
}

# ─── Step 2: Start minikube ──────────────────────────────────────────────────
start_minikube() {
  info "Checking minikube status..."

  if minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then
    success "Minikube already running ($(minikube ip))"
  else
    info "Starting minikube (${MINIKUBE_CPUS} CPUs, ${MINIKUBE_MEMORY} MB RAM)..."
    minikube start \
      --cpus="$MINIKUBE_CPUS" \
      --memory="$MINIKUBE_MEMORY" \
      --driver=docker
    success "Minikube started"
  fi

  info "Enabling required addons..."
  minikube addons enable ingress        2>/dev/null || true
  minikube addons enable metrics-server 2>/dev/null || true
  success "Addons: ingress, metrics-server"
}

# ─── Step 3: Build & push Docker image ──────────────────────────────────────
build_and_push() {
  if [[ "$SKIP_BUILD" == "true" ]]; then
    warn "Skipping Docker build (--skip-build)"
    return
  fi

  if [[ "$LOAD_INTO_MINIKUBE" == "true" ]]; then
    # Build locally and load directly into minikube — no Docker Hub needed
    local full_image="${IMAGE_NAME}:${TAG}"
    info "Building image $full_image..."
    docker build -t "$full_image" ./backend
    info "Loading image into minikube (this replaces a push to Docker Hub)..."
    minikube image load "$full_image"
    # Update kustomization.yaml to use the locally-loaded image name
    sed -i.bak \
      -e "s|newName: .*|newName: ${IMAGE_NAME}|" \
      -e "s|newTag: .*|newTag: ${TAG}|" \
      "$OVERLAY_DIR/kustomization.yaml"
    rm -f "$OVERLAY_DIR/kustomization.yaml.bak"
    success "Image loaded into minikube: $full_image"
  else
    # Default: build and push to Docker Hub
    local full_image="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"
    info "Logging into Docker Hub..."
    echo "$DOCKERHUB_TOKEN" | docker login --username "$DOCKERHUB_USERNAME" --password-stdin

    info "Building image $full_image..."
    docker build -t "$full_image" ./backend

    info "Pushing $full_image to Docker Hub..."
    docker push "$full_image"

    # Also tag as test-latest for convenience
    local latest_tag="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:test-latest"
    docker tag  "$full_image" "$latest_tag"
    docker push "$latest_tag"

    # Update image name + tag in kustomization.yaml so kubectl apply -k picks it up
    sed -i.bak \
      -e "s|newName: .*|newName: ${DOCKERHUB_USERNAME}/${IMAGE_NAME}|" \
      -e "s|newTag: .*|newTag: ${TAG}|" \
      "$OVERLAY_DIR/kustomization.yaml"
    rm -f "$OVERLAY_DIR/kustomization.yaml.bak"

    success "Pushed $full_image"
  fi
}

# ─── Step 4: Create namespace ────────────────────────────────────────────────
create_namespace() {
  info "Ensuring namespace '$NAMESPACE' exists..."
  kubectl apply -f kubernetes/base/namespace.yaml
  success "Namespace ready"
}

# ─── Step 5: Generate & apply secrets ────────────────────────────────────────
generate_secrets() {
  info "Generating application secrets..."

  local secret_key       ; secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
  local jwt_secret_key   ; jwt_secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
  local encryption_key   ; encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
                             || python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  local postgres_password; postgres_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  local database_url     ; database_url="postgresql://postgres:${postgres_password}@postgres:5432/aws_cost_dashboard"

  # --dry-run=client + apply = idempotent upsert (safe to re-run)
  kubectl create secret generic backend-secret \
    --namespace="$NAMESPACE" \
    --from-literal=SECRET_KEY="$secret_key" \
    --from-literal=JWT_SECRET_KEY="$jwt_secret_key" \
    --from-literal=ENCRYPTION_KEY="$encryption_key" \
    --from-literal=DATABASE_URL="$database_url" \
    --from-literal=POSTGRES_PASSWORD="$postgres_password" \
    --from-literal=REDIS_PASSWORD="" \
    --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}" \
    --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}" \
    --from-literal=TEAMS_WEBHOOK_URL="" \
    --from-literal=EXPORT_S3_BUCKET="" \
    --dry-run=client -o yaml | kubectl apply -f -

  kubectl create secret generic postgres-secret \
    --namespace="$NAMESPACE" \
    --from-literal=POSTGRES_PASSWORD="$postgres_password" \
    --dry-run=client -o yaml | kubectl apply -f -

  success "Secrets applied (generated fresh random values)"

  # Warn if AWS credentials are empty — AWS features won't work without them
  if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
    warn "AWS_ACCESS_KEY_ID is not set — AWS Cost Explorer features will not work."
    warn "Set it before running: export AWS_ACCESS_KEY_ID=AKIA..."
  fi
}

# ─── Step 6: Apply kustomize overlay ─────────────────────────────────────────
deploy() {
  info "Applying local kustomize overlay..."
  kubectl apply -k "$OVERLAY_DIR"
  success "Manifests applied"
}

# ─── Step 7: Wait for rollouts ───────────────────────────────────────────────
wait_for_ready() {
  info "Waiting for Postgres to be ready..."
  kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout=120s

  info "Waiting for Redis to be ready..."
  kubectl rollout status statefulset/redis    -n "$NAMESPACE" --timeout=120s

  info "Waiting for backend to be ready..."
  kubectl rollout status deployment/backend   -n "$NAMESPACE" --timeout=300s

  success "All workloads are running"
}

# ─── Step 8: Print access summary ───────────────────────────────────────────
print_summary() {
  local minikube_ip
  minikube_ip=$(minikube ip 2>/dev/null || echo "<minikube-ip>")

  local full_image
  if [[ "$LOAD_INTO_MINIKUBE" == "true" ]]; then
    full_image="${IMAGE_NAME}:${TAG}"
  else
    full_image="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"
  fi

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║           Deployment complete!  ✅                       ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${BLUE}Image:${NC}      $full_image"
  echo -e "  ${BLUE}Namespace:${NC}  $NAMESPACE"
  echo -e "  ${BLUE}Cluster:${NC}    $(kubectl config current-context 2>/dev/null || echo 'minikube')"
  echo ""
  echo -e "${YELLOW}─── Access the API ───────────────────────────────────────${NC}"
  echo ""
  echo "  Option A — Port-forward (recommended for local dev):"
  echo "    kubectl port-forward -n $NAMESPACE svc/backend 8000:80 &"
  echo ""
  echo "    API:     http://localhost:8000/api/v1"
  echo "    Health:  http://localhost:8000/health"
  echo "    Swagger: http://localhost:8000/docs"
  echo ""
  echo "  Option B — Minikube Ingress (via cluster IP):"
  echo "    API:     http://${minikube_ip}/api/v1"
  echo "    Health:  http://${minikube_ip}/health"
  echo ""
  echo -e "${YELLOW}─── Configure the frontend ───────────────────────────────${NC}"
  echo ""
  echo "  In frontend/.env.local (or frontend/.env):"
  echo "    VITE_API_BASE_URL=http://localhost:8000"
  echo ""
  echo "  Then start the Vite dev server:"
  echo "    cd frontend && npm run dev"
  echo ""
  echo -e "${YELLOW}─── Useful commands ──────────────────────────────────────${NC}"
  echo ""
  echo "  Logs:          kubectl logs -n $NAMESPACE deploy/backend -f"
  echo "  Pod status:    kubectl get pods -n $NAMESPACE"
  echo "  Describe pod:  kubectl describe pod -n $NAMESPACE -l app.kubernetes.io/component=backend"
  echo "  Delete all:    kubectl delete namespace $NAMESPACE"
  echo "  Stop minikube: minikube stop"
  echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AWS Cost Dashboard — Local Deploy (Minikube + Docker Hub) ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo "  TAG: $TAG"
if [[ "$LOAD_INTO_MINIKUBE" == "true" ]]; then
  echo "  Mode: minikube image load (no Docker Hub push)"
elif [[ "$SKIP_BUILD" == "true" ]]; then
  echo "  Mode: skip build, existing image on Docker Hub"
else
  echo "  Mode: build + push to Docker Hub"
fi
echo ""

check_prerequisites
start_minikube
build_and_push
create_namespace
generate_secrets
deploy
wait_for_ready
print_summary
