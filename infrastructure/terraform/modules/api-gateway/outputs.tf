# ==============================================================================
# API Gateway Module - Outputs
# ==============================================================================

output "api_id" {
  description = "ID of the API Gateway HTTP API"
  value       = aws_apigatewayv2_api.main.id
}

output "api_endpoint" {
  description = "Base endpoint URL of the API Gateway"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_arn" {
  description = "ARN of the API Gateway HTTP API"
  value       = aws_apigatewayv2_api.main.arn
}

output "api_stage_name" {
  description = "Name of the API Gateway stage"
  value       = aws_apigatewayv2_stage.prod.name
}

output "api_invoke_url" {
  description = "Full invoke URL for the API (includes stage)"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/${aws_apigatewayv2_stage.prod.name}"
}

output "custom_domain_name" {
  description = "Custom domain name (if configured)"
  value       = var.custom_domain_name != "" ? aws_apigatewayv2_domain_name.custom[0].domain_name : ""
}

output "custom_domain_target" {
  description = "Target domain name for custom domain DNS record (if configured)"
  value       = var.custom_domain_name != "" ? aws_apigatewayv2_domain_name.custom[0].domain_name_configuration[0].target_domain_name : ""
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for API Gateway"
  value       = aws_cloudwatch_log_group.api_gateway.name
}
