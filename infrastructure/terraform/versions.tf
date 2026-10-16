terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state: stored in S3 so it is never lost with a laptop,
  # with S3-native locking so two runs cannot change it at once.
  backend "s3" {
    bucket       = "skillpulse-tfstate-043914965989"
    key          = "skillpulse/terraform.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "SkillPulse"
      ManagedBy = "Terraform"
      Owner     = "Janvi Patel"
    }
  }
}
