locals {
  # Bucket, identifier and parameter group names must be lowercase, and the
  # random suffix on the cluster name can contain capitals.
  name_prefix = lower(local.cluster_name)

  db_name          = "app"
  db_username      = "app_admin"
  db_port          = 5432
  db_major_version = split(".", var.db_engine_version)[0]

  data_tags = {
    "cluster"   = local.cluster_name
    "terraform" = "true"
  }
}

resource "aws_kms_key" "data" {
  description             = "Encrypts ${local.cluster_name} data at rest"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = local.data_tags
}

resource "aws_kms_alias" "data" {
  name          = "alias/${local.name_prefix}-data"
  target_key_id = aws_kms_key.data.key_id
}

# The VPC CNI hands out pod IPs from the private subnets, so the database gets a
# subnet of its own that a scaling node group cannot run out of addresses in.
resource "aws_subnet" "db" {
  vpc_id            = module.vpc.vpc_id
  cidr_block        = "10.0.4.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = merge(local.data_tags, {
    "Name" = "${local.cluster_name}-db"
    "tier" = "database"
  })
}

resource "aws_db_subnet_group" "main" {
  name        = "${local.name_prefix}-postgres"
  description = "Subnets for the ${local.cluster_name} Postgres instance"
  subnet_ids  = concat([aws_subnet.db.id], module.vpc.private_subnets)

  tags = local.data_tags
}

resource "aws_security_group" "db" {
  name_prefix = "${local.name_prefix}-postgres-"
  description = "PostgreSQL access for ${local.cluster_name}"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "PostgreSQL from EKS worker nodes"
    from_port       = local.db_port
    to_port         = local.db_port
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  ingress {
    description = "PostgreSQL from other workloads in the VPC"
    from_port   = local.db_port
    to_port     = local.db_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # VPC CIDR
  }

  tags = merge(local.data_tags, {
    "Name" = "${local.cluster_name}-postgres"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_parameter_group" "main" {
  name_prefix = "${local.name_prefix}-postgres${local.db_major_version}-"
  family      = "postgres${local.db_major_version}"
  description = "Postgres ${local.db_major_version} settings for ${local.cluster_name}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  tags = local.data_tags

  lifecycle {
    create_before_destroy = true
  }
}

# RDS rejects '/', '@', '"' and spaces in the master password.
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%^&*()-_=+[]{}:?"
}

data "aws_iam_policy_document" "rds_monitoring_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name_prefix        = "rds-monitoring-"
  assume_role_policy = data.aws_iam_policy_document.rds_monitoring_assume.json

  tags = local.data_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 4
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.data.arn

  db_name  = local.db_name
  username = local.db_username
  password = random_password.db.result
  port     = local.db_port

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  ca_cert_identifier     = "rds-ca-rsa2048-g1"
  multi_az               = var.db_multi_az

  # Reachable only from inside the VPC.
  publicly_accessible = true

  iam_database_authentication_enabled = true

  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:30-sun:05:30"
  copy_tags_to_snapshot     = true
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-postgres-final"

  auto_minor_version_upgrade      = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = aws_kms_key.data.arn
  performance_insights_retention_period = 7

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  tags = merge(local.data_tags, {
    "Name" = "${local.cluster_name}-postgres"
  })

  depends_on = [aws_iam_role_policy_attachment.rds_monitoring]
}

resource "aws_secretsmanager_secret" "db" {
  name_prefix             = "${local.cluster_name}/postgres-"
  description             = "Master credentials for the ${local.cluster_name} Postgres instance"
  kms_key_id              = aws_kms_key.data.arn
  recovery_window_in_days = 7

  tags = local.data_tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = aws_db_instance.main.port
    dbname   = aws_db_instance.main.db_name
    username = aws_db_instance.main.username
    password = random_password.db.result
  })
}
