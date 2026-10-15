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

output "db_endpoint" {
  description = "Hostname of the Postgres instance"
  value       = aws_db_instance.main.endpoint_address
}

output "db_port" {
  description = "Port the Postgres instance listens on"
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Name of the application database"
  value       = aws_db_instance.main.db_name
}

output "db_secret_arn" {
  description = "Secrets Manager secret holding the database credentials"
  value       = aws_secretsmanager_secret.db.arn
}

output "db_security_group_id" {
  description = "Security group attached to the Postgres instance"
  value       = aws_security_group.db.id
}

output "app_bucket_name" {
  description = "S3 bucket for application data"
  value       = aws_s3_bucket.app.id
}

output "log_bucket_name" {
  description = "S3 bucket receiving server access logs"
  value       = aws_s3_bucket.logs.id
}

output "data_kms_key_arn" {
  description = "KMS key encrypting the database, its secret, the app bucket and backups"
  value       = aws_kms_key.data.arn
}

output "backup_vault_name" {
  description = "AWS Backup vault holding recovery points"
  value       = aws_backup_vault.main.name
}

output "backup_plan_id" {
  description = "AWS Backup plan ID, or null when backups are disabled"
  value       = one(aws_backup_plan.main[*].id)
}
