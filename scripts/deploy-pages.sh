#!/usr/bin/env bash
# =============================================================================
# deploy-pages.sh — Build and deploy the frontend to GitHub Pages
#
# Usage:
#   ./scripts/deploy-pages.sh [--dry-run]
#
# Prerequisites:
#   - Node.js installed
#   - VITE_API_BASE_URL set in .env.production (get from `terraform output api_gateway_url`)
#   - Git remote "origin" pointing to your GitHub repository
#   - GitHub Pages configured to serve from the gh-pages branch
#
# What it does:
#   1. Loads VITE_* variables from .env.production
#   2. Runs `npm run build` (bakes env vars into the static bundle)
#   3. Pushes the dist/ folder to the gh-pages branch
#
# First-time GitHub Pages setup:
#   1. Push once with this script so the gh-pages branch exists
#   2. In your GitHub repo: Settings → Pages → Branch: gh-pages / (root)
#   3. Your site will be at: https://YOUR-USERNAME.github.io/REPO-NAME/
#      Set this URL as cors_allowed_origins in terraform.tfvars, then re-apply.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env.production"
FRONTEND_DIR="$ROOT_DIR/frontend"
DRY_RUN="${1:-}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
err()  { echo -e "${RED}✗ $1${NC}"; exit 1; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
info() { echo -e "${BLUE}ℹ $1${NC}"; }

# ---- Prerequisites -----------------------------------------------------------
check_prereqs() {
  command -v node  &>/dev/null || err "Node.js is not installed"
  command -v npm   &>/dev/null || err "npm is not installed"
  command -v git   &>/dev/null || err "git is not installed"
  ok "Prerequisites met (node $(node --version), npm $(npm --version))"
}

# ---- Load .env.production ----------------------------------------------------
load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    err "$ENV_FILE not found. Copy .env.example to .env.production and fill in VITE_API_BASE_URL."
  fi

  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^#' "$ENV_FILE" | grep -v '^$')
  set +a

  if [[ -z "${VITE_API_BASE_URL:-}" ]]; then
    err "VITE_API_BASE_URL is not set in $ENV_FILE"
  fi

  ok "Loaded .env.production"
  info "API base URL : $VITE_API_BASE_URL"
}

# ---- Build -------------------------------------------------------------------
build_frontend() {
  echo ""
  info "Installing dependencies ..."
  cd "$FRONTEND_DIR"
  npm install --silent

  info "Building static bundle ..."
  VITE_API_BASE_URL="$VITE_API_BASE_URL" \
  VITE_API_VERSION="${VITE_API_VERSION:-v1}" \
  VITE_APP_NAME="${VITE_APP_NAME:-AWS Cost Dashboard}" \
  VITE_APP_VERSION="${VITE_APP_VERSION:-${VERSION:-dev}}" \
    npm run build

  ok "Build complete — output in frontend/dist/"
}

# ---- Deploy to gh-pages branch -----------------------------------------------
deploy_to_pages() {
  echo ""
  cd "$FRONTEND_DIR"

  local dist_dir="$FRONTEND_DIR/dist"

  if [[ ! -d "$dist_dir" ]]; then
    err "dist/ directory not found. Run build step first."
  fi

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    warn "Dry run — skipping git push"
    info "Would push $dist_dir to gh-pages branch"
    return 0
  fi

  # Use git worktree so we don't need to switch branches
  local worktree_dir; worktree_dir=$(mktemp -d)
  trap 'rm -rf "$worktree_dir"' EXIT

  local repo_root; repo_root=$(git -C "$ROOT_DIR" rev-parse --show-toplevel)

  info "Deploying to gh-pages branch ..."

  # Ensure gh-pages branch exists
  if ! git -C "$repo_root" ls-remote --exit-code --heads origin gh-pages &>/dev/null; then
    info "Creating gh-pages branch for the first time ..."
    git -C "$repo_root" checkout --orphan gh-pages 2>/dev/null || true
    git -C "$repo_root" reset --hard 2>/dev/null || true
    git -C "$repo_root" checkout - 2>/dev/null || true
  fi

  # Add worktree for gh-pages
  git -C "$repo_root" worktree add "$worktree_dir" gh-pages 2>/dev/null || \
    git -C "$repo_root" worktree add --detach "$worktree_dir" origin/gh-pages

  # Clear old content and copy dist/
  find "$worktree_dir" -mindepth 1 -not -path '*/.git*' -delete 2>/dev/null || true
  cp -r "$dist_dir"/. "$worktree_dir/"

  # GitHub Pages uses .nojekyll to serve files starting with _
  touch "$worktree_dir/.nojekyll"

  # Commit and push
  cd "$worktree_dir"
  git add -A
  if git diff --cached --quiet; then
    warn "Nothing to deploy — gh-pages is already up to date"
  else
    local commit_msg="Deploy frontend $(date '+%Y-%m-%d %H:%M:%S')"
    [[ -n "${VERSION:-}" ]] && commit_msg="Deploy frontend v$VERSION ($(date '+%Y-%m-%d'))"
    git commit -m "$commit_msg"
    git push origin gh-pages
    ok "Deployed to gh-pages"
  fi

  cd "$ROOT_DIR"
}

# ---- Show post-deploy info ---------------------------------------------------
show_info() {
  echo ""
  # Try to figure out the GitHub Pages URL from the git remote
  local remote_url; remote_url=$(git -C "$ROOT_DIR" remote get-url origin 2>/dev/null || echo "")
  local pages_url=""

  # Parse GitHub SSH or HTTPS remote
  if [[ "$remote_url" =~ github\.com[:/]([^/]+)/([^/.]+) ]]; then
    local gh_user="${BASH_REMATCH[1]}"
    local gh_repo="${BASH_REMATCH[2]}"
    pages_url="https://${gh_user}.github.io/${gh_repo}"
  fi

  if [[ -n "$pages_url" ]]; then
    ok "Frontend live at: $pages_url"
    echo ""
    info "If this is a first deploy, make sure GitHub Pages is enabled:"
    info "  Repo → Settings → Pages → Branch: gh-pages / (root)"
    echo ""
    info "Ensure CORS allows your Pages origin — add to terraform.tfvars:"
    echo "    cors_allowed_origins = ["
    echo "      \"$pages_url\","
    echo "      \"http://localhost:5173\","
    echo "    ]"
    info "Then run: ./scripts/deploy.sh production apply"
  fi
}

# ---- Main --------------------------------------------------------------------
echo "==========================================="
echo " AWS Cost Dashboard — GitHub Pages Deploy"
echo "==========================================="
echo ""

check_prereqs
load_env
build_frontend
deploy_to_pages
show_info

ok "Done."
