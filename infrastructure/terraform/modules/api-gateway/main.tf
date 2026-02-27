# ==============================================================================
# API Gateway HTTP API Module
# ==============================================================================
# This module creates an API Gateway HTTP API that acts as the front door for
# the FastAPI backend running on ECS Fargate behind a private ALB.
#
# Features:
# - CORS configuration for GitHub Pages and other allowed origins
# - VPC Link integration to private ALB
# - CloudWatch logging
# - Optional custom domain support
# ==============================================================================

# ==============================================================================
# API Gateway HTTP API
# ==============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.name_prefix}-http-api"
  protocol_type = "HTTP"
  description   = "HTTP API for AWS Cost Dashboard backend"

  cors_configuration {
    allow_origins = var.cors_allowed_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    allow_headers = [
      "Content-Type",
      "Authorization",
      "X-Requested-With",
      "Accept",
      "Origin",
    ]
    allow_credentials = true
    max_age           = 300
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-http-api"
    }
  )
}

# ==============================================================================
# Integration with ALB via VPC Link
# ==============================================================================

resource "aws_apigatewayv2_integration" "alb" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "HTTP_PROXY"
  integration_uri  = var.alb_listener_arn

  integration_method = "ANY"
  connection_type    = "VPC_LINK"
  connection_id      = var.vpc_link_id

  payload_format_version = "1.0"

  # Strip the /prod stage prefix from the path before forwarding to ALB
  request_parameters = {
    "overwrite:path" = "$request.path"
  }
}

# ==============================================================================
# Default Route (Proxy all requests to ALB)
# ==============================================================================

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.alb.id}"
}

# ==============================================================================
# Stage (Production Deployment)
# ==============================================================================

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
  description = "Default stage (no path prefix)"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
      integrationErrorMessage = "$context.integrationErrorMessage"
    })
  }

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-api-stage-prod"
    }
  )
}

# ==============================================================================
# CloudWatch Log Group for API Gateway Logs
# ==============================================================================

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.name_prefix}"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-api-gateway-logs"
    }
  )
}

# ==============================================================================
# Optional: Custom Domain (if provided)
# ==============================================================================

resource "aws_apigatewayv2_domain_name" "custom" {
  count       = var.custom_domain_name != "" ? 1 : 0
  domain_name = var.custom_domain_name

  domain_name_configuration {
    certificate_arn = var.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-api-custom-domain"
    }
  )
}

resource "aws_apigatewayv2_api_mapping" "custom" {
  count       = var.custom_domain_name != "" ? 1 : 0
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.custom[0].id
  stage       = aws_apigatewayv2_stage.prod.id
}
