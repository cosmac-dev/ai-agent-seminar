from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """エージェントの実行設定。

    Attributes:
        model: 使用するチャットモデル名。
        temperature: 生成のランダムさ（再現性重視のため既定は 0）。
        max_iterations: ReAct ループの最大反復回数（暴走防止）。
        api_key_env: APIキーを読み取る環境変数名。
    """

    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 6
    api_key_env: str = "OPENAI_API_KEY"

    def require_api_key(self) -> str:
        """APIキーを環境変数から取得する。無ければ分かりやすいエラーを出す。"""
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"環境変数 {self.api_key_env} が未設定。"
                f"例: os.environ['{self.api_key_env}'] = getpass.getpass()"
            )
        return key
