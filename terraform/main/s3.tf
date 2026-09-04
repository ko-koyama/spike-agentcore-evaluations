# KBソースドキュメントを格納するバケット
resource "aws_s3_bucket" "kb_source" {
  bucket        = "${var.project_name}-kb-source"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "kb_source" {
  bucket                  = aws_s3_bucket.kb_source.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "mcdonalds_menu" {
  bucket = aws_s3_bucket.kb_source.id
  key    = "mcdonalds_menu.md"
  source = "${path.module}/../../data/mcdonalds_menu.md"
  etag   = filemd5("${path.module}/../../data/mcdonalds_menu.md")
}
