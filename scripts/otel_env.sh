#!/usr/bin/env bash
# ADOT計装に必要な環境変数をエクスポートする。`source scripts/otel_env.sh`で読み込む。
set -euo pipefail

export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_RESOURCE_ATTRIBUTES=service.name=agentcore-evaluations-demo
export AWS_REGION=ap-northeast-1
export KNOWLEDGE_BASE_ID=$(terraform -chdir="$(dirname "${BASH_SOURCE[0]}")/../terraform/main" output -raw knowledge_base_id)

# スパンをX-Ray(Transaction Search)へ直接送るためのOTLPエンドポイント
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="https://xray.${AWS_REGION}.amazonaws.com/v1/traces"
# session.id baggageをスパン属性へ伝播させるため、Agent Observabilityを有効化
export AGENT_OBSERVABILITY_ENABLED=true

# AgentCore Evaluationsがスパンと突き合わせる「ログイベント」(input/output messages)の送信先。
# aws/spansはスパン本体のみを保持するため、自己管理エージェントでは別途ログ用ロググループを用意する必要がある。
EVENTS_LOG_GROUP="/otel/agentcore-evaluations-demo"
EVENTS_LOG_STREAM="agentcore-evaluations-demo"
aws logs create-log-group --log-group-name "$EVENTS_LOG_GROUP" --region "$AWS_REGION" 2>/dev/null || true
# OTLPログエクスポーターはログストリームを自動作成しないため、事前に作成しておく
aws logs create-log-stream --log-group-name "$EVENTS_LOG_GROUP" --log-stream-name "$EVENTS_LOG_STREAM" --region "$AWS_REGION" 2>/dev/null || true
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=${EVENTS_LOG_GROUP},x-aws-log-stream=${EVENTS_LOG_STREAM}"
