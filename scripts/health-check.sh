#!/bin/bash
# ============================================================================
# Health Check Script
# ============================================================================
# This script checks the health of all application components
#
# Usage:
#   ./scripts/health-check.sh [environment] [url]
#
# Examples:
#   ./scripts/health-check.sh local http://localhost:8000
#   ./scripts/health-check.sh production https://cost-dashboard.example.com
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${1:-local}"
BASE_URL="${2:-http://localhost:8000}"

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if service is running
check_service() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}

    print_info "Checking $name..."

    local response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)

    if [ "$response" == "$expected_status" ]; then
        print_success "$name is healthy (HTTP $response)"
        return 0
    else
        print_error "$name is unhealthy (HTTP $response)"
        return 1
    fi
}

# Check database connection
check_database() {
    print_info "Checking database connection..."

    local response=$(curl -s "$BASE_URL/api/v1/health/db" 2>/dev/null)
    local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "unknown")

    if [ "$status" == "healthy" ]; then
        print_success "Database connection is healthy"
        return 0
    else
        print_error "Database connection is unhealthy"
        echo "$response"
        return 1
    fi
}

# Check Redis connection
check_redis() {
    print_info "Checking Redis connection..."

    local response=$(curl -s "$BASE_URL/api/v1/health/cache" 2>/dev/null)
    local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "unknown")

    if [ "$status" == "healthy" ]; then
        print_success "Redis connection is healthy"
        return 0
    else
        print_error "Redis connection is unhealthy"
        echo "$response"
        return 1
    fi
}

# Check AWS credentials
check_aws() {
    print_info "Checking AWS connectivity..."

    local response=$(curl -s "$BASE_URL/api/v1/health/aws" 2>/dev/null)
    local status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "unknown")

    if [ "$status" == "healthy" ]; then
        print_success "AWS connectivity is healthy"
        return 0
    else
        print_warning "AWS connectivity check returned: $status"
        return 0  # Not critical
    fi
}

# Get system metrics
get_metrics() {
    print_info "Retrieving system metrics..."

    local response=$(curl -s "$BASE_URL/api/v1/performance/stats" 2>/dev/null)

    if [ -n "$response" ]; then
        echo "$response" | jq . || echo "$response"
    else
        print_warning "Unable to retrieve metrics"
    fi
}

# Check ECS service (if running on AWS)
check_ecs_service() {
    if [ "$ENVIRONMENT" == "local" ]; then
        return 0
    fi

    print_info "Checking ECS service status..."

    # Get cluster and service names from Terraform outputs
    local cluster_name=$(cd ../infrastructure/terraform && terraform output -raw ecs_cluster_name 2>/dev/null)
    local service_name=$(cd ../infrastructure/terraform && terraform output -raw ecs_service_name 2>/dev/null)

    if [ -z "$cluster_name" ] || [ -z "$service_name" ]; then
        print_warning "ECS information not available"
        return 0
    fi

    local service_info=$(aws ecs describe-services \
        --cluster "$cluster_name" \
        --services "$service_name" \
        --query 'services[0]' \
        2>/dev/null)

    local running_count=$(echo "$service_info" | jq -r '.runningCount')
    local desired_count=$(echo "$service_info" | jq -r '.desiredCount')
    local status=$(echo "$service_info" | jq -r '.status')

    echo "  Status: $status"
    echo "  Running tasks: $running_count / $desired_count"

    if [ "$running_count" == "$desired_count" ] && [ "$status" == "ACTIVE" ]; then
        print_success "ECS service is healthy"
        return 0
    else
        print_warning "ECS service may have issues"
        return 1
    fi
}

# Main health check
main() {
    echo "=========================================="
    echo "AWS Cost Dashboard - Health Check"
    echo "=========================================="
    echo "Environment: $ENVIRONMENT"
    echo "Base URL: $BASE_URL"
    echo

    local total_checks=0
    local failed_checks=0

    # Backend health
    total_checks=$((total_checks + 1))
    check_service "Backend API" "$BASE_URL/health" || failed_checks=$((failed_checks + 1))

    # Database
    total_checks=$((total_checks + 1))
    check_database || failed_checks=$((failed_checks + 1))

    # Redis
    total_checks=$((total_checks + 1))
    check_redis || failed_checks=$((failed_checks + 1))

    # AWS
    total_checks=$((total_checks + 1))
    check_aws || true  # Don't count as failure

    # ECS (if applicable)
    if [ "$ENVIRONMENT" != "local" ]; then
        total_checks=$((total_checks + 1))
        check_ecs_service || failed_checks=$((failed_checks + 1))
    fi

    echo
    echo "=========================================="
    echo "System Metrics"
    echo "=========================================="
    get_metrics

    echo
    echo "=========================================="
    echo "Health Check Summary"
    echo "=========================================="
    echo "Total checks: $total_checks"
    echo "Failed checks: $failed_checks"
    echo "Success rate: $(( (total_checks - failed_checks) * 100 / total_checks ))%"
    echo

    if [ $failed_checks -eq 0 ]; then
        print_success "All health checks passed!"
        exit 0
    else
        print_error "$failed_checks health check(s) failed"
        exit 1
    fi
}

main
