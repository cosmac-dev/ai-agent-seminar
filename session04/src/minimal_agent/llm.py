from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import AgentConfig


def build_llm(config: AgentConfig | None = None) -> ChatOpenAI:
    """設定に基づき ChatOpenAI を生成する。

    APIキーの存在チェックも行う（未設定なら明示的に失敗させる）。
    """
    config = config or AgentConfig()
    config.require_api_key()
    return ChatOpenAI(model=config.model, temperature=config.temperature)
