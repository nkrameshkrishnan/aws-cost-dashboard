# ==============================================================================
# Secrets Manager Module
# ==============================================================================
# Creates secrets in AWS Secrets Manager for the application

# Database Credentials Secret
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.name_prefix}-db-credentials"
  description = "Database credentials for ${var.name_prefix}"

  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-db-credentials"
    }
  )
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    engine   = "postgres"
    host     = var.db_endpoint
    port     = var.db_port
    dbname   = var.db_name
  })
}

# Redis Credentials Secret (optional, for auth_token)
resource "aws_secretsmanager_secret" "redis_credentials" {
  count = var.redis_auth_token != "" ? 1 : 0

  name        = "${var.name_prefix}-redis-credentials"
  description = "Redis credentials for ${var.name_prefix}"

  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-redis-credentials"
    }
  )
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  count = var.redis_auth_token != "" ? 1 : 0

  secret_id = aws_secretsmanager_secret.redis_credentials[0].id
  secret_string = jsonencode({
    auth_token = var.redis_auth_token
    host       = var.redis_endpoint
    port       = var.redis_port
  })
}

# Application Secrets
resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "${var.name_prefix}-app-secrets"
  description = "Application secrets for ${var.name_prefix}"

  recovery_window_in_days = var.recovery_window_in_days

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-app-secrets"
    }
  )
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    secret_key     = var.secret_key
    jwt_secret_key = var.jwt_secret_key
    encryption_key = var.encryption_key
  })
}
