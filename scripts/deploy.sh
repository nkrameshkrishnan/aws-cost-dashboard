#!/bin/bash
# ============================================================================
# AWS Cost Dashboard - Deployment Script
# ============================================================================
# This script automates the deployment process for the AWS Cost Dashboard
#
# Usage:
#   ./scripts/deploy.sh [environment] [action]
#
# Arguments:
#   environment: dev, staging, or production (default: dev)
#   action: plan, apply, or destroy (default: plan)
#
# Examples:
#   ./scripts/deploy.sh dev plan
#   ./scripts/deploy.sh production apply
#   ./scripts/deploy.sh staging destroy
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-dev}"
ACTION="${2:-plan}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"

# Functions
print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
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

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Validate environment
validate_environment() {
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
        print_error "Invalid environment: $ENVIRONMENT"
        echo "Valid environments: dev, staging, production"
        exit 1
    fi
}

# Validate action
validate_action() {
    if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
        print_error "Invalid action: $ACTION"
        echo "Valid actions: plan, apply, destroy"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check for required tools
    local tools=("terraform" "aws" "docker" "jq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            print_error "$tool is not installed"
            exit 1
        else
            print_success "$tool is installed"
        fi
    done

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured"
        exit 1
    else
        local account_id=$(aws sts get-caller-identity --query Account --output text)
        local user_arn=$(aws sts get-caller-identity --query Arn --output text)
        print_success "AWS credentials configured"
        print_info "Account ID: $account_id"
        print_info "User: $user_arn"
    fi

    # Check Terraform directory
    if [ ! -d "$TERRAFORM_DIR" ]; then
        print_error "Terraform directory not found: $TERRAFORM_DIR"
        exit 1
    fi

    print_success "All prerequisites met"
    echo
}

# Build Docker images
build_images() {
    print_header "Building Docker Images"

    cd "$PROJECT_ROOT"

    # Build backend
    print_info "Building backend image..."
    docker build -f backend/Dockerfile.prod -t awscost-backend:${ENVIRONMENT} backend/
    print_success "Backend image built"

    # Build frontend
    print_info "Building frontend image..."
    docker build -f frontend/Dockerfile.prod -t awscost-frontend:${ENVIRONMENT} frontend/
    print_success "Frontend image built"

    echo
}

# Push Docker images (optional)
push_images() {
    print_header "Pushing Docker Images"

    # Check if registry is configured in terraform.tfvars
    if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
        print_warning "terraform.tfvars not found, skipping image push"
        return
    fi

    local backend_image=$(grep "backend_image" "$TERRAFORM_DIR/terraform.tfvars" | cut -d'=' -f2 | tr -d ' "')
    local frontend_image=$(grep "frontend_image" "$TERRAFORM_DIR/terraform.tfvars" | cut -d'=' -f2 | tr -d ' "')

    if [ -z "$backend_image" ] || [ -z "$frontend_image" ]; then
        print_warning "Image registry not configured, skipping image push"
        return
    fi

    # Tag and push backend
    print_info "Pushing backend image to $backend_image..."
    docker tag awscost-backend:${ENVIRONMENT} "$backend_image"
    docker push "$backend_image"
    print_success "Backend image pushed"

    # Tag and push frontend
    print_info "Pushing frontend image to $frontend_image..."
    docker tag awscost-frontend:${ENVIRONMENT} "$frontend_image"
    docker push "$frontend_image"
    print_success "Frontend image pushed"

    echo
}

# Initialize Terraform
init_terraform() {
    print_header "Initializing Terraform"

    cd "$TERRAFORM_DIR"

    if [ ! -f "terraform.tfvars" ]; then
        print_error "terraform.tfvars not found"
        print_info "Copy terraform.tfvars.example to terraform.tfvars and fill in values"
        exit 1
    fi

    terraform init
    print_success "Terraform initialized"
    echo
}

# Run Terraform plan
terraform_plan() {
    print_header "Running Terraform Plan"

    cd "$TERRAFORM_DIR"

    terraform plan \
        -var="environment=$ENVIRONMENT" \
        -out="tfplan-${ENVIRONMENT}.out"

    print_success "Terraform plan complete"
    print_info "Plan saved to tfplan-${ENVIRONMENT}.out"
    echo
}

# Run Terraform apply
terraform_apply() {
    print_header "Applying Terraform Changes"

    cd "$TERRAFORM_DIR"

    # Check if plan file exists
    if [ ! -f "tfplan-${ENVIRONMENT}.out" ]; then
        print_warning "No plan file found, running plan first..."
        terraform_plan
    fi

    # Confirmation for production
    if [ "$ENVIRONMENT" == "production" ]; then
        print_warning "You are about to deploy to PRODUCTION"
        read -p "Type 'yes' to confirm: " confirm
        if [ "$confirm" != "yes" ]; then
            print_error "Deployment cancelled"
            exit 1
        fi
    fi

    terraform apply "tfplan-${ENVIRONMENT}.out"

    print_success "Terraform apply complete"

    # Clean up plan file
    rm -f "tfplan-${ENVIRONMENT}.out"

    echo
}

# Run Terraform destroy
terraform_destroy() {
    print_header "Destroying Infrastructure"

    cd "$TERRAFORM_DIR"

    # Confirmation
    print_warning "You are about to DESTROY all infrastructure in $ENVIRONMENT"
    read -p "Type 'destroy-$ENVIRONMENT' to confirm: " confirm
    if [ "$confirm" != "destroy-$ENVIRONMENT" ]; then
        print_error "Destruction cancelled"
        exit 1
    fi

    terraform destroy -var="environment=$ENVIRONMENT" -auto-approve

    print_success "Infrastructure destroyed"
    echo
}

# Display deployment information
show_info() {
    print_header "Deployment Information"

    cd "$TERRAFORM_DIR"

    # Get outputs
    local alb_dns=$(terraform output -raw alb_dns_name 2>/dev/null || echo "N/A")
    local cluster=$(terraform output -raw ecs_cluster_name 2>/dev/null || echo "N/A")
    local service=$(terraform output -raw ecs_service_name 2>/dev/null || echo "N/A")

    echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
    echo -e "${GREEN}ALB URL:${NC} http://$alb_dns"
    echo -e "${GREEN}ECS Cluster:${NC} $cluster"
    echo -e "${GREEN}ECS Service:${NC} $service"
    echo

    print_info "Access your application at: http://$alb_dns"
    print_info "API docs at: http://$alb_dns/api/v1/docs"
    echo
}

# Main execution
main() {
    print_header "AWS Cost Dashboard Deployment"
    echo "Environment: $ENVIRONMENT"
    echo "Action: $ACTION"
    echo

    validate_environment
    validate_action
    check_prerequisites

    case "$ACTION" in
        plan)
            init_terraform
            terraform_plan
            ;;
        apply)
            build_images
            push_images
            init_terraform
            terraform_apply
            show_info
            ;;
        destroy)
            init_terraform
            terraform_destroy
            ;;
    esac

    print_success "Deployment script completed successfully!"
}

# Run main function
main
