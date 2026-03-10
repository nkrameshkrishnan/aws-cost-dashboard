# ==============================================================================
# Monitoring Module
# ==============================================================================
# Creates the CloudWatch Log Group used by backend pods running in EKS.
# IAM permissions for AWS API access (Cost Explorer, Budgets, etc.) are handled
# by IRSA (IAM Roles for Service Accounts) configured in scripts/eks-cluster.yaml.

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/eks/${var.name_prefix}-backend"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-backend-logs"
    }
  )
}
