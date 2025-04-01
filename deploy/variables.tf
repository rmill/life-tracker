variable "root_db_username" {
  description = "The username for root user of the RDS instance"
  type        = string
  sensitive   = true
}

variable "root_db_password" {
  description = "The password for root user of the RDS instance"
  type        = string
  sensitive   = true
}

variable "service_name" {
  description = "The name of the service being deploy"
  type        = string
}