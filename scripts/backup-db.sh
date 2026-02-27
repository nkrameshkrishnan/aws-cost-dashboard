#!/bin/bash
# ============================================================================
# Database Backup Script
# ============================================================================
# This script creates backups of the PostgreSQL database
#
# Usage:
#   ./scripts/backup-db.sh [environment] [action]
#
# Actions:
#   create   - Create a new backup (default)
#   restore  - Restore from a backup
#   list     - List available backups
#   cleanup  - Remove old backups
#
# Examples:
#   ./scripts/backup-db.sh production create
#   ./scripts/backup-db.sh staging restore
#   ./scripts/backup-db.sh production list
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="${1:-production}"
ACTION="${2:-create}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# Create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        print_info "Created backup directory: $BACKUP_DIR"
    fi
}

# Get database connection info
get_db_info() {
    if [ "$ENVIRONMENT" == "local" ]; then
        # Local Docker Compose
        export PGHOST="localhost"
        export PGPORT="5432"
        export PGDATABASE="aws_cost_dashboard"
        export PGUSER="postgres"
        export PGPASSWORD="postgres"
    else
        # AWS RDS - get from Terraform outputs
        cd "$PROJECT_ROOT/infrastructure/terraform"

        local db_endpoint=$(terraform output -raw rds_endpoint 2>/dev/null)

        if [ -z "$db_endpoint" ]; then
            print_error "Unable to get database endpoint"
            exit 1
        fi

        export PGHOST=$(echo "$db_endpoint" | cut -d: -f1)
        export PGPORT=$(echo "$db_endpoint" | cut -d: -f2)
        export PGDATABASE="aws_cost_dashboard"

        # Get credentials from AWS Secrets Manager
        local secret_name="awscost-db-${ENVIRONMENT}"
        local secret=$(aws secretsmanager get-secret-value --secret-id "$secret_name" --query SecretString --output text)

        export PGUSER=$(echo "$secret" | jq -r '.username')
        export PGPASSWORD=$(echo "$secret" | jq -r '.password')
    fi

    print_info "Database: $PGDATABASE@$PGHOST:$PGPORT"
}

# Create backup
create_backup() {
    print_info "Creating database backup for $ENVIRONMENT..."

    create_backup_dir
    get_db_info

    local backup_file="$BACKUP_DIR/${ENVIRONMENT}_${TIMESTAMP}.sql.gz"

    # Create backup
    pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
        --no-owner --no-acl | gzip > "$backup_file"

    local size=$(du -h "$backup_file" | cut -f1)
    print_success "Backup created: $backup_file ($size)"

    # Upload to S3 (if configured)
    if command -v aws &> /dev/null && [ -n "$BACKUP_S3_BUCKET" ]; then
        print_info "Uploading backup to S3..."
        aws s3 cp "$backup_file" "s3://$BACKUP_S3_BUCKET/database-backups/"
        print_success "Backup uploaded to S3"
    fi
}

# Restore from backup
restore_backup() {
    print_warning "Restoring database from backup for $ENVIRONMENT..."

    get_db_info

    # List available backups
    echo "Available backups:"
    ls -lh "$BACKUP_DIR/${ENVIRONMENT}_"*.sql.gz 2>/dev/null || {
        print_error "No backups found"
        exit 1
    }

    echo
    read -p "Enter backup filename (or path): " backup_file

    if [ ! -f "$backup_file" ]; then
        backup_file="$BACKUP_DIR/$backup_file"
    fi

    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi

    print_warning "This will OVERWRITE the current database!"
    read -p "Type 'restore-$ENVIRONMENT' to confirm: " confirm

    if [ "$confirm" != "restore-$ENVIRONMENT" ]; then
        print_error "Restore cancelled"
        exit 1
    fi

    # Restore backup
    gunzip -c "$backup_file" | psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE"

    print_success "Database restored from: $backup_file"
}

# List backups
list_backups() {
    print_info "Available backups for $ENVIRONMENT:"

    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backups found"
        return
    fi

    ls -lh "$BACKUP_DIR/${ENVIRONMENT}_"*.sql.gz 2>/dev/null || {
        print_warning "No backups found for $ENVIRONMENT"
    }

    # List S3 backups (if configured)
    if command -v aws &> /dev/null && [ -n "$BACKUP_S3_BUCKET" ]; then
        echo
        print_info "S3 backups:"
        aws s3 ls "s3://$BACKUP_S3_BUCKET/database-backups/${ENVIRONMENT}_" 2>/dev/null || {
            print_warning "No S3 backups found"
        }
    fi
}

# Cleanup old backups
cleanup_backups() {
    print_info "Cleaning up old backups for $ENVIRONMENT..."

    local days_to_keep=${1:-30}

    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backups to clean up"
        return
    fi

    print_info "Removing backups older than $days_to_keep days..."

    find "$BACKUP_DIR" -name "${ENVIRONMENT}_*.sql.gz" -type f -mtime +$days_to_keep -delete

    print_success "Cleanup complete"
}

# Main execution
main() {
    echo "=========================================="
    echo "AWS Cost Dashboard - Database Backup"
    echo "=========================================="
    echo "Environment: $ENVIRONMENT"
    echo "Action: $ACTION"
    echo

    # Check prerequisites
    if ! command -v pg_dump &> /dev/null; then
        print_error "pg_dump is not installed"
        print_info "Install PostgreSQL client tools"
        exit 1
    fi

    case "$ACTION" in
        create)
            create_backup
            ;;

        restore)
            restore_backup
            ;;

        list)
            list_backups
            ;;

        cleanup)
            cleanup_backups
            ;;

        *)
            print_error "Unknown action: $ACTION"
            echo "Valid actions: create, restore, list, cleanup"
            exit 1
            ;;
    esac
}

main
