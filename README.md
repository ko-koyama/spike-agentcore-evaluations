# spike-agentcore-evaluations

- Amazon Bedrock AgentCore Evaluations(オンデマンド評価)の学習用リポジトリ
- Strands Agents SDKで簡単なAIエージェント(計算・気温確認・Knowledge Base検索の3ツール)を実装
- `strands-agents-evals`(`bedrock-agentcore[strands-agents-evals]`)でエージェントの実行トレースをインメモリで収集
- AgentCore Evaluationsの組み込みエバリュエーターを、正解データ(ground truth)なしでトレースに対して実行

## ディレクトリ構成

```
.
├── src/
│   ├── agent.py           # Strandsエージェント定義(モデル・システムプロンプト・3ツール登録)
│   ├── tools/
│   │   └── temperature.py # 都道府県→気温を返すダミーツール
│   └── main.py            # CLIエントリポイント
├── evaluation/
│   ├── test_cases.py      # 評価用テストクエリ
│   └── run_evaluation.py  # エージェント実行→トレース取得→オンデマンド評価→結果表示
├── data/
│   └── mcdonalds_menu.md  # マクドナルドメニューの栄養成分(Knowledge Baseのソースデータ)
├── terraform/
│   └── main/               # KBソースS3・S3 Vectors・Knowledge Base・データソース(S3 backend)
├── outputs/                # 評価実行結果
└── .env.example            # .envのテンプレート
```

## セットアップ

### 開発環境

- devcontainerで開発を行う
- 依存パッケージのインストール・pre-commitフックの有効化は`postCreateCommand`で自動実行される

### .envファイルの作成

```bash
cp .env.example .env
terraform -chdir=terraform/main output -raw knowledge_base_id
```

- `.env`の`KNOWLEDGE_BASE_ID`に、上記コマンドの出力値を設定する
- インフラを再作成した場合は値を更新する

## デプロイ手順

### 1. tfstate用S3バケットの作成(初回のみ)

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

### 2. Terraformでインフラを構築

```bash
cd terraform/main && terraform init && terraform apply
```

### 3. Knowledge Baseへのデータ取り込み(ingestion)

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
- Terraformの管理外のため、AWS CLIで実行する
- `status`が`COMPLETE`になるまで数回リトライする(`STARTING`→`IN_PROGRESS`→`COMPLETE`)

## エージェントの実行方法
```bash
uv run --env-file .env python -m src.main
```

## 評価の実行方法
```bash
uv run --env-file .env python -m evaluation.run_evaluation
```

- 正解データ(ground truth)は使用しない
- 組み込みエバリュエーターのうち、`evaluation/run_evaluation.py`の`EVALUATOR_IDS`で有効化した5種(Helpfulness・Correctness・Faithfulness・GoalSuccessRate・ToolSelectionAccuracy)を実行する
- 実行結果は`outputs/<実行日時>/`配下に`agent_output.json`(エージェントの入出力・ツール実行履歴)と`evaluation_output.json`(エバリュエーターごとのスコア・理由)としてJSON保存される
