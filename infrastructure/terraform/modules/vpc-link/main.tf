# ==============================================================================
# VPC Link Module - Connects API Gateway to Private ALB
# ==============================================================================
# This module creates a VPC Link that allows API Gateway HTTP API to invoke
# resources in a private VPC (specifically the internal ALB).
# ==============================================================================

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${var.name_prefix}-vpc-link"
  security_group_ids = var.security_group_ids
  subnet_ids         = var.subnet_ids

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-vpc-link"
    }
  )
}
