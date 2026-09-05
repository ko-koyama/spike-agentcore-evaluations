# evaluation/run_evaluation.py
"""テストクエリでエージェントを実行し、生成されたトレースをAgentCore
Evaluationsの組み込みエバリュエーター(正解データなし)で評価する。"""

import json
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from bedrock_agentcore.evaluation import create_strands_evaluator  # noqa: E402
from strands_evals import Case, Experiment  # noqa: E402
from strands_evals.telemetry import StrandsEvalsTelemetry  # noqa: E402

from evaluation.test_cases import TEST_CASES  # noqa: E402
from src.agent import build_agent  # noqa: E402

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
OUTPUT_ROOT = Path("outputs")

EVALUATOR_IDS = [
    "Builtin.Helpfulness",
    "Builtin.Correctness",
    "Builtin.Faithfulness",
    # "Builtin.ResponseRelevance",
    # "Builtin.Conciseness",
    # "Builtin.Coherence",
    # "Builtin.InstructionFollowing",
    # "Builtin.Refusal",
    # "Builtin.Harmfulness",
    # "Builtin.Stereotyping",
    "Builtin.GoalSuccessRate",
    "Builtin.ToolSelectionAccuracy",
    # "Builtin.ToolParameterAccuracy",
]


def main() -> None:
    output_dir = OUTPUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True)

    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    agent = build_agent()
    agent_outputs = []

    def task_fn(case: Case) -> dict:
        # 前のケースのスパンを引き継がないよう、実行前にクリアする
        telemetry.in_memory_exporter.clear()
        response = agent(case.input)
        trajectory = list(telemetry.in_memory_exporter.get_finished_spans())
        agent_outputs.append({"input": case.input, "output": str(response)})
        return {"output": str(response), "trajectory": trajectory}

    cases = [Case(input=query) for query in TEST_CASES]
    evaluators = []
    for evaluator_id in EVALUATOR_IDS:
        evaluator = create_strands_evaluator(evaluator_id, region=REGION)
        evaluator.name = (
            evaluator_id  # 同じクラスの複数インスタンスを結果上で区別するため
        )
        evaluators.append(evaluator)

    experiment = Experiment(cases=cases, evaluators=evaluators)
    report = experiment.run_evaluations(task_fn)

    evaluation_outputs = []
    for case, score, reason in zip(
        report.cases, report.scores, report.reasons, strict=True
    ):
        print(f"\n[{case['evaluator']}] query={case['input']!r} score={score}")
        print(f"  reason: {reason}")
        evaluation_outputs.append(
            {
                "evaluator": case["evaluator"],
                "input": case["input"],
                "score": score,
                "reason": reason,
            }
        )

    _write_json(output_dir / "agent_output.json", agent_outputs)
    _write_json(output_dir / "evaluation_output.json", evaluation_outputs)


def _write_json(path: Path, data: object) -> None:
    """データをJSONとしてファイルへ書き出す。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
