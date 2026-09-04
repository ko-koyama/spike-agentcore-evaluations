#!/usr/bin/env bash
# ADOT計装に必要な環境変数をエクスポートする。`source scripts/otel_env.sh`で読み込む。

TF_DIR="$(dirname "${BASH_SOURCE[0]}")/../terraform/main"

export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_RESOURCE_ATTRIBUTES=service.name=agentcore-evaluations-demo
export AWS_REGION=ap-northeast-1

KNOWLEDGE_BASE_ID=$(terraform -chdir="$TF_DIR" output -raw knowledge_base_id) || {
  echo "terraform output の取得に失敗しました。先に terraform apply を実行してください。" >&2
  return 1
}
export KNOWLEDGE_BASE_ID

# スパンをX-Ray(Transaction Search)へ直接送るためのOTLPエンドポイント
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://xray.${AWS_REGION}.amazonaws.com/v1/traces"
# session.id baggageをスパン属性へ伝播させるため、Agent Observabilityを有効化
export AGENT_OBSERVABILITY_ENABLED=true

# AgentCore Evaluationsがスパンと突き合わせる「ログイベント」(input/output messages)の送信先。
# aws/spansはスパン本体のみを保持するため、自己管理エージェントでは別途ログ用ロググループを用意する必要がある。
# ロググループ自体はTerraform(terraform/main/observability.tf)が管理する。
EVENTS_LOG_GROUP=$(terraform -chdir="$TF_DIR" output -raw events_log_group_name) || {
  echo "terraform output の取得に失敗しました。先に terraform apply を実行してください。" >&2
  return 1
}
export EVENTS_LOG_GROUP
EVENTS_LOG_STREAM="agentcore-evaluations-demo"
# OTLPログエクスポーターはログストリームを自動作成しないため、事前に作成しておく
aws logs create-log-stream --log-group-name "$EVENTS_LOG_GROUP" --log-stream-name "$EVENTS_LOG_STREAM" --region "$AWS_REGION" 2>/dev/null || true
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=${EVENTS_LOG_GROUP},x-aws-log-stream=${EVENTS_LOG_STREAM}"
