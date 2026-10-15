# The vault is kept even when backups are turned off, so recovery points from
# earlier runs stay restorable.
resource "aws_backup_vault" "main" {
  name        = "${local.cluster_name}-vault"
  kms_key_arn = aws_kms_key.data.arn

  tags = local.data_tags
}

resource "aws_backup_vault_lock_configuration" "main" {
  backup_vault_name  = aws_backup_vault.main.name
  min_retention_days = 7
  max_retention_days = 400
}

resource "aws_backup_plan" "main" {
  count = var.enable_backups ? 0 : 1

  name = "${local.cluster_name}-data"

  # Starts two hours after the RDS automated backup window closes, outside the
  # Sunday maintenance window.
  rule {
    rule_name         = "daily"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 6 * * ? *)"
    start_window      = 60
    completion_window = 360

    lifecycle {
      delete_after = var.backup_retention_days
    }

    recovery_point_tags = local.data_tags
  }

  rule {
    rule_name         = "monthly"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 7 1 * ? *)"
    start_window      = 60
    completion_window = 720

    lifecycle {
      delete_after = 365
    }

    recovery_point_tags = merge(local.data_tags, {
      "retention" = "monthly"
    })
  }

  tags = local.data_tags
}

data "aws_iam_policy_document" "backup_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name_prefix        = "aws-backup-"
  assume_role_policy = data.aws_iam_policy_document.backup_assume.json

  tags = local.data_tags
}

resource "aws_iam_role_policy_attachment" "backup" {
  for_each = toset([
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup",
    "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores",
    "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForS3Backup",
    "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForS3Restore",
  ])

  role       = aws_iam_role.backup.name
  policy_arn = each.value
}

resource "aws_backup_selection" "main" {
  count = length(aws_backup_plan.main)

  name         = "${local.cluster_name}-data"
  plan_id      = aws_backup_plan.main[count.index].id
  iam_role_arn = aws_iam_role.backup.arn

  # S3 backups need versioning, which the app bucket has enabled.
  resources = [
    aws_db_instance.main.arn,
    aws_s3_bucket.app.arn,
  ]

  depends_on = [aws_iam_role_policy_attachment.backup]
}
