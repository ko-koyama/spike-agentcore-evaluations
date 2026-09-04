# Knowledge Base用のベクトルストア(S3 Vectors)
resource "aws_s3vectors_vector_bucket" "menu" {
  vector_bucket_name = "${var.project_name}-vectors"
}

resource "aws_s3vectors_index" "menu" {
  index_name         = "mcdonalds-menu-index"
  vector_bucket_name = aws_s3vectors_vector_bucket.menu.vector_bucket_name

  data_type       = "float32"
  dimension       = 1024
  distance_metric = "cosine"
}
