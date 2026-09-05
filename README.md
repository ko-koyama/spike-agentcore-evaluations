# spike-agentcore-evaluations

Amazon Bedrock AgentCore Evaluations(オンデマンド評価)の学習用リポジトリ。

- Strands Agents SDKで簡単なAIエージェント(計算・気温確認・Knowledge Base検索の3ツール)を実装
- `strands-agents-evals`(`bedrock-agentcore[strands-agents-evals]`)でエージェントの実行トレースをインメモリで収集
- AgentCore Evaluationsの組み込みエバリュエーター13種を、正解データ(ground truth)なしでトレースに対して実行

対象リージョンは`ap-northeast-1`(東京)。エージェントはAgentCore Runtimeにはデプロイせず、ローカルのPythonプロセスとして実行する。

## ディレクトリ構成

```
.
├── src/
│   ├── agent.py           # Strandsエージェント定義(モデル・システムプロンプト・3ツール登録)
│   ├── tools/
│   │   └── temperature.py # 都道府県→気温を返すダミーツール
│   └── main.py            # CLIエントリポイント(固定クエリでの動作確認用)
├── evaluation/
│   ├── test_cases.py      # 評価用テストクエリ(計算・気温・RAGを誘発する質問)
│   └── run_evaluation.py  # エージェント実行→トレース取得→オンデマンド評価→結果表示
├── data/
│   └── mcdonalds_menu.md  # マクドナルドメニューの栄養成分(Knowledge Baseのソースデータ)
├── terraform/
│   └── main/               # KBソースS3・S3 Vectors・Knowledge Base・データソース(S3 backend)
└── .env.example            # .envのテンプレート
```

## セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. tfstate用S3バケットの作成(初回のみ)

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

### 3. Terraformでインフラを構築

```bash
cd terraform/main
terraform init
terraform apply -auto-approve
cd ../..
```

(`-auto-approve`を付けない場合は、確認プロンプトに`yes`と答える。)

### 4. .envファイルの作成

```bash
cp .env.example .env
terraform -chdir=terraform/main output -raw knowledge_base_id
```

`.env`の`KNOWLEDGE_BASE_ID`に、上記コマンドの出力値を設定する。インフラを再作成した場合は値を更新する。

### 5. Knowledge Baseへのデータ取り込み(ingestion)

```bash
cd terraform/main
KB_ID=$(terraform output -raw knowledge_base_id)
DS_ID=$(terraform output -raw data_source_id)
cd ../..

JOB_ID=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --region ap-northeast-1 --query 'ingestionJob.ingestionJobId' --output text)

aws bedrock-agent get-ingestion-job \
  --knowledge-base-id "$KB_ID" --data-source-id "$DS_ID" \
  --ingestion-job-id "$JOB_ID" --region ap-northeast-1
```

`status`が`COMPLETE`になるまで数回リトライする(`STARTING`→`IN_PROGRESS`→`COMPLETE`)。

## エージェントの実行方法

セットアップの手順4で作成した`.env`(`KNOWLEDGE_BASE_ID`・`AWS_REGION`)を`uv run --env-file`で読み込んで実行する。

```bash
uv run --env-file .env python -m src.main
```

## 評価の実行方法

`evaluation/run_evaluation.py`は、`evaluation/test_cases.py`の各テストクエリについてエージェントを実行し、`strands-agents-evals`(`StrandsEvalsTelemetry`)でインメモリに収集したトレースを、AgentCore Evaluationsの組み込みエバリュエーター13種(`create_strands_evaluator`が内部で`evaluate` APIを呼ぶ)に対して評価する。CloudWatchへのトレース送信やポーリングは不要。

```bash
uv run --env-file .env python -m evaluation.run_evaluation
```

正解データ(ground truth)は使用せず、13エバリュエーター × テストクエリ数ぶんの評価結果(スコア・説明)が表示される。
