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
