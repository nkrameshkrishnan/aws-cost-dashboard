#!/usr/bin/env bash
# =============================================================================
# eks-deploy.sh — Full EKS deployment for AWS Cost Dashboard
#
# Run this script once to go from nothing → a live production deployment.
# It is safe to re-run; most steps are idempotent.
#
# Prerequisites (install once):
#   macOS:  brew install awscli eksctl kubectl helm
#   Linux:  see INSTALL section below for curl-based installers
#
# Usage:
#   # 1. Configure your AWS credentials first:
#   aws configure
#
#   # 2. Run the deploy
#   chmod +x scripts/eks-deploy.sh
#   ./scripts/eks-deploy.sh
#
# What this script does:
#   Stage 1  — Validate prerequisites
#   Stage 2  — Create ECR repository + build/push Docker image
#   Stage 3  — Create EKS cluster (takes ~15 min)
#   Stage 4  — Install nginx-ingress + cert-manager via Helm
#   Stage 5  — Get the public NLB hostname → derive sslip.io API URL
#   Stage 6  — Generate application secrets + apply Kubernetes manifests
#   Stage 7  — Print summary + next steps
# =============================================================================
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these values before running
# ─────────────────────────────────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=""          # auto-detected from `aws sts get-caller-identity`
ECR_REPO_NAME="aws-cost-dashboard-backend"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$(dirname "$0")/.." rev-parse --short HEAD 2>/dev/null || echo "latest")}"
CLUSTER_NAME="aws-cost-dashboard"
NAMESPACE="aws-cost-dashboard"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Colours
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
banner()  { echo -e "\n${CYAN}════════════════════════════════════════════════════${NC}"; echo -e "${CYAN} $*${NC}"; echo -e "${CYAN}════════════════════════════════════════════════════${NC}"; }

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — Prerequisites
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 1 · Checking prerequisites"

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    error "$1 not found. Install it:\n  $2"
  fi
  success "$1 $(\"$1\" --version 2>&1 | head -1)"
}

check_cmd aws      "brew install awscli  OR  https://aws.amazon.com/cli/"
check_cmd eksctl   "brew tap weaveworks/tap && brew install weaveworks/tap/eksctl  OR  https://eksctl.io"
check_cmd kubectl  "brew install kubectl  OR  https://kubernetes.io/docs/tasks/tools/"
check_cmd helm     "brew install helm  OR  https://helm.sh/docs/intro/install/"
check_cmd docker   "https://docs.docker.com/get-docker/"

# Verify Docker is running
docker info &>/dev/null || error "Docker daemon is not running. Start Docker Desktop first."

# Verify AWS credentials
info "Verifying AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) \
  || error "AWS credentials not configured. Run: aws configure"
success "AWS Account: $AWS_ACCOUNT_ID  Region: $AWS_REGION"

ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — ECR + Docker image
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 2 · ECR repository + Docker image"

# Create ECR repo (idempotent)
info "Creating ECR repository '$ECR_REPO_NAME' (skipped if already exists)..."
aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" &>/dev/null \
  || aws ecr create-repository \
       --repository-name "$ECR_REPO_NAME" \
       --image-scanning-configuration scanOnPush=true \
       --encryption-configuration encryptionType=AES256 \
       --region "$AWS_REGION" \
       --output json | python3 -c "import sys,json; r=json.load(sys.stdin)['repository']; print(f'  Created: {r[\"repositoryUri\"]}')"

ECR_IMAGE="$ECR_REGISTRY/$ECR_REPO_NAME"
success "ECR image URI: $ECR_IMAGE:$IMAGE_TAG"

# Authenticate Docker with ECR
info "Logging Docker into ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

# Build backend image
info "Building backend Docker image (tag: $IMAGE_TAG)..."
docker build \
  -f "$ROOT_DIR/backend/Dockerfile.prod" \
  -t "$ECR_IMAGE:$IMAGE_TAG" \
  -t "$ECR_IMAGE:latest" \
  "$ROOT_DIR/backend"
success "Image built: $ECR_IMAGE:$IMAGE_TAG"

# Push to ECR
info "Pushing image to ECR..."
docker push "$ECR_IMAGE:$IMAGE_TAG"
docker push "$ECR_IMAGE:latest"
success "Image pushed to ECR"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — EKS cluster
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 3 · EKS cluster (this takes ~15 minutes)"

if eksctl get cluster --name "$CLUSTER_NAME" --region "$AWS_REGION" &>/dev/null; then
  warn "Cluster '$CLUSTER_NAME' already exists — skipping creation"
else
  info "Creating EKS cluster from $SCRIPT_DIR/eks-cluster.yaml ..."
  eksctl create cluster -f "$SCRIPT_DIR/eks-cluster.yaml"
  success "EKS cluster created"
fi

# Update local kubeconfig
info "Updating kubeconfig..."
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
success "kubectl context: $(kubectl config current-context)"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4 — nginx-ingress + cert-manager
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 4 · nginx-ingress + cert-manager"

# Add Helm repos
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx &>/dev/null || true
helm repo add jetstack https://charts.jetstack.io &>/dev/null || true
helm repo update &>/dev/null

# Install / upgrade nginx-ingress
info "Installing nginx-ingress controller..."
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb \
  --set controller.config.use-forwarded-headers="true" \
  --wait --timeout 5m
success "nginx-ingress installed"

# Install / upgrade cert-manager
info "Installing cert-manager..."
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --wait --timeout 5m
success "cert-manager installed"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 5 — Discover NLB hostname → sslip.io API URL
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 5 · Discovering public API hostname"

info "Waiting for NLB to be provisioned (up to 5 min)..."
NLB_HOSTNAME=""
for i in $(seq 1 30); do
  NLB_HOSTNAME=$(kubectl get svc ingress-nginx-controller -n ingress-nginx \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
  if [[ -n "$NLB_HOSTNAME" ]]; then
    break
  fi
  echo -n "."
  sleep 10
done
echo ""

if [[ -z "$NLB_HOSTNAME" ]]; then
  error "NLB hostname not available after 5 min. Check: kubectl get svc -n ingress-nginx"
fi
success "NLB hostname: $NLB_HOSTNAME"

# Resolve NLB hostname to IP for sslip.io (NLBs resolve to IPs)
info "Resolving NLB IP for sslip.io TLS hostname..."
NLB_IP=""
for i in $(seq 1 12); do
  NLB_IP=$(python3 -c "import socket; print(socket.gethostbyname('$NLB_HOSTNAME'))" 2>/dev/null || true)
  if [[ -n "$NLB_IP" ]]; then
    break
  fi
  echo -n "."
  sleep 10
done
echo ""

if [[ -z "$NLB_IP" ]]; then
  warn "Could not resolve NLB IP. Using NLB hostname directly (HTTP only, no TLS)."
  API_HOSTNAME="$NLB_HOSTNAME"
  USE_TLS=false
else
  # sslip.io maps IP dashes to DNS, e.g. 1.2.3.4 → 1-2-3-4.sslip.io
  SSLIP_HOSTNAME="$(echo "$NLB_IP" | tr '.' '-').sslip.io"
  API_HOSTNAME="$SSLIP_HOSTNAME"
  USE_TLS=true
  success "sslip.io TLS hostname: $API_HOSTNAME  (maps to $NLB_IP)"
fi

API_URL="https://$API_HOSTNAME"
[[ "$USE_TLS" == false ]] && API_URL="http://$API_HOSTNAME"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 6 — Generate secrets + apply Kubernetes manifests
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 6 · Deploying application"

# Generate strong secrets
info "Generating application secrets..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/aws_cost_dashboard"
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null \
  || python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

# Base64-encode for Kubernetes secrets
b64() { echo -n "$1" | base64; }

# Apply namespace first
kubectl apply -f "$ROOT_DIR/kubernetes/base/namespace.yaml"

# Apply RBAC (ServiceAccounts, Role, RoleBinding)
kubectl apply -f "$ROOT_DIR/kubernetes/base/rbac.yaml"

# Apply ConfigMap (update CORS + AWS region)
kubectl apply -f - <<EOF
$(sed \
  -e "s|us-east-1|$AWS_REGION|g" \
  "$ROOT_DIR/kubernetes/base/configmap.yaml")
EOF
success "ConfigMap applied"

# Apply generated Secret
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: backend-secret
  namespace: $NAMESPACE
type: Opaque
data:
  SECRET_KEY: $(b64 "$SECRET_KEY")
  JWT_SECRET_KEY: $(b64 "$JWT_SECRET_KEY")
  ENCRYPTION_KEY: $(b64 "$ENCRYPTION_KEY")
  DATABASE_URL: $(b64 "$DATABASE_URL")
  POSTGRES_PASSWORD: $(b64 "$POSTGRES_PASSWORD")
  REDIS_PASSWORD: $(b64 "")
  AWS_ACCESS_KEY_ID: $(b64 "")
  AWS_SECRET_ACCESS_KEY: $(b64 "")
  TEAMS_WEBHOOK_URL: $(b64 "")
  EXPORT_S3_BUCKET: $(b64 "")
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: $NAMESPACE
type: Opaque
data:
  POSTGRES_PASSWORD: $(b64 "$POSTGRES_PASSWORD")
EOF
success "Secrets applied (generated fresh)"

# Apply NetworkPolicies
kubectl apply -f "$ROOT_DIR/kubernetes/base/network-policies.yaml"

# Deploy PostgreSQL + Redis (in-cluster)
info "Deploying PostgreSQL..."
kubectl apply -f "$ROOT_DIR/kubernetes/postgres/"
info "Deploying Redis..."
kubectl apply -f "$ROOT_DIR/kubernetes/redis/"

# Wait for databases to be ready
info "Waiting for PostgreSQL..."
kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout=3m
info "Waiting for Redis..."
kubectl rollout status statefulset/redis -n "$NAMESPACE" --timeout=3m

# Deploy backend (patch image to ECR URI)
info "Deploying backend..."
kubectl apply -f - <<EOF
$(sed "s|REPLACE_WITH_ECR_IMAGE|$ECR_IMAGE:$IMAGE_TAG|g" \
  "$ROOT_DIR/kubernetes/backend/deployment.yaml")
EOF
kubectl apply -f "$ROOT_DIR/kubernetes/backend/service.yaml"
kubectl apply -f "$ROOT_DIR/kubernetes/backend/hpa.yaml"

kubectl rollout status deployment/backend -n "$NAMESPACE" --timeout=5m
success "Backend deployed"

# Apply Ingress (with correct hostname + TLS if using sslip.io)
info "Configuring Ingress ($API_HOSTNAME)..."

if [[ "$USE_TLS" == true ]]; then
  # Apply cert-manager ClusterIssuer (Let's Encrypt)
  kubectl apply -f "$ROOT_DIR/kubernetes/ingress/cert-issuer.yaml"

  kubectl apply -f - <<EOF
$(sed \
  -e "s|api.your-domain.com|$API_HOSTNAME|g" \
  "$ROOT_DIR/kubernetes/ingress/ingress.yaml")
EOF
else
  # HTTP-only ingress (no TLS, no cert annotation)
  kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: backend-ingress
  namespace: $NAMESPACE
  annotations:
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://nkrameshkrishnan.github.io"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "Authorization, Content-Type, Accept"
    nginx.ingress.kubernetes.io/cors-allow-credentials: "true"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "120"
    nginx.ingress.kubernetes.io/limit-rps: "20"
spec:
  rules:
    - host: $API_HOSTNAME
      http:
        paths:
          - path: /health
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  name: http
          - path: /api/v1
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  name: http
EOF
fi
success "Ingress applied"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 7 — Summary
# ─────────────────────────────────────────────────────────────────────────────
banner "Stage 7 · Deployment complete"

# Save API URL for easy retrieval
echo "$API_URL" > "$ROOT_DIR/.api-url"

echo ""
echo -e "${GREEN}✓ EKS deployment complete!${NC}"
echo ""
echo "  API URL:    $API_URL"
echo "  Health:     $API_URL/health"
echo "  Cluster:    $CLUSTER_NAME ($AWS_REGION)"
echo "  Image:      $ECR_IMAGE:$IMAGE_TAG"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "  1. Verify the backend is healthy:"
echo "     curl $API_URL/health"
echo ""
echo "  2. Update VITE_API_BASE_URL in GitHub Actions:"
echo "     → Go to: https://github.com/nkrameshkrishnan/aws-cost-dashboard/settings/secrets/actions"
echo "     → Set VITE_API_BASE_URL = $API_URL"
echo "     → Then re-run: Actions → Deploy Frontend → Run workflow"
echo ""
if [[ "$USE_TLS" == true ]]; then
echo "  3. TLS certificate status (takes ~2 min after first request):"
echo "     kubectl describe certificate backend-tls -n $NAMESPACE"
echo ""
fi
echo "  4. Watch everything:"
echo "     kubectl get all -n $NAMESPACE"
echo ""
echo "  5. Tail backend logs:"
echo "     kubectl logs -n $NAMESPACE -l app.kubernetes.io/component=backend -f"
echo ""
echo -e "${YELLOW}To tear down everything:${NC}"
echo "  eksctl delete cluster --name $CLUSTER_NAME --region $AWS_REGION"
echo "  aws ecr delete-repository --repository-name $ECR_REPO_NAME --force --region $AWS_REGION"
echo ""
