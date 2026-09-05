# src/main.py
"""CLIエントリポイント: 固定のプロンプトをエージェントに渡して応答を表示する。"""

from src.agent import build_agent

PROMPT = "ビッグマックのカロリーを教えて"


def main() -> None:
    agent = build_agent()
    agent(PROMPT)


if __name__ == "__main__":
    main()
