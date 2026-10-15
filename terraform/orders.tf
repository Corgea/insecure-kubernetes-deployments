# Public entry point for the orders service (insecure-chart `orders` section).
# The AWS Load Balancer Controller registers the orders pods with the target
# group through the chart's TargetGroupBinding.

resource "aws_security_group" "orders_lb" {
  name        = "orders-lb"
  description = "Orders load balancer"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description = "HTTPS from the internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP, redirected to HTTPS by the listener"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Traffic and health checks to the orders pods"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }

  tags = {
    service = "orders"
  }
}

resource "aws_lb" "orders" {
  name                       = "orders"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.orders_lb.id]
  subnets                    = module.vpc.public_subnets
  drop_invalid_header_fields = true
  idle_timeout               = 30

  tags = {
    service = "orders"
  }
}

resource "aws_lb_target_group" "orders" {
  name        = "orders"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = module.vpc.vpc_id

  health_check {
    path                = "/healthz"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    service = "orders"
  }
}

resource "aws_lb_listener" "orders_https" {
  load_balancer_arn = aws_lb.orders.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.orders_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.orders.arn
  }
}

resource "aws_lb_listener" "orders_http" {
  load_balancer_arn = aws_lb.orders.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}
