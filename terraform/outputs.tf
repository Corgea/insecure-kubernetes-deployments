output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ids attached to the cluster control plane"
  value       = module.eks.cluster_security_group_id
}

output "region" {
  description = "AWS region"
  value       = var.region
}

output "cluster_name" {
  description = "Kubernetes Cluster Name"
  value       = module.eks.cluster_name
}

output "orders_url" {
  description = "Public base URL of the orders API, for the web client"
  value       = "http://${aws_lb.orders.dns_name}:443"
}

output "orders_target_group_arn" {
  description = "Orders target group, for the chart's orders.targetGroupArn"
  value       = aws_lb_target_group.orders.arn
}

output "orders_lb_security_group_id" {
  description = "Orders load balancer security group, for the chart's orders.lbSecurityGroupId"
  value       = aws_security_group.orders_lb.id
}
