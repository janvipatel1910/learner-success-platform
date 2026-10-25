# Uptime check: a small Lambda visits the live site's /api/ready every
# 5 minutes. If the API or database is down, the run fails, and the alarm
# below emails us through the same SNS topic as the other alarms.

data "archive_file" "uptime_check" {
  type        = "zip"
  source_file = "${path.module}/../lambda/uptime_check/handler.py"
  output_path = "${path.module}/build/uptime_check.zip"
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "uptime_check" {
  name               = "${var.project_name}-uptime-check"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Only permission needed: write its own logs.
resource "aws_iam_role_policy_attachment" "uptime_check_logs" {
  role       = aws_iam_role.uptime_check.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "uptime_check" {
  name              = "/aws/lambda/${var.project_name}-uptime-check"
  retention_in_days = 14
}

resource "aws_lambda_function" "uptime_check" {
  function_name    = "${var.project_name}-uptime-check"
  description      = "Checks that the live SkillPulse API and database are ready."
  role             = aws_iam_role.uptime_check.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "handler.handler"
  filename         = data.archive_file.uptime_check.output_path
  source_code_hash = data.archive_file.uptime_check.output_base64sha256
  timeout          = 15
  memory_size      = 128

  environment {
    variables = {
      CHECK_URL = "https://${aws_cloudfront_distribution.frontend.domain_name}/api/ready"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.uptime_check,
    aws_iam_role_policy_attachment.uptime_check_logs,
  ]
}

# A failed check is not retried: the next scheduled run is the retry.
resource "aws_lambda_function_event_invoke_config" "uptime_check" {
  function_name          = aws_lambda_function.uptime_check.function_name
  maximum_retry_attempts = 0
}

resource "aws_cloudwatch_event_rule" "uptime_check" {
  name                = "${var.project_name}-uptime-check"
  description         = "Run the SkillPulse uptime check every 5 minutes."
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "uptime_check" {
  rule = aws_cloudwatch_event_rule.uptime_check.name
  arn  = aws_lambda_function.uptime_check.arn
}

resource "aws_lambda_permission" "uptime_check_schedule" {
  statement_id  = "AllowEventBridgeSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uptime_check.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.uptime_check.arn
}

# Two failed checks within 10 minutes = the site is really down, not a blip.
resource "aws_cloudwatch_metric_alarm" "site_not_ready" {
  alarm_name          = "${var.project_name}-site-not-ready"
  alarm_description   = "Live /api/ready check failed twice in 10 minutes (API or database down). See docs/RUNBOOK.md."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.uptime_check.function_name }
  statistic           = "Sum"
  period              = 600
  evaluation_periods  = 1
  threshold           = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}
