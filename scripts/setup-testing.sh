#!/bin/bash
# ============================================================================
# Testing Setup Script
# ============================================================================
# Sets up the testing environment for backend and frontend
#
# Usage:
#   ./scripts/setup-testing.sh [backend|frontend|all]
#
# Examples:
#   ./scripts/setup-testing.sh all       # Set up both
#   ./scripts/setup-testing.sh backend   # Backend only
#   ./scripts/setup-testing.sh frontend  # Frontend only
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMPONENT="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

print_header() {
    echo
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Setup backend testing
setup_backend() {
    print_header "Setting Up Backend Testing"

    cd "$PROJECT_ROOT/backend"

    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_info "Virtual environment already exists"
    fi

    # Activate virtual environment
    print_info "Activating virtual environment..."
    source venv/bin/activate

    # Install testing dependencies
    print_info "Installing testing dependencies..."

    # Create requirements-test.txt if it doesn't exist
    if [ ! -f "requirements-test.txt" ]; then
        print_info "Creating requirements-test.txt..."
        cat > requirements-test.txt <<EOF
# Testing dependencies
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2
moto[all]==4.2.9
fakeredis==2.20.1
factory-boy==3.3.0
faker==20.1.0
EOF
        print_success "Created requirements-test.txt"
    fi

    pip install -q -r requirements.txt
    pip install -q -r requirements-test.txt
    print_success "Testing dependencies installed"

    # Create pytest.ini if it doesn't exist
    if [ ! -f "pytest.ini" ]; then
        print_info "Creating pytest.ini..."
        cat > pytest.ini <<EOF
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts =
    --verbose
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    aws: Tests requiring AWS credentials
EOF
        print_success "Created pytest.ini"
    fi

    # Create conftest.py if it doesn't exist
    if [ ! -f "tests/conftest.py" ]; then
        print_info "Creating tests/conftest.py..."
        cat > tests/conftest.py <<'EOF'
"""
Global test configuration and fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import fakeredis

from app.main import app
from app.database.base import Base


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db_session(test_db_engine):
    """Create database session for each test."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def redis_client():
    """Create fake Redis client."""
    return fakeredis.FakeRedis()


@pytest.fixture(scope="function")
def client(db_session, redis_client):
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def aws_credentials(monkeypatch):
    """Mock AWS credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
EOF
        print_success "Created tests/conftest.py"
    fi

    # Create sample test file if tests are empty
    if [ ! -f "tests/test_api/test_health.py" ]; then
        print_info "Creating sample test file..."
        mkdir -p tests/test_api
        cat > tests/test_api/test_health.py <<'EOF'
"""
Tests for health check endpoints.
"""
import pytest


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
EOF
        print_success "Created sample test file"
    fi

    print_success "Backend testing setup complete!"
    print_info "Run tests with: cd backend && pytest"
}

# Setup frontend testing
setup_frontend() {
    print_header "Setting Up Frontend Testing"

    cd "$PROJECT_ROOT/frontend"

    # Check Node.js
    if ! command_exists node; then
        print_error "Node.js is not installed"
        exit 1
    fi
    print_success "Node.js found: $(node --version)"

    # Check npm
    if ! command_exists npm; then
        print_error "npm is not installed"
        exit 1
    fi
    print_success "npm found: $(npm --version)"

    # Install testing dependencies
    print_info "Installing testing dependencies..."
    npm install --silent --save-dev \
        vitest \
        @vitest/ui \
        @testing-library/react \
        @testing-library/jest-dom \
        @testing-library/user-event \
        jsdom \
        msw \
        @playwright/test

    print_success "Testing dependencies installed"

    # Create vitest.config.ts if it doesn't exist
    if [ ! -f "vitest.config.ts" ]; then
        print_info "Creating vitest.config.ts..."
        cat > vitest.config.ts <<'EOF'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mockData',
        'src/main.tsx',
      ],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 70,
        statements: 70,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
EOF
        print_success "Created vitest.config.ts"
    fi

    # Create test setup file
    if [ ! -f "src/test/setup.ts" ]; then
        print_info "Creating test setup file..."
        mkdir -p src/test
        cat > src/test/setup.ts <<'EOF'
import { expect, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers)

afterEach(() => {
  cleanup()
})
EOF
        print_success "Created src/test/setup.ts"
    fi

    # Update package.json scripts
    print_info "Updating package.json scripts..."

    # Add test scripts to package.json if they don't exist
    node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
pkg.scripts = pkg.scripts || {};
pkg.scripts['test'] = 'vitest';
pkg.scripts['test:ui'] = 'vitest --ui';
pkg.scripts['test:coverage'] = 'vitest --coverage';
pkg.scripts['test:watch'] = 'vitest --watch';
pkg.scripts['test:e2e'] = 'playwright test';
pkg.scripts['test:e2e:ui'] = 'playwright test --ui';
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"
    print_success "Updated package.json scripts"

    # Create Playwright config
    if [ ! -f "playwright.config.ts" ]; then
        print_info "Creating playwright.config.ts..."
        cat > playwright.config.ts <<'EOF'
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
})
EOF
        print_success "Created playwright.config.ts"
    fi

    # Install Playwright browsers
    print_info "Installing Playwright browsers..."
    npx playwright install chromium --with-deps
    print_success "Playwright browsers installed"

    print_success "Frontend testing setup complete!"
    print_info "Run tests with:"
    print_info "  npm test          - Run unit tests"
    print_info "  npm run test:ui   - Run with UI"
    print_info "  npm run test:e2e  - Run E2E tests"
}

# Main execution
main() {
    print_header "AWS Cost Dashboard - Testing Setup"
    print_info "Component: $COMPONENT"

    case "$COMPONENT" in
        backend)
            setup_backend
            ;;
        frontend)
            setup_frontend
            ;;
        all)
            setup_backend
            echo
            setup_frontend
            ;;
        *)
            print_error "Invalid component: $COMPONENT"
            echo "Usage: $0 [backend|frontend|all]"
            exit 1
            ;;
    esac

    print_header "Setup Complete!"
    print_success "Testing environment is ready"
    echo
    print_info "Next steps:"

    if [ "$COMPONENT" = "backend" ] || [ "$COMPONENT" = "all" ]; then
        echo "  Backend:"
        echo "    cd backend"
        echo "    source venv/bin/activate"
        echo "    pytest"
    fi

    if [ "$COMPONENT" = "frontend" ] || [ "$COMPONENT" = "all" ]; then
        echo "  Frontend:"
        echo "    cd frontend"
        echo "    npm test"
    fi
    echo
    print_info "For detailed testing plan, see: PHASE8_TESTING_PLAN.md"
}

main
