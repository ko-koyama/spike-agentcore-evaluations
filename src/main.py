# src/main.py
"""CLIエントリポイント: 引数のプロンプトをエージェントに渡して応答を表示する。"""

import os
import sys
import uuid

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from src.agent import build_agent  # noqa: E402
from src.telemetry import session_scope  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: python -m src.main '<質問>'")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    session_id = str(uuid.uuid4())
    agent = build_agent()
    with session_scope(session_id):
        response = agent(prompt)
    print(response)
    print(f"session_id: {session_id}")


if __name__ == "__main__":
    main()
