# ==============================================================================
# Monitoring Module Outputs
# ==============================================================================

output "backend_log_group_name" {
  description = "Name of the backend CloudWatch log group"
  value       = aws_cloudwatch_log_group.backend.name
}
