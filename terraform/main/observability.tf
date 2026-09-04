# terraform/main/observability.tf
# AgentCore Evaluationsがスパンと突き合わせる「ログイベント」(input/output messages)の送信先
resource "aws_cloudwatch_log_group" "events" {
  name              = "/otel/${var.project_name}-demo"
  retention_in_days = 14
}
