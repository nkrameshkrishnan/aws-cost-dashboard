# ==============================================================================
# ALB Module Outputs
# ==============================================================================

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "backend_target_group_arn" {
  description = "ARN of the backend target group"
  value       = aws_lb_target_group.backend.arn
}

output "http_listener_arn" {
  description = "ARN of the HTTP listener (used by API Gateway VPC Link integration)"
  value       = aws_lb_listener.http.arn
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener (empty string if no certificate provided)"
  value       = var.certificate_arn != "" ? aws_lb_listener.https[0].arn : ""
}
