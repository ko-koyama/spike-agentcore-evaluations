# src/agent.py
"""エージェント定義: モデル・システムプロンプト・3ツールを組み立てる。"""

from strands import Agent
from strands.models import BedrockModel
from strands_tools import python_repl, retrieve

from src.tools.temperature import get_temperature

MODEL_ID = "jp.anthropic.claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "retrieveはマクドナルドのバーガーメニューの栄養成分"
    "(カロリー・たんぱく質・脂質・炭水化物)を検索するナレッジベースに接続されています。"
)


def build_agent() -> Agent:
    """3ツールを登録したエージェントを組み立てて返す。"""
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        tools=[python_repl, get_temperature, retrieve],
        system_prompt=SYSTEM_PROMPT,
    )
