from __future__ import annotations

from langchain_core.tools import BaseTool

from .builtins import calculator, current_datetime, search_information


def get_default_tools() -> list[BaseTool]:
    """既定で登録するツール一覧を返す。

    新しいツールを増やすときはここに足す（または独自リストを Agent に渡す）。
    """
    return [calculator, current_datetime, search_information]


__all__ = [
    "get_default_tools",
    "calculator",
    "current_datetime",
    "search_information",
]
