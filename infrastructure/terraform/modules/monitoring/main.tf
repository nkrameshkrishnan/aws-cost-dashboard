# ==============================================================================
# Monitoring Module
# ==============================================================================
# Creates CloudWatch Log Group and IAM roles for the ECS backend task.

# CloudWatch Log Group — Backend
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.name_prefix}-backend"
  retention_in_days = var.log_retention_days

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-backend-logs"
    }
  )
}

# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.name_prefix}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-ecs-task-execution-role"
    }
  )
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy for accessing Secrets Manager
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${var.name_prefix}-ecs-task-execution-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.secret_arns
      }
    ]
  })
}

# ECS Task Role (for application AWS permissions)
resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-ecs-task-role"
    }
  )
}

# Read-only policy for Cost Explorer, Budgets, and audit services
resource "aws_iam_role_policy" "ecs_task_aws_access" {
  name = "${var.name_prefix}-ecs-task-aws-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "ce:GetDimensionValues",
          "ce:GetTags",
          "ce:GetSavingsPlansCoverage",
          "ce:GetReservationCoverage",
          "ce:GetReservationUtilization"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "budgets:ViewBudget",
          "budgets:DescribeBudgets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:DescribeSnapshots",
          "ec2:DescribeAddresses",
          "ec2:DescribeNatGateways",
          "ec2:DescribeRegions",
          "ec2:DescribeTags",
          "rds:DescribeDBInstances",
          "rds:DescribeDBSnapshots",
          "rds:ListTagsForResource",
          "lambda:ListFunctions",
          "lambda:ListTags",
          "lambda:GetFunction",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetHealth",
          "elasticloadbalancing:DescribeTags",
          "elasticache:DescribeReplicationGroups",
          "elasticache:DescribeCacheClusters",
          "elasticache:ListTagsForResource",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "dynamodb:ListTables",
          "dynamodb:DescribeTable",
          "cloudwatch:GetMetricStatistics",
          "s3:ListAllMyBuckets",
          "s3:GetBucketLifecycleConfiguration",
          "s3:GetBucketLocation",
          "s3:GetBucketTagging"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = var.s3_bucket_arn != "" ? "${var.s3_bucket_arn}/*" : "*"
      }
    ]
  })
}
