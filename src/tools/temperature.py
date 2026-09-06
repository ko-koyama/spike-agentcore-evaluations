# src/tools/temperature.py
"""都道府県の気温を返すダミーツール。"""

import hashlib

from strands import tool


@tool
def get_temperature(prefecture: str) -> str:
    """指定した都道府県の気温を返す(サンプルのためダミー値)。

    Args:
        prefecture: 都道府県名(例: 東京都)
    """
    seed = int(hashlib.sha256(prefecture.encode()).hexdigest(), 16)
    temperature = 5 + seed % 26
    return f"{prefecture}の気温は{temperature}度です。"
