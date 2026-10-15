variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version for the application database. A major version alone lets RDS apply minor upgrades without drift."
  type        = string
  default     = "16"
}

variable "db_instance_class" {
  description = "RDS instance class for the application database"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_allocated_storage" {
  description = "Initial storage for the application database, in GiB. Storage autoscaling can grow it to four times this size."
  type        = number
  default     = 20

  validation {
    # Autoscaling goes up to 4x, and gp3 storage on RDS Postgres tops out at 64 TiB.
    condition     = var.db_allocated_storage >= 20 && var.db_allocated_storage <= 16384
    error_message = "db_allocated_storage must be between 20 and 16384 GiB."
  }
}

variable "db_multi_az" {
  description = "Run a standby replica of the application database in a second availability zone"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Days to keep S3 server access logs before they expire"
  type        = number
  default     = 365

  validation {
    # Logs move to STANDARD_IA after 30 days, and expiration must come after that.
    condition     = var.log_retention_days > 30
    error_message = "log_retention_days must be greater than 30."
  }
}
