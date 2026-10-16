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
