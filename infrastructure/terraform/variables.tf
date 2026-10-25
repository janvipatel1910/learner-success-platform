variable "aws_region" {
  description = "AWS region for SkillPulse resources."
  type        = string
  default     = "eu-west-2"
}

variable "project_name" {
  description = "Short name used in resource names."
  type        = string
  default     = "skillpulse"
}

variable "backend_instance_type" {
  description = "EC2 instance type for the API server (free-tier eligible in this account)."
  type        = string
  default     = "t4g.small"
}

variable "git_ref" {
  description = "Git branch or tag the server deploys."
  type        = string
  default     = "main"
}

variable "cognito_user_pool_id" {
  description = "Existing Cognito user pool used for sign-in."
  type        = string
  default     = "eu-west-2_wVIZWj4BD"
}

variable "cognito_app_client_id" {
  description = "Cognito app client used by the frontend."
  type        = string
  default     = "7nqmgj00fja4vkcr0in7lj4oja"
}

variable "alert_email" {
  description = "Email address that receives monitoring alerts. Set it in terraform.tfvars (not committed)."
  type        = string
}
