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
SPANS_LOG_GROUP = "aws/spans"
# scripts/otel_env.shでOTELログ(input/output messagesを含むイベント)の送信先として設定したロググループ
EVENTS_LOG_GROUP = "/otel/agentcore-evaluations-demo"

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


def wait_for_span_logs(logs_client, session_id: str, timeout: int = 180, interval: int = 20) -> list[dict]:
    """スパン(aws/spans)とログイベント(EVENTS_LOG_GROUP)の両方がCloudWatchに反映され、
    かつ件数が前回ポーリング時から変化しなくなる(＝取り込みが落ち着いた)まで
    (最大timeout秒)ポーリングし、結合したリストを返す。"""
    deadline = time.monotonic() + timeout
    previous_count = None
    while time.monotonic() < deadline:
        span_logs = query_log_group(logs_client, SPANS_LOG_GROUP, session_id)
        event_logs = query_log_group(logs_client, EVENTS_LOG_GROUP, session_id)
        current_count = len(span_logs) + len(event_logs)
        if span_logs and event_logs and current_count == previous_count:
            return span_logs + event_logs
        previous_count = current_count if (span_logs and event_logs) else None
        print(f"  スパン/ログイベント未反映または取り込み中、{interval}秒待機します...")
        time.sleep(interval)
    return []


def query_log_group(logs_client, log_group: str, session_id: str) -> list[dict]:
    """CloudWatch Logs Insightsでlog_groupからsession.idに紐づくレコードを取得する。"""
    start_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    end_time = datetime.now(timezone.utc)
    query = (
        "fields @timestamp, @message"
        " | filter ispresent(attributes.session.id)"
        f' | filter attributes.session.id = "{session_id}"'
        " | sort @timestamp asc"
    )

    query_id = logs_client.start_query(
        logGroupName=log_group,
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
