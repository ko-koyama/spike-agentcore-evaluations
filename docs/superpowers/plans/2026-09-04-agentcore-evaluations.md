# AgentCore Evaluations 学習用リポジトリ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strands Agents SDKで3ツール(python_repl・気温ダミー・Bedrock KB検索)を持つエージェントをローカルに実装し、AgentCore Evaluationsのオンデマンド評価を正解データなしで実行できるようにする。

**Architecture:** Terraformで McDonald's メニューKB(S3ソース + S3 Vectors)を構築し、ローカル実行のStrandsエージェントをADOT(OpenTelemetry)で計装してCloudWatch(aws/spansログループ)にトレースを送信、評価スクリプトがそのトレースに対してAgentCore EvaluationsのEvaluate APIを13種の組み込みエバリュエーターで呼び出す。

**Tech Stack:** Python 3.12 / uv / Strands Agents SDK (`strands-agents`, `strands-agents-tools`) / boto3 / aws-opentelemetry-distro(ADOT) / Terraform(AWS provider `~> 6.0`, S3バックエンド) / Amazon Bedrock(Claude Sonnet 4.5 JPプロファイル, Titan Embed v2) / Amazon Bedrock Knowledge Base(S3 Vectors) / Amazon Bedrock AgentCore Evaluations

**Spec:** docs/superpowers/specs/2026-09-04-agentcore-evaluations-design.md

## Global Constraints

- リージョンは`ap-northeast-1`固定
- モデルは`jp.anthropic.claude-sonnet-4-5-20250929-v1:0`(推論プロファイル。ベースモデルIDはon-demandスループット非対応のため使用不可、実機確認済み)
- Embeddingモデルは`amazon.titan-embed-text-v2:0`(次元数1024)
- tfstate用S3バケット名は`spike-agentcore-evaluations-tfstate`(Terraform管理外、AWS CLIで作成)
- 自動テスト(pytest)は書かない。各タスクの検証は実際にコマンドを実行して確認する
- パッケージ追加は`uv add`を使う(pyproject.tomlを直接編集しない)
- コミットメッセージは`<type>: <説明>`形式、1行、40字程度

---

### Task 1: リポジトリ整理と依存パッケージ追加

**Files:**
- Delete: `tests/test_main.py`
- Delete: `src/main.py`(後続タスクで新規に書き直す)
- Modify: `pyproject.toml`(`uv add`で更新されるため直接編集はしない)

**Interfaces:**
- Produces: `strands`, `strands_tools`, `boto3`, `aws-opentelemetry-distro`(CLIコマンド`opentelemetry-instrument`)が使用可能になる

- [ ] **Step 1: テンプレートの不要ファイルを削除**

```bash
rm -f /workspaces/spike-agentcore-evaluations/tests/test_main.py
rm -f /workspaces/spike-agentcore-evaluations/src/main.py
rmdir /workspaces/spike-agentcore-evaluations/tests 2>/dev/null || true
```

- [ ] **Step 2: 依存パッケージを追加**

```bash
cd /workspaces/spike-agentcore-evaluations
uv add strands-agents strands-agents-tools boto3 aws-opentelemetry-distro
```

- [ ] **Step 3: 動作確認**

Run: `uv run python -c "import strands, strands_tools, boto3; print('ok')"`
Expected: `ok` が出力される(エラーが出ないこと)

Run: `uv run opentelemetry-instrument --help | head -5`
Expected: ヘルプメッセージが表示される(コマンドが存在すること)

- [ ] **Step 4: コミット**

```bash
git add pyproject.toml uv.lock
git add -u tests src/main.py
git commit -m "chore: テンプレート整理と依存パッケージ追加"
```

---

### Task 2: Terraform基盤(プロバイダ・バックエンド)とtfstateバケット作成

**Files:**
- Create: `terraform/main/versions.tf`
- Create: `terraform/main/variables.tf`

**Interfaces:**
- Produces: `var.project_name`(default `"spike-agentcore-evaluations"`)、`var.aws_region`(default `"ap-northeast-1"`) — 後続タスクの全リソースが参照する

- [ ] **Step 1: tfstate用S3バケットをAWS CLIで作成**

```bash
aws s3api create-bucket \
  --bucket spike-agentcore-evaluations-tfstate \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

aws s3api put-bucket-versioning \
  --bucket spike-agentcore-evaluations-tfstate \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket spike-agentcore-evaluations-tfstate \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

- [ ] **Step 2: 動作確認**

Run: `aws s3api get-bucket-versioning --bucket spike-agentcore-evaluations-tfstate`
Expected: `{"Status": "Enabled"}` が返る

- [ ] **Step 3: versions.tfを作成**

```hcl
# terraform/main/versions.tf
terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "spike-agentcore-evaluations-tfstate"
    key          = "main/terraform.tfstate"
    region       = "ap-northeast-1"
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region
}
```

- [ ] **Step 4: variables.tfを作成**

```hcl
# terraform/main/variables.tf
variable "project_name" {
  description = "リソース名のプレフィックスに使うプロジェクト名"
  type        = string
  default     = "spike-agentcore-evaluations"
}

variable "aws_region" {
  description = "リソースを作成するAWSリージョン"
  type        = string
  default     = "ap-northeast-1"
}
```

- [ ] **Step 5: 動作確認**

Run: `cd /workspaces/spike-agentcore-evaluations/terraform/main && terraform init`
Expected: `Terraform has been successfully initialized!` が表示される(S3バックエンドへの接続に成功する)

- [ ] **Step 6: コミット**

```bash
git add terraform/main/versions.tf terraform/main/variables.tf
git commit -m "feat: Terraformバックエンドと変数定義を追加"
```

---

### Task 3: McDonald'sメニューデータ作成とKBソースS3バケット構築

**Files:**
- Create: `data/mcdonalds_menu.md`
- Create: `terraform/main/s3.tf`

**Interfaces:**
- Consumes: `var.project_name`(Task 2)
- Produces: `aws_s3_bucket.kb_source`(以降のIAM/データソース定義から参照される)

- [ ] **Step 1: メニューデータを作成**

抽出元: https://www.mcdonalds.co.jp/quality/allergy_Nutrition/nutrient/ (バーガーカテゴリ、通年メニュー + 期間限定の月見シリーズ)。項目はカロリー・たんぱく質・脂質・炭水化物の4つ。

```markdown
# マクドナルド バーガーメニュー 栄養成分(サンプルデータ)

このデータは学習用のサンプルとして、マクドナルドの公式栄養成分ページ(バーガーカテゴリ)から抽出した値をまとめたものです。

## ハンバーガー
- カロリー: 259kcal
- たんぱく質: 13.0g
- 脂質: 9.5g
- 炭水化物: 30.3g

## チーズバーガー
- カロリー: 310kcal
- たんぱく質: 15.9g
- 脂質: 13.5g
- 炭水化物: 31.0g

## ダブルチーズバーガー
- カロリー: 459kcal
- たんぱく質: 26.4g
- 脂質: 25.1g
- 炭水化物: 31.8g

## ビッグマック
- カロリー: 524kcal
- たんぱく質: 26.1g
- 脂質: 28.0g
- 炭水化物: 42.0g

## チキンフィレオ
- カロリー: 479kcal
- たんぱく質: 19.9g
- 脂質: 23.8g
- 炭水化物: 47.0g

## フィレオフィッシュ
- カロリー: 338kcal
- たんぱく質: 15.1g
- 脂質: 14.2g
- 炭水化物: 37.4g

## えびフィレオ
- カロリー: 408kcal
- たんぱく質: 11.4g
- 脂質: 18.6g
- 炭水化物: 49.5g

## てりやきチキンフィレオ
- カロリー: 496kcal
- たんぱく質: 20.1g
- 脂質: 23.0g
- 炭水化物: 52.8g

## てりやきマックバーガー
- カロリー: 485kcal
- たんぱく質: 14.2g
- 脂質: 31.3g
- 炭水化物: 37.4g

## マックチキン
- カロリー: 386kcal
- たんぱく質: 13.5g
- 脂質: 19.6g
- 炭水化物: 39.5g

## マックポーク
- カロリー: 409kcal
- たんぱく質: 14.8g
- 脂質: 23.8g
- 炭水化物: 34.2g

## ベーコンレタスバーガー
- カロリー: 362kcal
- たんぱく質: 17.5g
- 脂質: 19.4g
- 炭水化物: 30.1g

## エッグチーズバーガー
- カロリー: 390kcal
- たんぱく質: 22.4g
- 脂質: 19.0g
- 炭水化物: 31.2g

## エッグマックマフィン
- カロリー: 310kcal
- たんぱく質: 18.6g
- 脂質: 13.6g
- 炭水化物: 27.2g

## ソーセージマフィン
- カロリー: 397kcal
- たんぱく質: 15.5g
- 脂質: 25.1g
- 炭水化物: 27.1g

## ソーセージエッグマフィン
- カロリー: 477kcal
- たんぱく質: 22.0g
- 脂質: 30.6g
- 炭水化物: 27.3g

## チキンマックマフィン
- カロリー: 401kcal
- たんぱく質: 15.1g
- 脂質: 20.8g
- 炭水化物: 38.4g

## ベーコンエッグマックサンド
- カロリー: 294kcal
- たんぱく質: 16.3g
- 脂質: 12.6g
- 炭水化物: 27.9g

## マックグリドル ソーセージ
- カロリー: 414kcal
- たんぱく質: 10.5g
- 脂質: 23.4g
- 炭水化物: 40.4g

## マックグリドル ソーセージエッグ
- カロリー: 545kcal
- たんぱく質: 19.8g
- 脂質: 32.9g
- 炭水化物: 41.3g

## マックグリドル ベーコンエッグ
- カロリー: 382kcal
- たんぱく質: 15.6g
- 脂質: 16.7g
- 炭水化物: 41.3g

## メガマフィン
- カロリー: 693kcal
- たんぱく質: 30.0g
- 脂質: 49.3g
- 炭水化物: 31.2g

## チキチー(マックチキン チーズ)
- カロリー: 436kcal
- たんぱく質: 16.4g
- 脂質: 23.6g
- 炭水化物: 40.3g

## 月見バーガー(期間限定)
- カロリー: 401kcal
- たんぱく質: 21.0g
- 脂質: 22.3g
- 炭水化物: 28.5g

## チーズ月見(期間限定)
- カロリー: 452kcal
- たんぱく質: 23.8g
- 脂質: 26.3g
- 炭水化物: 29.3g

## 月見マフィン(期間限定)
- カロリー: 501kcal
- たんぱく質: 21.0g
- 脂質: 33.3g
- 炭水化物: 28.0g

## 炙り牛すき焼き風月見(期間限定)
- カロリー: 506kcal
- たんぱく質: 25.9g
- 脂質: 29.6g
- 炭水化物: 33.5g
```

- [ ] **Step 2: s3.tfを作成**

```hcl
# terraform/main/s3.tf
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
```

- [ ] **Step 3: 動作確認**

Run: `cd /workspaces/spike-agentcore-evaluations/terraform/main && terraform validate`
Expected: `Success! The configuration is valid.`

Run: `terraform plan`
Expected: `aws_s3_bucket.kb_source`, `aws_s3_bucket_public_access_block.kb_source`, `aws_s3_object.mcdonalds_menu` の3リソースが作成予定として表示される

- [ ] **Step 4: コミット**

```bash
git add data/mcdonalds_menu.md terraform/main/s3.tf
git commit -m "feat: メニューデータとKBソースバケットを追加"
```

---

### Task 4: S3 Vectors(ベクトルストア)構築

**Files:**
- Create: `terraform/main/s3_vectors.tf`

**Interfaces:**
- Consumes: `var.project_name`(Task 2)
- Produces: `aws_s3vectors_index.menu.index_arn`(Task 5のKnowledge Base定義から参照される)

- [ ] **Step 1: s3_vectors.tfを作成**

```hcl
# terraform/main/s3_vectors.tf
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
```

- [ ] **Step 2: 動作確認**

Run: `terraform validate && terraform plan`
Expected: `aws_s3vectors_vector_bucket.menu`, `aws_s3vectors_index.menu` が作成予定として表示される

- [ ] **Step 3: コミット**

```bash
git add terraform/main/s3_vectors.tf
git commit -m "feat: S3 Vectorsベクトルストアを追加"
```

---

### Task 5: IAMロールとBedrock Knowledge Base構築、ingestion実行

**Files:**
- Create: `terraform/main/iam.tf`
- Create: `terraform/main/knowledge_base.tf`
- Create: `terraform/main/outputs.tf`

**Interfaces:**
- Consumes: `aws_s3_bucket.kb_source`(Task 3)、`aws_s3vectors_index.menu`(Task 4)
- Produces: `output.knowledge_base_id`、`output.data_source_id` — Task 8の評価スクリプトとTask 6のエージェント設定が参照する

- [ ] **Step 1: iam.tfを作成**

```hcl
# terraform/main/iam.tf
data "aws_caller_identity" "current" {}

# Knowledge Baseがモデル/S3/S3 Vectorsにアクセスするためのロール
resource "aws_iam_role" "kb" {
  name = "${var.project_name}-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "kb_model_invocation" {
  name = "model-invocation"
  role = aws_iam_role.kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel"]
      Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
    }]
  })
}

resource "aws_iam_role_policy" "kb_s3_source" {
  name = "s3-source-access"
  role = aws_iam_role.kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.kb_source.arn, "${aws_s3_bucket.kb_source.arn}/*"]
    }]
  })
}

resource "aws_iam_role_policy" "kb_s3vectors" {
  name = "s3vectors-access"
  role = aws_iam_role.kb.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3vectors:PutVectors",
        "s3vectors:GetVectors",
        "s3vectors:DeleteVectors",
        "s3vectors:QueryVectors",
        "s3vectors:GetIndex",
      ]
      Resource = aws_s3vectors_index.menu.index_arn
    }]
  })
}
```

- [ ] **Step 2: knowledge_base.tfを作成**

```hcl
# terraform/main/knowledge_base.tf
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
```

- [ ] **Step 3: outputs.tfを作成**

```hcl
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
```

- [ ] **Step 4: terraform apply実行**

```bash
cd /workspaces/spike-agentcore-evaluations/terraform/main
terraform apply
```

Expected: `Apply complete!` と3つのoutputが表示される

- [ ] **Step 5: ingestion実行**

```bash
KB_ID=$(terraform output -raw knowledge_base_id)
DS_ID=$(terraform output -raw data_source_id)

JOB_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --region ap-northeast-1 --query 'ingestionJob.ingestionJobId' --output text)

aws bedrock-agent get-ingestion-job \
  --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --ingestion-job-id "$JOB_ID" --region ap-northeast-1
```

Expected: `status`が`COMPLETE`になるまで数回リトライ(`STARTING`→`IN_PROGRESS`→`COMPLETE`)

- [ ] **Step 6: 検索動作確認**

```bash
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id "$KB_ID" \
  --retrieval-query '{"text":"ビッグマックのカロリーは?"}' \
  --region ap-northeast-1
```

Expected: `retrievalResults`に「ビッグマック」を含むチャンクが返る

- [ ] **Step 7: コミット**

```bash
git add terraform/main/iam.tf terraform/main/knowledge_base.tf terraform/main/outputs.tf
git commit -m "feat: Bedrock Knowledge Baseとデータソースを追加"
```

---

### Task 6: Strandsエージェント実装とローカル動作確認

**Files:**
- Create: `src/tools/__init__.py`
- Create: `src/tools/temperature.py`
- Create: `src/agent.py`
- Create: `src/main.py`

**Interfaces:**
- Consumes: 環境変数`KNOWLEDGE_BASE_ID`(Task 5のTerraform output)
- Produces: `src.agent.build_agent() -> strands.Agent`(Task 8の評価スクリプトが使用する)

- [ ] **Step 1: temperature.pyを作成**

```python
# src/tools/temperature.py
"""都道府県の気温を返すダミーツール。"""

import hashlib

from strands import tool


@tool
def get_temperature(prefecture: str) -> str:
    """指定した都道府県の気温を返す(サンプルのためダミー値)。

    Args:
        prefecture: 都道府県名(例: 東京都)
    """
    seed = int(hashlib.sha256(prefecture.encode()).hexdigest(), 16)
    temperature = 5 + seed % 26
    return f"{prefecture}の気温は{temperature}度です。"
```

`src/tools/__init__.py`は空ファイルでよい。

- [ ] **Step 2: agent.pyを作成**

```python
# src/agent.py
"""エージェント定義: モデル・システムプロンプト・3ツールを組み立てる。"""

from strands import Agent
from strands.models import BedrockModel
from strands_tools import python_repl, retrieve

from src.tools.temperature import get_temperature

MODEL_ID = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0"

SYSTEM_PROMPT = (
    "あなたは計算・気温確認・マクドナルドのメニュー成分検索ができるアシスタントです。"
    "計算にはpython_replを、気温にはget_temperatureを、"
    "メニューの栄養成分に関する質問にはretrieveを使ってください。"
)


def build_agent() -> Agent:
    """3ツールを登録したエージェントを組み立てて返す。"""
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        tools=[python_repl, get_temperature, retrieve],
        system_prompt=SYSTEM_PROMPT,
    )
```

- [ ] **Step 3: main.pyを作成**

```python
# src/main.py
"""CLIエントリポイント: 引数のプロンプトをエージェントに渡して応答を表示する。"""

import os
import sys

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from src.agent import build_agent  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: python -m src.main '<質問>'")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    agent = build_agent()
    response = agent(prompt)
    print(response)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 動作確認(計算ツール)**

```bash
export KNOWLEDGE_BASE_ID=$(terraform -chdir=terraform/main output -raw knowledge_base_id)
export AWS_REGION=ap-northeast-1
uv run python -m src.main "123 * 456 を計算して"
```

Expected: 応答に`56088`が含まれる

- [ ] **Step 5: 動作確認(気温ツール)**

```bash
uv run python -m src.main "東京都の気温を教えて"
```

Expected: 応答に気温の数値が含まれる

- [ ] **Step 6: 動作確認(RAGツール)**

```bash
uv run python -m src.main "ビッグマックのカロリーを教えて"
```

Expected: 応答に`524`(kcal)が含まれる

- [ ] **Step 7: コミット**

```bash
git add src/agent.py src/main.py src/tools/
git commit -m "feat: Strandsエージェントと3ツールを実装"
```

---

### Task 7: CloudWatch Transaction Search有効化とOTEL計装ヘルパー

**Files:**
- Create: `src/telemetry.py`
- Create: `scripts/otel_env.sh`

**Interfaces:**
- Produces: `src.telemetry.session_scope(session_id: str)`(コンテキストマネージャ。Task 6の`main.py`とTask 8の`run_evaluation.py`から利用される)

- [ ] **Step 1: CloudWatch Transaction Searchを有効化(アカウントに一度だけ実施)**

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws logs put-resource-policy --policy-name AgentCoreEvaluationsTransactionSearch \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"TransactionSearchXRayAccess\",\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"xray.amazonaws.com\"},\"Action\":\"logs:PutLogEvents\",\"Resource\":[\"arn:aws:logs:ap-northeast-1:${ACCOUNT_ID}:log-group:aws/spans:*\",\"arn:aws:logs:ap-northeast-1:${ACCOUNT_ID}:log-group:/aws/application-signals/data:*\"],\"Condition\":{\"ArnLike\":{\"aws:SourceArn\":\"arn:aws:xray:ap-northeast-1:${ACCOUNT_ID}:*\"},\"StringEquals\":{\"aws:SourceAccount\":\"${ACCOUNT_ID}\"}}}]}" \
  --region ap-northeast-1

aws xray update-trace-segment-destination --destination CloudWatchLogs --region ap-northeast-1

aws xray update-indexing-rule --name "Default" \
  --rule '{"Probabilistic": {"DesiredSamplingPercentage": 100}}' \
  --region ap-northeast-1
```

- [ ] **Step 2: 動作確認**

Run: `aws xray get-trace-segment-destination --region ap-northeast-1`
Expected: `"Destination": "CloudWatchLogs"`, `"Status": "ACTIVE"`(反映まで数分かかる場合がある)

- [ ] **Step 3: telemetry.pyを作成**

```python
# src/telemetry.py
"""OTELのsession.id baggageをスパンに伝播させるヘルパー。"""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import baggage, context


@contextmanager
def session_scope(session_id: str) -> Iterator[None]:
    """このスコープ内で生成されるスパンにsession.idを付与する。"""
    token = context.attach(baggage.set_baggage("session.id", session_id))
    try:
        yield
    finally:
        context.detach(token)
```

- [ ] **Step 4: main.pyをsession_scope対応に更新**

```python
# src/main.py
"""CLIエントリポイント: 引数のプロンプトをエージェントに渡して応答を表示する。"""

import os
import sys
import uuid

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from src.agent import build_agent  # noqa: E402
from src.telemetry import session_scope  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: python -m src.main '<質問>'")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    session_id = str(uuid.uuid4())
    agent = build_agent()
    with session_scope(session_id):
        response = agent(prompt)
    print(response)
    print(f"session_id: {session_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: otel_env.shを作成**

```bash
#!/usr/bin/env bash
# ADOT計装に必要な環境変数をエクスポートする。`source scripts/otel_env.sh`で読み込む。
set -euo pipefail

export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_RESOURCE_ATTRIBUTES=service.name=agentcore-evaluations-demo
export AWS_REGION=ap-northeast-1
export KNOWLEDGE_BASE_ID=$(terraform -chdir="$(dirname "${BASH_SOURCE[0]}")/../terraform/main" output -raw knowledge_base_id)
```

- [ ] **Step 6: 動作確認**

```bash
chmod +x scripts/otel_env.sh
source scripts/otel_env.sh
opentelemetry-instrument uv run python -m src.main "東京都の気温を教えて"
```

Expected: 応答とsession_idが表示され、エラーが出ないこと

- [ ] **Step 7: トレースがCloudWatchに届いていることを確認**

Step 6実行後、2〜3分待ってから実行:

```bash
SESSION_ID="<Step 6の出力に表示されたsession_id>"
aws logs start-query \
  --log-group-name "aws/spans" \
  --start-time "$(date -u -d '10 minutes ago' +%s)" \
  --end-time "$(date -u +%s)" \
  --query-string "fields @timestamp, @message | filter attributes.session.id = \"${SESSION_ID}\" | sort @timestamp asc" \
  --region ap-northeast-1
```

上記コマンドが返す`queryId`を使って:

```bash
aws logs get-query-results --query-id "<queryId>" --region ap-northeast-1
```

Expected: `results`に`gen_ai.operation.name`が`invoke_agent`または`execute_tool`のスパンが1件以上含まれる

- [ ] **Step 8: コミット**

```bash
git add src/telemetry.py src/main.py scripts/otel_env.sh
git commit -m "feat: OTEL計装とTransaction Search設定を追加"
```

---

### Task 8: オンデマンド評価スクリプト実装と実行

**Files:**
- Create: `evaluation/__init__.py`
- Create: `evaluation/test_cases.py`
- Create: `evaluation/run_evaluation.py`

**Interfaces:**
- Consumes: `src.agent.build_agent`(Task 6)、`src.telemetry.session_scope`(Task 7)
- Produces: 標準出力への評価結果表示(他タスクからは参照されない)

- [ ] **Step 1: test_cases.pyを作成**

```python
# evaluation/test_cases.py
"""評価用のテストクエリ(計算・気温・RAGを誘発する質問)。"""

TEST_CASES = [
    "123 * 456 を計算して",
    "東京都の気温を教えて",
    "ビッグマックのカロリーを教えて",
]
```

- [ ] **Step 2: run_evaluation.pyを作成**

```python
# evaluation/run_evaluation.py
"""テストクエリでエージェントを実行し、生成されたトレースをAgentCore
Evaluationsの組み込みエバリュエーター(正解データなし)で評価する。"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import boto3

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from src.agent import build_agent  # noqa: E402
from src.telemetry import session_scope  # noqa: E402
from evaluation.test_cases import TEST_CASES  # noqa: E402

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
LOG_GROUP = "aws/spans"

EVALUATORS = [
    "Builtin.Helpfulness",
    "Builtin.Correctness",
    "Builtin.Faithfulness",
    "Builtin.ResponseRelevance",
    "Builtin.Conciseness",
    "Builtin.Coherence",
    "Builtin.InstructionFollowing",
    "Builtin.Refusal",
    "Builtin.Harmfulness",
    "Builtin.Stereotyping",
    "Builtin.GoalSuccessRate",
    "Builtin.ToolSelectionAccuracy",
    "Builtin.ToolParameterAccuracy",
]


def query_session_span_logs(logs_client, session_id: str) -> list[dict]:
    """CloudWatch Logs InsightsでLOG_GROUPからsession.idに紐づくスパンを取得する。"""
    start_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    end_time = datetime.now(timezone.utc)
    query = (
        "fields @timestamp, @message"
        " | filter ispresent(attributes.session.id)"
        f' | filter attributes.session.id = "{session_id}"'
        " | sort @timestamp asc"
    )

    query_id = logs_client.start_query(
        logGroupName=LOG_GROUP,
        startTime=int(start_time.timestamp()),
        endTime=int(end_time.timestamp()),
        queryString=query,
    )["queryId"]

    while True:
        result = logs_client.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed"):
            break
        time.sleep(2)

    if result["status"] == "Failed":
        raise RuntimeError("CloudWatch Logs Insightsクエリが失敗しました")

    messages = []
    for row in result["results"]:
        for field in row:
            if field["field"] == "@message" and field["value"].strip().startswith("{"):
                messages.append(json.loads(field["value"]))
    return messages


def wait_for_span_logs(logs_client, session_id: str, timeout: int = 180, interval: int = 20) -> list[dict]:
    """スパンがCloudWatchに反映されるまで(最大timeout秒)ポーリングする。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        spans = query_session_span_logs(logs_client, session_id)
        if spans:
            return spans
        print(f"  スパン未反映、{interval}秒待機します...")
        time.sleep(interval)
    return []


def run_case(agentcore_client, logs_client, query: str) -> None:
    session_id = str(uuid.uuid4())
    print(f"\n=== クエリ: {query} (session_id={session_id}) ===")

    agent = build_agent()
    with session_scope(session_id):
        response = agent(query)
    print(f"応答: {response}")

    span_logs = wait_for_span_logs(logs_client, session_id)
    if not span_logs:
        print("スパンが取得できなかったため、このクエリの評価をスキップします")
        return

    for evaluator_id in EVALUATORS:
        try:
            result = agentcore_client.evaluate(
                evaluatorId=evaluator_id,
                evaluationInput={"sessionSpans": span_logs},
            )
            for entry in result.get("evaluationResults", []):
                print(f"  [{evaluator_id}] {entry}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{evaluator_id}] 評価に失敗しました: {exc}")


def main() -> None:
    agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)
    logs_client = boto3.client("logs", region_name=REGION)

    for query in TEST_CASES:
        run_case(agentcore_client, logs_client, query)


if __name__ == "__main__":
    main()
```

`evaluation/__init__.py`は空ファイルでよい。

- [ ] **Step 3: 動作確認**

```bash
source scripts/otel_env.sh
opentelemetry-instrument uv run python -m evaluation.run_evaluation
```

Expected: 3件のテストクエリそれぞれについて、応答の表示後に13種のエバリュエーターの評価結果(スコア・ラベル・説明)が表示される。一部の評価が失敗する場合はエラーメッセージが表示され、処理は継続する。

- [ ] **Step 4: コミット**

```bash
git add evaluation/
git commit -m "feat: オンデマンド評価スクリプトを実装"
```

---

### Task 9: README作成

**Files:**
- Modify: `README.md`

**Interfaces:**
- なし(ドキュメントのみ)

- [ ] **Step 1: README.mdをこのリポジトリ向けに書き換える**

既存のpython-templateの説明を、以下の内容に置き換える:
- リポジトリの目的(AgentCore Evaluations学習用)
- ディレクトリ構成
- セットアップ手順: `uv sync`、tfstateバケット作成コマンド(Task 2 Step 1と同じ内容)、`terraform apply`、ingestion実行(Task 5 Step 5と同じ内容)、Transaction Search有効化(Task 7 Step 1と同じ内容)
- エージェントの実行方法: `source scripts/otel_env.sh && opentelemetry-instrument uv run python -m src.main "<質問>"`
- 評価の実行方法: `source scripts/otel_env.sh && opentelemetry-instrument uv run python -m evaluation.run_evaluation`

- [ ] **Step 2: 動作確認**

READMEに記載したコマンドを上から順に実行し、記載通りに動くことを目視確認する。

- [ ] **Step 3: コミット**

```bash
git add README.md
git commit -m "docs: セットアップ・実行手順を記載"
```

## Self-Review

- **spec coverage**: 設計ドキュメントの各セクション(エージェント実装/KB/評価/Terraform/着手順序)は Task 1〜9 でそれぞれ対応済み。
- **placeholder scan**: 「TBD」「後で実装」等の記述なし。すべてのコードブロックは実際に貼り付けて動く内容。
- **type consistency**: `build_agent()`はTask 6で定義、Task 7・8で同じシグネチャで参照。`session_scope(session_id: str)`はTask 7で定義、Task 7・8で同じシグネチャで使用。`KNOWLEDGE_BASE_ID`・`AWS_REGION`環境変数名はTask 6〜8で統一。
