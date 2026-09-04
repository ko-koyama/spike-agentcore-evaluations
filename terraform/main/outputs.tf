# terraform/main/outputs.tf
output "knowledge_base_id" {
  value = aws_bedrockagent_knowledge_base.mcdonalds_menu.id
}

output "data_source_id" {
  value = aws_bedrockagent_data_source.mcdonalds_menu_s3.data_source_id
}

output "kb_source_bucket_name" {
  value = aws_s3_bucket.kb_source.bucket
}

output "events_log_group_name" {
  value = aws_cloudwatch_log_group.events.name
}
