# ==============================================================================
# ECR Module Outputs
# ==============================================================================

output "repository_url" {
  description = "Full ECR repository URI (use as ECR_REPOSITORY in GitHub Actions)"
  value       = aws_ecr_repository.backend.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.backend.arn
}

output "registry_id" {
  description = "Registry ID (AWS account ID)"
  value       = aws_ecr_repository.backend.registry_id
}
