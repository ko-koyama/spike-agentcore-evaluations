# AgentCore Evaluations 学習用リポジトリ 設計

## 目的
- Amazon Bedrock AgentCore Evaluationsを学ぶため、簡単なAIエージェントを実装し、オンデマンド評価を実際に動かす
- 正解データを用意せず、組み込みエバリュエーターのみで評価する

## スコープ
- ローカル実行のエージェント + AgentCore Evaluations(オンデマンド評価)
- AgentCore Runtimeへのデプロイは対象外
- 自動テスト(pytest)は対象外(学習用の小規模リポジトリのため)

## 全体構成
```
├── src/
│   ├── agent.py          # Strandsエージェント定義(モデル・システムプロンプト・3ツール登録)
│   ├── tools/
│   │   └── temperature.py # 都道府県→気温を返すダミーツール
│   ├── telemetry.py      # ADOT(OTEL)初期化
│   └── main.py           # CLIエントリポイント(対話 or 単発クエリ)
├── evaluation/
│   ├── test_cases.py     # 評価用テストクエリ(計算/気温/RAGを誘発する質問)
│   └── run_evaluation.py # エージェント実行→トレース取得→オンデマンド評価→結果表示
├── data/
│   └── mcdonalds_menu.md # バーガーメニューの栄養成分(KBソースデータ)
├── terraform/
│   └── main/              # KBソースS3・S3 Vectors・Knowledge Base・データソース(S3 backend)
├── README.md              # tfstateバケット作成コマンド等を記載
└── pyproject.toml
```

既存の`tests/test_main.py`とテンプレの`greet`実装は本リポジトリの目的と無関係なため削除する。

## エージェント実装
- フレームワーク: Strands Agents SDK
- モデル: Claude Sonnet(`anthropic.claude-sonnet-4-5-20250929-v1:0`。on-demandスループット非対応の場合はinference profile IDに切り替え)
- リージョン: ap-northeast-1(東京) — Claude/Titan Embeddings/S3 Vectors/AgentCore Evaluationsいずれも利用可能なことを確認済み
- ツール3種:
  - `strands_tools.python_repl`(計算用)
  - 自作`get_temperature(prefecture: str)`(ダミー値を返す。都道府県名を受け取り固定/擬似的な気温を返すのみ)
  - `strands_tools.retrieve`(Bedrock Knowledge Base検索。McDonald'sメニューKBに接続)

## Bedrock Knowledge Base(RAG)
- ソースデータ: `data/mcdonalds_menu.md`
  - 抽出元: https://www.mcdonalds.co.jp/quality/allergy_Nutrition/nutrient/ のバーガーカテゴリ
  - 対象: 通年の標準バーガーメニューに加え、期間限定品(月見シリーズ等)も含める。倍尺メニュー(倍ハンバーガー等)・非バーガー品(ホットケーキ等)は除く
  - 項目: カロリー(kcal)・たんぱく質(g)・脂質(g)・炭水化物(g)の4項目のみ
- チャンク戦略: `fixed_size`(短い項目の羅列のため)
- ベクトルストア: S3 Vectors(セットアップが最も簡単)
- Embeddingモデル: `amazon.titan-embed-text-v2:0`

## 評価(AgentCore Evaluations オンデマンド)
- `src/telemetry.py`でADOT計装し、CloudWatch Transaction Search経由でトレースを収集
- `evaluation/run_evaluation.py`:
  1. `evaluation/test_cases.py`に定義したテストクエリ(計算誘発・気温誘発・メニューRAG誘発の質問)でエージェントを実行
  2. 生成されたtrace/span IDを取得
  3. 組み込みエバリュエーター13種すべて(Helpfulness, Correctness, Faithfulness, ResponseRelevance, Conciseness, Coherence, InstructionFollowing, Refusal, Harmfulness, Stereotyping, GoalSuccessRate, ToolSelectionAccuracy, ToolParameterAccuracy)を対象にEvaluate APIを呼び出す(正解データは提供せず、いずれも参照データ不要モードで実行)
  4. 結果をコンソールに表示
- AgentCore Runtimeへのデプロイ・オンライン評価・バッチ評価は対象外

## Terraform
- IaCはTerraformで記述し、tfstateはS3で管理する
- tfstate用S3バケットはTerraform化せず、AWS CLIで一度だけ作成する(コマンドはREADMEに記載)
  - バケット名: `spike-agentcore-evaluations-tfstate`
  - バージョニング有効化、パブリックアクセスブロック
- `terraform/main/`(S3バックエンドを使用)で以下を構築:
  - KBソース用S3バケット(`data/mcdonalds_menu.md`を配置)
  - S3 Vectorsバケット(KBのベクトルストア)
  - Bedrock Knowledge Base + データソース
- エージェント実行用の専用IAMロールは作成しない(開発者自身のIAMユーザー権限でローカル実行する想定)

## 着手順序
1. tfstate用S3バケットをAWS CLIで作成
2. `terraform/main/`でKB基盤を構築(S3ソースバケット→`mcdonalds_menu.md`配置→S3 Vectors→Knowledge Base→データソース作成→ingestion実行)
3. Strandsエージェントを実装し、ローカルで3ツールの動作を確認
4. ADOT計装を追加し、CloudWatch Transaction Searchを有効化
5. オンデマンド評価スクリプトを実装・実行し、13種の評価結果を確認
