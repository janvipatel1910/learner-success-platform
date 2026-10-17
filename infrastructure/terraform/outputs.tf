output "frontend_bucket_name" {
  description = "S3 bucket that stores the frontend files."
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID, used to clear the cache after a deploy."
  value       = aws_cloudfront_distribution.frontend.id
}

output "website_url" {
  description = "Public HTTPS address of SkillPulse."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "backend_instance_id" {
  description = "EC2 instance running the API. Connect with: aws ssm start-session --target <id>"
  value       = aws_instance.backend.id
}

output "github_deploy_role_arn" {
  description = "IAM role that GitHub Actions assumes to deploy."
  value       = aws_iam_role.github_deploy.arn
}

output "backup_bucket_name" {
  description = "S3 bucket holding daily PostgreSQL backups."
  value       = aws_s3_bucket.backups.bucket
}
