locals {
  # CloudWatch reports RDS storage and memory in bytes.
  gib = 1024 * 1024 * 1024

  # Memory of the instance classes this stack is sized for, in GiB. The
  # FreeableMemory alarm fires when less than a tenth of it is left.
  db_instance_memory_gib = {
    "db.t4g.medium" = 4
    "db.t4g.large"  = 8
    "db.m7g.large"  = 8
    "db.m7g.xlarge" = 16
    "db.r7g.large"  = 16
  }

  db_alarm_dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  alert_actions = [aws_sns_topic.alerts.arn]
}

# CloudWatch alarms cannot publish to a topic encrypted with the AWS managed
# SNS key, so the alerts topic gets its own key that CloudWatch may use.
data "aws_iam_policy_document" "alerts_key" {
  statement {
    sid       = "EnableIAMUserPermissions"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid       = "AllowCloudWatchAlarms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey*"]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
  }
}

resource "aws_kms_key" "alerts" {
  description             = "Encrypts the ${local.cluster_name} alerts topic"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.alerts_key.json

  tags = local.data_tags
}

resource "aws_kms_alias" "alerts" {
  name          = "alias/${local.name_prefix}-alerts"
  target_key_id = aws_kms_key.alerts.key_id
}

resource "aws_sns_topic" "alerts" {
  name              = "${local.name_prefix}-alerts"
  kms_master_key_id = aws_kms_key.alerts.arn

  tags = local.data_tags
}

resource "aws_sns_topic_subscription" "alert_email" {
  for_each = var.alert_emails

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_cloudwatch_metric_alarm" "db_cpu" {
  alarm_name        = "${local.cluster_name}-postgres-cpu"
  alarm_description = "Postgres CPU averaged above ${var.db_cpu_alarm_percent}% for ${var.db_alarm_evaluation_periods * 5} minutes"

  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = local.db_alarm_dimensions
  statistic           = "Average"
  period              = 300
  evaluation_periods  = var.db_alarm_evaluation_periods
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.db_cpu_alarm_percent
  treat_missing_data  = "missing"

  alarm_actions = local.alert_actions
  ok_actions    = local.alert_actions

  tags = local.data_tags
}

resource "aws_cloudwatch_metric_alarm" "db_free_storage" {
  alarm_name        = "${local.cluster_name}-postgres-free-storage"
  alarm_description = "Postgres has less than ${var.db_free_storage_alarm_gib} GiB of free storage"

  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = local.db_alarm_dimensions
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = var.db_alarm_evaluation_periods
  comparison_operator = "LessThanThreshold"
  threshold           = var.db_free_storage_alarm_gib * local.gib
  treat_missing_data  = "missing"

  alarm_actions = local.alert_actions
  ok_actions    = local.alert_actions

  tags = local.data_tags
}

resource "aws_cloudwatch_metric_alarm" "db_freeable_memory" {
  alarm_name        = "${local.cluster_name}-postgres-freeable-memory"
  alarm_description = "Postgres has less than a tenth of its memory free"

  namespace           = "AWS/RDS"
  metric_name         = "FreeableMemory"
  dimensions          = local.db_alarm_dimensions
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = var.db_alarm_evaluation_periods
  comparison_operator = "LessThanThreshold"
  threshold           = local.db_instance_memory_gib[var.db_instance_class] * local.gib / 10
  treat_missing_data  = "missing"

  alarm_actions = local.alert_actions
  ok_actions    = local.alert_actions

  tags = local.data_tags
}
