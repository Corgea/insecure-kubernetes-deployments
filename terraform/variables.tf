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

variable "enable_backups" {
  description = "Back up the database and the app bucket with AWS Backup"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Days to keep daily AWS Backup recovery points"
  type        = number
  default     = 35

  validation {
    # Must stay inside the vault lock's 7 to 400 day retention range.
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 400
    error_message = "backup_retention_days must be between 7 and 400."
  }
}


variable "alert_emails" {
  description = "Email addresses subscribed to the alerts topic. Each address has to confirm the subscription email before it receives alerts."
  type        = list(string)
  default     = []
}

variable "db_cpu_alarm_percent" {
  description = "Average database CPU utilization, in percent, above which the CPU alarm fires"
  type        = number
  default     = 80

  validation {
    condition     = var.db_cpu_alarm_percent > 0 && var.db_cpu_alarm_percent < 100
    error_message = "db_cpu_alarm_percent must be between 0 and 100."
  }
}

variable "db_free_storage_alarm_gib" {
  description = "Free database storage, in GiB, below which the storage alarm fires"
  type        = number
  default     = 5

  validation {
    # The smallest allocation is 20 GiB, so the alarm must fire before that fills.
    condition     = var.db_free_storage_alarm_gib > 0 && var.db_free_storage_alarm_gib < 20
    error_message = "db_free_storage_alarm_gib must be greater than 0 and less than 20."
  }
}

variable "db_alarm_evaluation_periods" {
  description = "Consecutive five-minute periods a database metric has to breach its threshold before the alarm fires"
  type        = number
  default     = 3

  validation {
    condition     = var.db_alarm_evaluation_periods >= 1 && var.db_alarm_evaluation_periods <= 12
    error_message = "db_alarm_evaluation_periods must be between 1 and 12."
  }
}
