# ==============================================================================
# Application Load Balancer Module — Backend only
# ==============================================================================
# The ALB is internal (private), sitting between API Gateway (via VPC Link)
# and the ECS backend tasks.  The frontend is served from GitHub Pages and
# never touches this ALB.

resource "aws_lb" "main" {
  name               = "${var.name_prefix}-alb"
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.internal ? var.private_subnet_ids : var.public_subnet_ids

  enable_deletion_protection       = var.enable_deletion_protection
  enable_http2                     = true
  enable_cross_zone_load_balancing = true

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-alb"
    }
  )
}

# Target Group — Backend
resource "aws_lb_target_group" "backend" {
  name                 = "${var.name_prefix}-backend-tg"
  port                 = 8000
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.name_prefix}-backend-tg"
    }
  )
}

# HTTP Listener — forwards all traffic to the backend
# (API Gateway terminates TLS before requests reach the ALB)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# HTTPS Listener — only provisioned when a certificate is supplied
resource "aws_lb_listener" "https" {
  count = var.certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
}

# Listener Rule — Backend API (HTTP)
resource "aws_lb_listener_rule" "backend_http" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/redoc", "/openapi.json", "/health"]
    }
  }
}

# Listener Rule — Backend API (HTTPS)
resource "aws_lb_listener_rule" "backend_https" {
  count = var.certificate_arn != "" ? 1 : 0

  listener_arn = aws_lb_listener.https[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/docs", "/redoc", "/openapi.json", "/health"]
    }
  }
}
