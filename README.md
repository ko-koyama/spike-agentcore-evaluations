# spike-agentcore-evaluations

Amazon Bedrock AgentCore Evaluations(オンデマンド評価)の学習用リポジトリ。

- Strands Agents SDKで簡単なAIエージェント(計算・気温確認・Knowledge Base検索の3ツール)を実装
- ADOT(OpenTelemetry)でエージェントの実行をCloudWatch(X-Ray Transaction Search)にトレースとして送信
- AgentCore Evaluationsの組み込みエバリュエーター13種を、正解データ(ground truth)なしでトレースに対して実行

対象リージョンは`ap-northeast-1`(東京)。エージェントはAgentCore Runtimeにはデプロイせず、ローカルのPythonプロセスとして実行する。

## ディレクトリ構成

```
.
├── src/
│   ├── agent.py           # Strandsエージェント定義(モデル・システムプロンプト・3ツール登録)
│   ├── tools/
│   │   └── temperature.py # 都道府県→気温を返すダミーツール
│   ├── telemetry.py       # session.id baggageをスパンに伝播させるヘルパー
│   └── main.py            # CLIエントリポイント(単発クエリ実行)
├── evaluation/
│   ├── test_cases.py      # 評価用テストクエリ(計算・気温・RAGを誘発する質問)
│   └── run_evaluation.py  # エージェント実行→トレース取得→オンデマンド評価→結果表示
├── data/
│   └── mcdonalds_menu.md  # マクドナルドメニューの栄養成分(Knowledge Baseのソースデータ)
├── terraform/
│   └── main/               # KBソースS3・S3 Vectors・Knowledge Base・データソース(S3 backend)
└── scripts/
    └── otel_env.sh         # ADOT計装に必要な環境変数を設定するスクリプト
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

### 4. Knowledge Baseへのデータ取り込み(ingestion)

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

### 5. CloudWatch Transaction Searchの有効化(アカウントに一度だけ実施)

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

反映まで数分〜十数分かかる場合がある。`aws xray get-trace-segment-destination --region ap-northeast-1`で`"Status": "ACTIVE"`になっていることを確認する。

## エージェントの実行方法

`scripts/otel_env.sh`は、トレース送信先(X-Ray)・ログイベント送信先(自己管理エージェント用のCloudWatch Logsロググループ/ストリーム。ロググループはTerraformで管理、ログストリームは未作成なら作成する)など、ADOT計装に必要な環境変数一式を設定する。

```bash
source scripts/otel_env.sh
uv run opentelemetry-instrument python -m src.main "ビッグマックのカロリーを教えて"
```

## 評価の実行方法

`evaluation/run_evaluation.py`は、`evaluation/test_cases.py`の各テストクエリについてエージェントを実行し、`aws/spans`ロググループ(スパン本体)と`scripts/otel_env.sh`が設定したロググループ(input/outputメッセージ等のログイベント)の両方をCloudWatch Logs Insightsで検索・結合してから、AgentCore Evaluationsの組み込みエバリュエーター13種に対して評価(`evaluate` API)を実行する。取り込み中のレコード欠落を避けるため、2回連続で件数が変化しなくなるまでポーリングしてから評価を行う。

```bash
source scripts/otel_env.sh
uv run opentelemetry-instrument python -m evaluation.run_evaluation
```

正解データ(ground truth)は使用せず、13エバリュエーター × テストクエリ数ぶんの評価結果(スコア・ラベル・説明)が表示される。
