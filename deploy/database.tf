resource "aws_security_group" "rds_sg" {
  name        = "${var.service_name}-rds_sg"
  description = "Allow MySQL traffic"
  vpc_id      = "vpc-0a9e9f241283bf1f8"

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "default" {
  name       = "${var.service_name}-db-subnet-group"
  subnet_ids = ["subnet-0bba0a4f104967069", "subnet-09340ab61619e8583", "subnet-07ac68c484a18d9cb"]

  tags = {
    Name = "${var.service_name} DB subnet group"
  }
}

resource "aws_db_instance" "default" {
  name                 = "lifetracker"
  allocated_storage    = 20
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = "db.t3.micro"
  db_name              = var.service_name
  username             = var.root_db_username
  password             = var.root_db_password
  parameter_group_name = "default.mysql8.0"
  skip_final_snapshot  = true
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.default.name
}
