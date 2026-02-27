#!/bin/bash
# ============================================================================
# Secrets Management Script
# ============================================================================
# This script helps manage secrets in AWS Secrets Manager
#
# Usage:
#   ./scripts/manage-secrets.sh [command] [environment]
#
# Commands:
#   generate  - Generate new application keys
#   create    - Create secrets in AWS Secrets Manager
#   update    - Update secrets in AWS Secrets Manager
#   get       - Retrieve secrets from AWS Secrets Manager
#   rotate    - Rotate application keys
#
# Examples:
#   ./scripts/manage-secrets.sh generate
#   ./scripts/manage-secrets.sh create production
#   ./scripts/manage-secrets.sh get staging
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMMAND="${1:-generate}"
ENVIRONMENT="${2:-production}"

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

# Generate random keys
generate_keys() {
    print_info "Generating application keys..."

    # Generate SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    print_success "SECRET_KEY generated"

    # Generate JWT_SECRET_KEY
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    print_success "JWT_SECRET_KEY generated"

    # Generate ENCRYPTION_KEY (Fernet key)
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    print_success "ENCRYPTION_KEY generated"

    echo
    echo "========== Generated Keys =========="
    echo "SECRET_KEY=$SECRET_KEY"
    echo "JWT_SECRET_KEY=$JWT_SECRET_KEY"
    echo "ENCRYPTION_KEY=$ENCRYPTION_KEY"
    echo "===================================="
    echo
    print_warning "Save these keys securely!"
    print_warning "DO NOT commit these to version control!"
}

# Create secrets in AWS Secrets Manager
create_secrets() {
    print_info "Creating secrets in AWS Secrets Manager for $ENVIRONMENT..."

    local secret_name="awscost-app-keys-${ENVIRONMENT}"

    # Check if secret already exists
    if aws secretsmanager describe-secret --secret-id "$secret_name" &>/dev/null; then
        print_error "Secret already exists: $secret_name"
        print_info "Use 'update' command to update existing secret"
        exit 1
    fi

    # Generate keys
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Create secret
    aws secretsmanager create-secret \
        --name "$secret_name" \
        --description "Application keys for AWS Cost Dashboard ${ENVIRONMENT}" \
        --secret-string "{
            \"SECRET_KEY\": \"$SECRET_KEY\",
            \"JWT_SECRET_KEY\": \"$JWT_SECRET_KEY\",
            \"ENCRYPTION_KEY\": \"$ENCRYPTION_KEY\"
        }" \
        --tags "Key=Environment,Value=$ENVIRONMENT" "Key=Project,Value=AWS-Cost-Dashboard"

    print_success "Secret created: $secret_name"
    print_info "Keys have been stored in AWS Secrets Manager"
}

# Update secrets
update_secrets() {
    print_info "Updating secrets in AWS Secrets Manager for $ENVIRONMENT..."

    local secret_name="awscost-app-keys-${ENVIRONMENT}"

    # Check if secret exists
    if ! aws secretsmanager describe-secret --secret-id "$secret_name" &>/dev/null; then
        print_error "Secret not found: $secret_name"
        print_info "Use 'create' command to create new secret"
        exit 1
    fi

    # Get current secret
    print_info "Current secret value:"
    aws secretsmanager get-secret-value --secret-id "$secret_name" --query SecretString --output text | jq .

    echo
    read -p "Generate new keys? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        print_warning "Update cancelled"
        exit 0
    fi

    # Generate new keys
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Update secret
    aws secretsmanager update-secret \
        --secret-id "$secret_name" \
        --secret-string "{
            \"SECRET_KEY\": \"$SECRET_KEY\",
            \"JWT_SECRET_KEY\": \"$JWT_SECRET_KEY\",
            \"ENCRYPTION_KEY\": \"$ENCRYPTION_KEY\"
        }"

    print_success "Secret updated: $secret_name"
    print_warning "You may need to restart the application for changes to take effect"
}

# Get secrets
get_secrets() {
    print_info "Retrieving secrets from AWS Secrets Manager for $ENVIRONMENT..."

    local secret_name="awscost-app-keys-${ENVIRONMENT}"

    # Get secret
    aws secretsmanager get-secret-value --secret-id "$secret_name" --query SecretString --output text | jq .

    print_success "Secret retrieved: $secret_name"
}

# Rotate keys
rotate_keys() {
    print_warning "Rotating application keys for $ENVIRONMENT..."
    print_warning "This will invalidate all existing user sessions!"
    echo

    read -p "Are you sure? Type 'rotate-$ENVIRONMENT' to confirm: " confirm
    if [ "$confirm" != "rotate-$ENVIRONMENT" ]; then
        print_error "Rotation cancelled"
        exit 1
    fi

    update_secrets
}

# Check prerequisites
check_prerequisites() {
    # Check for AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi

    # Check for jq
    if ! command -v jq &> /dev/null; then
        print_error "jq is not installed"
        exit 1
    fi

    # Check for Python3
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed"
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured"
        exit 1
    fi
}

# Main execution
main() {
    echo "AWS Cost Dashboard - Secrets Management"
    echo "========================================"
    echo

    case "$COMMAND" in
        generate)
            generate_keys
            ;;

        create)
            check_prerequisites
            create_secrets
            ;;

        update)
            check_prerequisites
            update_secrets
            ;;

        get)
            check_prerequisites
            get_secrets
            ;;

        rotate)
            check_prerequisites
            rotate_keys
            ;;

        *)
            print_error "Unknown command: $COMMAND"
            echo "Valid commands: generate, create, update, get, rotate"
            exit 1
            ;;
    esac
}

main
