#!/usr/bin/env bash
# =============================================================================
# health-check.sh — Check the health of all application components
#
# Usage:
#   ./scripts/health-check.sh [environment] [api-url]
#
# Arguments:
#   environment : local | staging | production  (default: local)
#   api-url     : Base URL for the backend API  (default: http://localhost:8000)
#
# For cloud environments the API URL is the API Gateway invoke URL.
# Retrieve it with:   cd infrastructure/terraform && terraform output api_gateway_url
#
# Examples:
#   ./scripts/health-check.sh local http://localhost:8000
#   ./scripts/health-check.sh production https://abc123.execute-api.us-east-1.amazonaws.com/prod
# =============================================================================
set -euo pipefail

# ---- Colours -----------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

ENVIRONMENT="${1:-local}"
BASE_URL="${2:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")/infrastructure/terraform"

FAILED=0
TOTAL=0

info()    { echo -e "${BLUE}ℹ  $1${NC}"; }
ok()      { echo -e "${GREEN}✓  $1${NC}"; }
fail()    { echo -e "${RED}✗  $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $1${NC}"; }

# ---- Generic HTTP check ------------------------------------------------------
check_http() {
  local name="$1"
  local url="$2"
  local expected="${3:-200}"

  TOTAL=$((TOTAL + 1))
  info "Checking $name ..."

  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

  if [[ "$status" == "$expected" ]]; then
    ok "$name — HTTP $status"
  else
    fail "$name — HTTP $status (expected $expected)"
    FAILED=$((FAILED + 1))
  fi
}

# ---- Component health checks -------------------------------------------------
check_backend() {
  check_http "Backend /health" "$BASE_URL/health"
}

check_database() {
  TOTAL=$((TOTAL + 1))
  info "Checking database ..."

  local response; response=$(curl -s --max-time 10 "$BASE_URL/api/v1/health/db" 2>/dev/null || echo "{}")
  local status;   status=$(echo "$response" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

  if [[ "$status" == "healthy" ]]; then
    ok "Database — healthy"
  else
    fail "Database — $status"
    FAILED=$((FAILED + 1))
  fi
}

check_cache() {
  TOTAL=$((TOTAL + 1))
  info "Checking Redis cache ..."

  local response; response=$(curl -s --max-time 10 "$BASE_URL/api/v1/health/cache" 2>/dev/null || echo "{}")
  local status;   status=$(echo "$response" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

  if [[ "$status" == "healthy" ]]; then
    ok "Redis cache — healthy"
  else
    fail "Redis cache — $status"
    FAILED=$((FAILED + 1))
  fi
}

check_aws_connectivity() {
  # Not counted as a hard failure — AWS credentials may not always be
  # available from where health-check runs (e.g. CI).
  info "Checking AWS connectivity ..."

  local response; response=$(curl -s --max-time 10 "$BASE_URL/api/v1/health/aws" 2>/dev/null || echo "{}")
  local status;   status=$(echo "$response" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

  if [[ "$status" == "healthy" ]]; then
    ok "AWS connectivity — healthy"
  else
    warn "AWS connectivity — $status (non-critical)"
  fi
}

# ---- ECS backend service check -----------------------------------------------
check_ecs() {
  [[ "$ENVIRONMENT" == "local" ]] && return 0

  TOTAL=$((TOTAL + 1))
  info "Checking ECS backend service ..."

  if [[ ! -d "$TERRAFORM_DIR" ]]; then
    warn "Terraform directory not found — skipping ECS check"
    return 0
  fi

  local cluster; cluster=$(cd "$TERRAFORM_DIR" && terraform output -raw ecs_cluster_name    2>/dev/null || echo "")
  local svc;     svc=$(cd "$TERRAFORM_DIR" && terraform output -raw backend_service_name    2>/dev/null || echo "")

  if [[ -z "$cluster" ]] || [[ -z "$svc" ]]; then
    warn "ECS outputs not available (run terraform apply first)"
    TOTAL=$((TOTAL - 1))
    return 0
  fi

  local info_json
  info_json=$(aws ecs describe-services \
    --cluster "$cluster" \
    --services "$svc" \
    --query 'services[0]' \
    2>/dev/null || echo "{}")

  local running;  running=$(echo "$info_json"  | jq -r '.runningCount  // 0')
  local desired;  desired=$(echo "$info_json"  | jq -r '.desiredCount  // 0')
  local svc_status; svc_status=$(echo "$info_json" | jq -r '.status // "UNKNOWN"')

  echo "     Cluster : $cluster"
  echo "     Service : $svc"
  echo "     Status  : $svc_status  ($running/$desired tasks running)"

  if [[ "$running" == "$desired" ]] && [[ "$svc_status" == "ACTIVE" ]]; then
    ok "ECS backend service — healthy"
  else
    fail "ECS backend service — unhealthy"
    FAILED=$((FAILED + 1))
  fi
}

# ---- Performance metrics (informational) -------------------------------------
show_metrics() {
  echo ""
  echo "==========================================="
  echo " Performance Metrics (informational)"
  echo "==========================================="

  local response
  response=$(curl -s --max-time 10 "$BASE_URL/api/v1/performance/stats" 2>/dev/null || echo "")

  if [[ -n "$response" ]]; then
    echo "$response" | jq . 2>/dev/null || echo "$response"
  else
    warn "Metrics endpoint not available"
  fi
}

# ---- Main --------------------------------------------------------------------
main() {
  echo "==========================================="
  echo " AWS Cost Dashboard — Health Check"
  echo "==========================================="
  echo "  Environment : $ENVIRONMENT"
  echo "  API URL     : $BASE_URL"
  echo ""

  check_backend
  check_database
  check_cache
  check_aws_connectivity

  if [[ "$ENVIRONMENT" != "local" ]]; then
    check_ecs
  fi

  show_metrics

  echo ""
  echo "==========================================="
  echo " Summary"
  echo "==========================================="
  echo "  Total   : $TOTAL"
  echo "  Passed  : $((TOTAL - FAILED))"
  echo "  Failed  : $FAILED"
  echo ""

  if [[ $FAILED -eq 0 ]]; then
    ok "All checks passed"
    exit 0
  else
    fail "$FAILED check(s) failed"
    exit 1
  fi
}

main
