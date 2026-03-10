#!/usr/bin/env bash
# =============================================================================
# localstack-setup.sh — Deploy API Gateway (REST / v1) in LocalStack Community
# =============================================================================
#
# Uses apigateway (v1 REST API) — included in the free LocalStack tier.
# apigatewayv2 (HTTP API) requires a paid license.
#
# Usage:
#   ./scripts/localstack-setup.sh [--reset]
#
#   --reset   Delete existing API and reprovision from scratch.
#
# Defaults (override via env vars):
#   LOCALSTACK_ENDPOINT   http://localhost.localstack.cloud:4566
#   AWS_DEFAULT_REGION    us-east-1
#   AWS_ACCESS_KEY_ID     test
#   AWS_SECRET_ACCESS_KEY test
#   BACKEND_URL           http://host.docker.internal:8000
#                         Use http://localhost:8000 if LocalStack is NOT in Docker.
# =============================================================================
set -euo pipefail

ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost.localstack.cloud:4566}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
AWS_KEY="${AWS_ACCESS_KEY_ID:-test}"
AWS_SECRET="${AWS_SECRET_ACCESS_KEY:-test}"
BACKEND_URL="${BACKEND_URL:-http://host.docker.internal:8000}"
API_NAME="aws-cost-dashboard-api"
STAGE_NAME="local"
RESET_MODE="${1:-}"

awsl() {
    AWS_ACCESS_KEY_ID="$AWS_KEY" \
    AWS_SECRET_ACCESS_KEY="$AWS_SECRET" \
    AWS_DEFAULT_REGION="$REGION" \
    aws --endpoint-url "$ENDPOINT" "$@"
}

echo "→ Checking LocalStack is up at $ENDPOINT ..."
until curl -sf "${ENDPOINT}/_localstack/health" | grep -q '"apigateway"' 2>/dev/null; do
    echo "  waiting..."; sleep 2
done
echo "  ready."

# ── Optional reset ────────────────────────────────────────────────────────────
if [[ "$RESET_MODE" == "--reset" ]]; then
    echo "→ Deleting existing APIs named '$API_NAME' ..."
    IDS=$(awsl apigateway get-rest-apis \
        --query "items[?name=='$API_NAME'].id" --output text 2>/dev/null || true)
    for id in $IDS; do
        awsl apigateway delete-rest-api --rest-api-id "$id"
        echo "  deleted $id"
    done
fi

# ── 1. Create REST API ────────────────────────────────────────────────────────
EXISTING_ID=$(awsl apigateway get-rest-apis \
    --query "items[?name=='$API_NAME'].id" --output text 2>/dev/null | awk '{print $1}')

if [[ -n "$EXISTING_ID" && "$EXISTING_ID" != "None" ]]; then
    echo "→ API '$API_NAME' already exists ($EXISTING_ID) — run with --reset to reprovision"
    API_ID="$EXISTING_ID"
else
    echo "→ Creating REST API ..."
    API_ID=$(awsl apigateway create-rest-api \
        --name "$API_NAME" \
        --description "AWS Cost Dashboard — local dev (LocalStack)" \
        --query 'id' --output text)
    echo "  created: $API_ID"
fi

# ── 2. Get root resource ID ───────────────────────────────────────────────────
ROOT_ID=$(awsl apigateway get-resources \
    --rest-api-id "$API_ID" \
    --query 'items[?path==`/`].id' --output text)
echo "→ Root resource: $ROOT_ID"

# ── 3. Create {proxy+} resource ───────────────────────────────────────────────
PROXY_ID=$(awsl apigateway get-resources \
    --rest-api-id "$API_ID" \
    --query "items[?pathPart=='{proxy+}'].id" --output text | awk '{print $1}')

if [[ -z "$PROXY_ID" || "$PROXY_ID" == "None" ]]; then
    echo "→ Creating {proxy+} resource ..."
    PROXY_ID=$(awsl apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$ROOT_ID" \
        --path-part '{proxy+}' \
        --query 'id' --output text)
    echo "  created: $PROXY_ID"
else
    echo "→ {proxy+} resource already exists: $PROXY_ID"
fi

# ── Helper: wire ANY (HTTP_PROXY) + OPTIONS (MOCK CORS) on a resource ─────────
setup_resource() {
    local resource_id="$1"
    local proxy_uri="$2"

    # ANY — proxy to backend
    awsl apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method ANY \
        --authorization-type NONE \
        --no-api-key-required 2>/dev/null || true

    awsl apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method ANY \
        --type HTTP_PROXY \
        --integration-http-method ANY \
        --uri "$proxy_uri" > /dev/null

    # OPTIONS — mock integration returning CORS preflight headers
    awsl apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method OPTIONS \
        --authorization-type NONE \
        --no-api-key-required 2>/dev/null || true

    awsl apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method OPTIONS \
        --type MOCK \
        --request-templates '{"application/json": "{\"statusCode\": 200}"}' > /dev/null

    # method.response — declare the headers the OPTIONS response will return
    awsl apigateway put-method-response \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{
            "method.response.header.Access-Control-Allow-Origin":  false,
            "method.response.header.Access-Control-Allow-Headers": false,
            "method.response.header.Access-Control-Allow-Methods": false
        }' 2>/dev/null || true

    # integration.response — static values for those headers
    # Note: API Gateway static values must be wrapped in single quotes INSIDE
    # the double-quoted JSON string, e.g. "'value'"
    awsl apigateway put-integration-response \
        --rest-api-id "$API_ID" \
        --resource-id "$resource_id" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{
            "method.response.header.Access-Control-Allow-Origin":  "'"'"'https://nkrameshkrishnan.github.io,http://localhost:5173,http://localhost:3000'"'"'",
            "method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,Authorization,X-Requested-With,Accept,Origin'"'"'",
            "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,PUT,DELETE,PATCH,OPTIONS'"'"'"
        }' \
        --response-templates '{"application/json": ""}' > /dev/null
}

# ── 4. Wire root / and {proxy+} ───────────────────────────────────────────────
echo "→ Setting up root / ..."
setup_resource "$ROOT_ID"  "${BACKEND_URL}/"

echo "→ Setting up /{proxy+} ..."
setup_resource "$PROXY_ID" "${BACKEND_URL}/{proxy}"

# ── 5. CORS headers on gateway-level error responses (4xx / 5xx) ──────────────
echo "→ Configuring CORS on gateway error responses ..."

for response_type in DEFAULT_4XX DEFAULT_5XX; do
    awsl apigateway put-gateway-response \
        --rest-api-id "$API_ID" \
        --response-type "$response_type" \
        --response-parameters '{
            "gatewayresponse.header.Access-Control-Allow-Origin":  "'"'"'https://nkrameshkrishnan.github.io,http://localhost:5173,http://localhost:3000'"'"'",
            "gatewayresponse.header.Access-Control-Allow-Headers": "'"'"'Content-Type,Authorization,X-Requested-With,Accept,Origin'"'"'",
            "gatewayresponse.header.Access-Control-Allow-Methods": "'"'"'GET,POST,PUT,DELETE,PATCH,OPTIONS'"'"'"
        }' > /dev/null
    echo "  $response_type"
done

# ── 6. Deploy to stage ────────────────────────────────────────────────────────
echo "→ Deploying to stage '$STAGE_NAME' ..."
awsl apigateway create-deployment \
    --rest-api-id "$API_ID" \
    --stage-name "$STAGE_NAME" \
    --description "Local dev deployment" > /dev/null
echo "  deployed."

# ── Summary ───────────────────────────────────────────────────────────────────
INVOKE_URL="http://localhost.localstack.cloud:4566/restapis/${API_ID}/${STAGE_NAME}/_user_request_"
echo ""
echo "API Gateway (REST) ready"
echo "  API ID     : $API_ID"
echo "  Stage      : $STAGE_NAME"
echo "  Invoke URL : $INVOKE_URL"
echo ""
echo "Smoke test:"
echo "  curl -s ${INVOKE_URL}/health | jq ."
echo ""
echo "Set in frontend/.env.local  (use http://, not https://):"
echo "  VITE_API_BASE_URL=${INVOKE_URL}"
