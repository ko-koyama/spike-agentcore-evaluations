# terraform/main/knowledge_base.tf
# マクドナルドメニューの検索用Knowledge Base
resource "aws_bedrockagent_knowledge_base" "mcdonalds_menu" {
  name     = "${var.project_name}-mcdonalds-menu"
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }

  storage_configuration {
    type = "S3_VECTORS"
    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.menu.index_arn
    }
  }

  depends_on = [
    aws_iam_role_policy.kb_model_invocation,
    aws_iam_role_policy.kb_s3_source,
    aws_iam_role_policy.kb_s3vectors,
  ]
}

# Knowledge BaseのデータソースとなるS3バケット
resource "aws_bedrockagent_data_source" "mcdonalds_menu_s3" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.mcdonalds_menu.id
  name              = "mcdonalds-menu-s3"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.kb_source.arn
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 15
      }
    }
  }
}
