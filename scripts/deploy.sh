#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy the AWS Cost Dashboard backend infrastructure
#
# Usage:
#   ./scripts/deploy.sh [environment] [action]
#
# Arguments:
#   environment : dev | staging | production  (default: dev)
#   action      : plan | apply | destroy      (default: plan)
#
# Architecture:
#   Frontend → GitHub Pages  (deploy with ./scripts/deploy-pages.sh)
#   Backend  → ECS Fargate   (deployed here via Terraform)
#   Entry    → API Gateway   (public HTTPS endpoint)
#
# Examples:
#   ./scripts/deploy.sh dev plan
#   ./scripts/deploy.sh production apply
#   ./scripts/deploy.sh staging destroy
# =============================================================================
set -euo pipefail

# ---- Colours -----------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ---- Args --------------------------------------------------------------------
ENVIRONMENT="${1:-dev}"
ACTION="${2:-plan}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"
ENV_FILE="$PROJECT_ROOT/.env.production"

# ---- Helpers -----------------------------------------------------------------
header()  { echo -e "${BLUE}============================================================${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}============================================================${NC}"; }
ok()      { echo -e "${GREEN}✓ $1${NC}"; }
err()     { echo -e "${RED}✗ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
info()    { echo -e "${BLUE}ℹ $1${NC}"; }

# ---- Validate inputs ---------------------------------------------------------
validate_inputs() {
  if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    err "Invalid environment: $ENVIRONMENT"
    echo "Valid environments: dev, staging, production"
    exit 1
  fi

  if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
    err "Invalid action: $ACTION"
    echo "Valid actions: plan, apply, destroy"
    exit 1
  fi
}

# ---- Check prerequisites -----------------------------------------------------
check_prereqs() {
  header "Checking Prerequisites"

  for tool in terraform aws docker jq; do
    if command -v "$tool" &>/dev/null; then
      ok "$tool installed"
    else
      err "$tool is not installed"
      exit 1
    fi
  done

  if aws sts get-caller-identity &>/dev/null; then
    local account; account=$(aws sts get-caller-identity --query Account --output text)
    local arn;     arn=$(aws sts get-caller-identity --query Arn --output text)
    ok "AWS credentials valid"
    info "Account : $account"
    info "Identity: $arn"
  else
    err "AWS credentials not configured (run: aws configure)"
    exit 1
  fi

  if [[ ! -d "$TERRAFORM_DIR" ]]; then
    err "Terraform directory not found: $TERRAFORM_DIR"
    exit 1
  fi

  ok "All prerequisites met"
  echo
}

# ---- Build and push backend image -------------------------------------------
build_and_push_backend() {
  header "Building Backend Docker Image"

  # Load .env.production to get DOCKER_REGISTRY and VERSION
  if [[ ! -f "$ENV_FILE" ]]; then
    warn ".env.production not found — skipping Docker build"
    warn "Set DOCKER_REGISTRY and VERSION in .env.production, then re-run."
    return 0
  fi

  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
  set +a

  if [[ -z "${DOCKER_REGISTRY:-}" ]] || [[ -z "${VERSION:-}" ]]; then
    warn "DOCKER_REGISTRY or VERSION not set in .env.production — skipping Docker build"
    return 0
  fi

  local backend_tag="$DOCKER_REGISTRY/aws-cost-dashboard-backend:$VERSION"

  info "Building $backend_tag ..."
  docker build \
    -f "$PROJECT_ROOT/backend/Dockerfile.prod" \
    -t "$backend_tag" \
    -t "$DOCKER_REGISTRY/aws-cost-dashboard-backend:latest" \
    "$PROJECT_ROOT/backend"
  ok "Backend image built"

  info "Pushing $backend_tag ..."
  docker push "$backend_tag"
  docker push "$DOCKER_REGISTRY/aws-cost-dashboard-backend:latest"
  ok "Backend image pushed"

  echo
  info "Update backend_image in terraform.tfvars to: $backend_tag"
  echo
}

# ---- Terraform init ----------------------------------------------------------
tf_init() {
  header "Initialising Terraform"

  cd "$TERRAFORM_DIR"

  if [[ ! -f "terraform.tfvars" ]]; then
    err "terraform.tfvars not found in $TERRAFORM_DIR"
    info "Copy terraform.tfvars.example to terraform.tfvars and fill in your values"
    exit 1
  fi

  terraform init
  ok "Terraform initialised"
  echo
}

# ---- Terraform plan ----------------------------------------------------------
tf_plan() {
  header "Running Terraform Plan"
  cd "$TERRAFORM_DIR"

  terraform plan \
    -var="environment=$ENVIRONMENT" \
    -out="tfplan-${ENVIRONMENT}.out"

  ok "Plan saved to tfplan-${ENVIRONMENT}.out"
  echo
}

# ---- Terraform apply ---------------------------------------------------------
tf_apply() {
  header "Applying Terraform Changes"
  cd "$TERRAFORM_DIR"

  if [[ ! -f "tfplan-${ENVIRONMENT}.out" ]]; then
    warn "No plan file found — running plan first"
    tf_plan
  fi

  if [[ "$ENVIRONMENT" == "production" ]]; then
    warn "You are about to deploy to PRODUCTION"
    read -rp "Type 'yes' to confirm: " confirm
    [[ "$confirm" == "yes" ]] || { err "Deployment cancelled"; exit 1; }
  fi

  terraform apply "tfplan-${ENVIRONMENT}.out"
  rm -f "tfplan-${ENVIRONMENT}.out"

  ok "Terraform apply complete"
  echo
}

# ---- Terraform destroy -------------------------------------------------------
tf_destroy() {
  header "Destroying Infrastructure"
  cd "$TERRAFORM_DIR"

  warn "You are about to DESTROY all $ENVIRONMENT infrastructure"
  read -rp "Type 'destroy-$ENVIRONMENT' to confirm: " confirm
  [[ "$confirm" == "destroy-$ENVIRONMENT" ]] || { err "Destruction cancelled"; exit 1; }

  terraform destroy -var="environment=$ENVIRONMENT" -auto-approve
  ok "Infrastructure destroyed"
  echo
}

# ---- Show post-deploy info ---------------------------------------------------
show_info() {
  header "Deployment Information"
  cd "$TERRAFORM_DIR"

  local api_url;     api_url=$(terraform output -raw api_gateway_url    2>/dev/null || echo "N/A")
  local cluster;     cluster=$(terraform output -raw ecs_cluster_name    2>/dev/null || echo "N/A")
  local svc;         svc=$(terraform output -raw backend_service_name    2>/dev/null || echo "N/A")
  local custom_url;  custom_url=$(terraform output -raw custom_domain_url 2>/dev/null || echo "")

  echo ""
  echo -e "  Environment   : ${GREEN}$ENVIRONMENT${NC}"
  echo -e "  API Gateway   : ${GREEN}$api_url${NC}"
  [[ -n "$custom_url" ]] && echo -e "  Custom domain : ${GREEN}$custom_url${NC}"
  echo -e "  ECS cluster   : $cluster"
  echo -e "  Backend svc   : $svc"
  echo ""

  info "Set VITE_API_BASE_URL=$api_url in .env.production, then deploy the frontend:"
  info "  ./scripts/deploy-pages.sh"
  echo ""

  info "Useful commands:"
  echo "  # Tail backend logs"
  echo "  aws logs tail /ecs/${ENVIRONMENT}-backend --follow"
  echo ""
  echo "  # Force a new ECS deployment (e.g. after pushing a new image)"
  echo "  aws ecs update-service --cluster $cluster --service $svc --force-new-deployment"
  echo ""
  echo "  # Run database migrations"
  echo "  ./scripts/db-migrate.sh upgrade"
  echo ""
}

# ---- Main --------------------------------------------------------------------
main() {
  header "AWS Cost Dashboard — Backend Deployment"
  echo "  Environment : $ENVIRONMENT"
  echo "  Action      : $ACTION"
  echo ""

  validate_inputs
  check_prereqs

  case "$ACTION" in
    plan)
      tf_init
      tf_plan
      ;;
    apply)
      build_and_push_backend
      tf_init
      tf_apply
      show_info
      ;;
    destroy)
      tf_init
      tf_destroy
      ;;
  esac

  ok "Done."
}

main
