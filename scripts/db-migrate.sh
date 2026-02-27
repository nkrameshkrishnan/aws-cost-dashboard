#!/bin/bash
# ============================================================================
# Database Migration Script
# ============================================================================
# This script runs database migrations using Alembic
#
# Usage:
#   ./scripts/db-migrate.sh [command] [options]
#
# Commands:
#   upgrade    - Upgrade to latest migration (default)
#   downgrade  - Downgrade one migration
#   history    - Show migration history
#   current    - Show current migration version
#   init       - Initialize Alembic (first time only)
#
# Examples:
#   ./scripts/db-migrate.sh upgrade
#   ./scripts/db-migrate.sh downgrade
#   ./scripts/db-migrate.sh history
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMMAND="${1:-upgrade}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

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

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    print_error "Backend directory not found: $BACKEND_DIR"
    exit 1
fi

cd "$BACKEND_DIR"

# Check if running in Docker or local
if [ -f "/.dockerenv" ]; then
    PYTHON_CMD="python"
else
    # Check if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
    PYTHON_CMD="python"
fi

# Check if alembic is installed
if ! $PYTHON_CMD -c "import alembic" 2>/dev/null; then
    print_error "Alembic is not installed"
    print_info "Install with: pip install alembic"
    exit 1
fi

# Execute migration command
case "$COMMAND" in
    upgrade)
        print_info "Upgrading database to latest version..."
        alembic upgrade head
        print_success "Database upgraded successfully"
        ;;

    downgrade)
        print_warning "Downgrading database by one version..."
        alembic downgrade -1
        print_success "Database downgraded successfully"
        ;;

    history)
        print_info "Migration history:"
        alembic history
        ;;

    current)
        print_info "Current migration version:"
        alembic current
        ;;

    init)
        print_info "Initializing Alembic..."
        alembic init alembic
        print_success "Alembic initialized"
        print_warning "Remember to configure alembic.ini and env.py"
        ;;

    create)
        if [ -z "$2" ]; then
            print_error "Migration message required"
            echo "Usage: $0 create \"migration message\""
            exit 1
        fi
        print_info "Creating new migration: $2"
        alembic revision --autogenerate -m "$2"
        print_success "Migration created"
        ;;

    *)
        print_error "Unknown command: $COMMAND"
        echo "Valid commands: upgrade, downgrade, history, current, init, create"
        exit 1
        ;;
esac
