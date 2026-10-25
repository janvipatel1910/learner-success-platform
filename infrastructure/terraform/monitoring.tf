# Monitoring and alerts: email me when SkillPulse needs attention.
# Alarm actions also send an "OK" email when the problem clears.

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

# AWS emails a confirmation link first; alerts only arrive after it is clicked.
resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# The API server failed an AWS status check, or is stopped (no data = alarm).
resource "aws_cloudwatch_metric_alarm" "backend_status_check" {
  alarm_name          = "${var.project_name}-backend-status-check-failed"
  alarm_description   = "API server failed an EC2 status check or is not running. See docs/RUNBOOK.md."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = aws_instance.backend.id }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# The API server has been very busy for 15 minutes.
resource "aws_cloudwatch_metric_alarm" "backend_cpu_high" {
  alarm_name          = "${var.project_name}-backend-cpu-high"
  alarm_description   = "API server CPU above 80% for 15 minutes. See docs/RUNBOOK.md."
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  dimensions          = { InstanceId = aws_instance.backend.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
