#!/bin/bash
# =============================================================================
# setup-testing.sh — Set up the test environment
#
# Usage:
#   ./scripts/setup-testing.sh [backend|frontend|all]
#
# Tests live in /tests/ (project root), separate from the application code.
# =============================================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
COMPONENT="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

info()    { echo -e "${BLUE}ℹ  $1${NC}"; }
success() { echo -e "${GREEN}✓  $1${NC}"; }
error()   { echo -e "${RED}✗  $1${NC}"; exit 1; }
header()  { echo; echo "=========================================="; echo "$1"; echo "=========================================="; }

# =============================================================================
# Backend test setup
# =============================================================================
setup_backend() {
    header "Setting Up Backend Tests"

    command -v python3 >/dev/null 2>&1 || error "Python 3 is not installed"
    success "Python 3: $(python3 --version)"

    # Create venv inside the tests/ project (keeps it separate from backend)
    VENV_DIR="$PROJECT_ROOT/tests/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        info "Creating virtual environment at tests/.venv ..."
        python3 -m venv "$VENV_DIR"
        success "Virtual environment created"
    else
        info "Virtual environment already exists"
    fi

    source "$VENV_DIR/bin/activate"

    info "Installing backend + test dependencies..."
    pip install -q -r "$PROJECT_ROOT/backend/requirements.txt"
    pip install -q -r "$PROJECT_ROOT/tests/requirements-test.txt"
    success "Dependencies installed"

    success "Backend test setup complete!"
    info "Run tests with:"
    echo "    cd tests && source .venv/bin/activate && python -m pytest"
    echo "    # or skip the slow AWS-calling suite:"
    echo "    cd tests && python -m pytest -m 'not slow and not aws'"
}

# =============================================================================
# Frontend test setup
# =============================================================================
setup_frontend() {
    header "Setting Up Frontend Tests"

    command -v node >/dev/null 2>&1 || error "Node.js is not installed"
    success "Node.js: $(node --version)"

    cd "$PROJECT_ROOT/frontend"

    info "Installing frontend dependencies..."
    npm install --silent
    success "Dependencies installed"

    success "Frontend test setup complete!"
    info "Run tests with:"
    echo "    cd frontend && npm test"
    echo "    cd frontend && npm run test:coverage"
}

# =============================================================================
# Main
# =============================================================================
header "AWS Cost Dashboard — Test Environment Setup"
info "Component: $COMPONENT"

case "$COMPONENT" in
    backend)  setup_backend ;;
    frontend) setup_frontend ;;
    all)      setup_backend; setup_frontend ;;
    *)        error "Unknown component: $COMPONENT. Use: backend | frontend | all" ;;
esac

header "Setup Complete"
success "Test environment is ready."
echo
info "Reference:"
echo "  Tests project : tests/"
echo "  pytest config : tests/pytest.ini"
echo "  Test deps     : tests/requirements-test.txt"
echo "  Docker (CI)   : docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit"
