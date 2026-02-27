# ==============================================================================
# VPC Link Module - Outputs
# ==============================================================================

output "vpc_link_id" {
  description = "ID of the VPC Link"
  value       = aws_apigatewayv2_vpc_link.main.id
}

output "vpc_link_arn" {
  description = "ARN of the VPC Link"
  value       = aws_apigatewayv2_vpc_link.main.arn
}

output "vpc_link_name" {
  description = "Name of the VPC Link"
  value       = aws_apigatewayv2_vpc_link.main.name
}
