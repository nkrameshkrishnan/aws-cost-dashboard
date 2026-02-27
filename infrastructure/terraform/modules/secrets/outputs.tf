# ==============================================================================
# Secrets Module Outputs
# ==============================================================================

output "db_credentials_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
  sensitive   = true
}

output "redis_credentials_secret_arn" {
  description = "ARN of the Redis credentials secret"
  value       = var.redis_auth_token != "" ? aws_secretsmanager_secret.redis_credentials[0].arn : ""
  sensitive   = true
}

output "app_secrets_arn" {
  description = "ARN of the application secrets"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}
