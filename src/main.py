# src/main.py
"""CLIエントリポイント: 引数のプロンプトをエージェントに渡して応答を表示する。"""

import os
import sys

os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

from src.agent import build_agent  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("使い方: python -m src.main '<質問>'")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    agent = build_agent()
    response = agent(prompt)
    print(response)


if __name__ == "__main__":
    main()
