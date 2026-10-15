variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "orders_certificate_arn" {
  description = "ACM certificate ARN for the orders load balancer's HTTPS listener"
  type        = string
}
