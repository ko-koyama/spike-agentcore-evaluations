# src/agent.py
"""エージェント定義: モデル・システムプロンプト・3ツールを組み立てる。"""

import os

from strands import Agent
from strands.models import BedrockModel
from strands_tools import python_repl, retrieve

from src.tools.temperature import get_temperature

# PTYモードは本環境では出力キャプチャが失敗するため、標準出力リダイレクトへ切り替える
os.environ.setdefault("PYTHON_REPL_INTERACTIVE", "false")

MODEL_ID = "jp.anthropic.claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "retrieveはマクドナルドのバーガーメニューの栄養成分"
    "(カロリー・たんぱく質・脂質・炭水化物)を検索するナレッジベースに接続されています。"
    "python_replはコードを実行するだけで結果を自動表示しないため、"
    "計算結果は必ずprint()で出力すること。"
)


def build_agent() -> Agent:
    """3ツールを登録したエージェントを組み立てて返す。"""
    model = BedrockModel(model_id=MODEL_ID)
    return Agent(
        model=model,
        tools=[python_repl, get_temperature, retrieve],
        system_prompt=SYSTEM_PROMPT,
    )
