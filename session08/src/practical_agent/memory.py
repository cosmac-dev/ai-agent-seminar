from __future__ import annotations

import re
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from .state import AgentState, Context

MEMORY_NAMESPACE_PREFIX = "memories"

# プロンプトに載せる関連記憶の最大件数
TOP_K = 5


def _namespace(user_id: str) -> tuple[str, str]:
    return (MEMORY_NAMESPACE_PREFIX, user_id)


def load_memory(state: AgentState, runtime: Runtime[Context]) -> AgentState:
    """長期記憶を Store から読む（グラフの入口 node）。

    現在のユーザー入力に意味的に関連する記憶だけをセマンティック検索で取得する。
    埋め込み index が無い Store でも動くよう、失敗時は全件取得にフォールバックする。
    """
    namespace = _namespace(runtime.context.user_id)

    # 直近のユーザー発話を検索クエリにする
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and msg.content:
            query = str(msg.content)
            break

    if query:
        try:
            items = runtime.store.search(namespace, query=query, limit=TOP_K)
        except Exception:  # noqa: BLE001 - index未設定などでは全件取得へ
            items = runtime.store.search(namespace)
    else:
        items = runtime.store.search(namespace)

    return {"memories": [item.value["text"] for item in items]}


class MemoryItem(BaseModel):
    """長期記憶として保存する価値のある、ユーザーに関する1件の事実。"""

    text: str = Field(
        description="三人称・簡潔・自己完結した日本語の事実文。例: 'ユーザーはPythonが好き'"
    )


class MemoryExtraction(BaseModel):
    """会話から抽出した長期記憶の候補一覧。"""

    candidates: list[MemoryItem] = Field(
        default_factory=list,
        description="保存候補のリスト。該当が無ければ空にする。",
    )


_MEMORY_EXTRACT_SYSTEM = """あなたは会話から「長期記憶として保存する価値のある情報」だけを抽出する抽出器です。

抽出する: ユーザーの恒常的な好み・プロフィール・目標・制約・重要な決定など、将来の会話でも役立つ事実。
抽出しない: 一時的な依頼、計算やツールの実行結果、その場限りの話題、アシスタント自身の発言、単なる推測。

各候補は三人称・簡潔・自己完結した日本語の事実文にする（例:「ユーザーはPythonが好き」）。
該当が無ければ空のリストを返す。"""


def make_extract_memory(model: BaseChatModel):
    """会話から保存候補を抽出する node を生成する。"""
    extractor = model.with_structured_output(MemoryExtraction)

    def extract_memory(state: AgentState) -> AgentState:
        transcript_lines: list[str] = []
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage) and msg.content:
                transcript_lines.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage) and msg.content:
                transcript_lines.append(f"Assistant: {msg.content}")

        if not transcript_lines:
            return {"memory_candidates": []}

        transcript = "\n".join(transcript_lines)

        try:
            result = extractor.invoke(
                [
                    SystemMessage(content=_MEMORY_EXTRACT_SYSTEM),
                    HumanMessage(
                        content=f"次の会話から長期記憶の保存候補を抽出してください。\n\n{transcript}"
                    ),
                ]
            )
            candidates = [c.text.strip() for c in result.candidates if c.text.strip()]
        except Exception:  # noqa: BLE001 - 失敗時は安全側に倒し保存しない
            candidates = []

        return {"memory_candidates": candidates}

    return extract_memory


# 長期保存すべきでないセンシティブ情報（PII等）を検出する正規表現
_SENSITIVE_PATTERNS = [
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),  # クレジットカード番号
    re.compile(r"\b\d{2,4}-\d{2,4}-\d{3,4}\b"),  # 電話番号など
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),  # メールアドレス
    re.compile(r"パスワード|password|秘密の質問|暗証番号", re.I),  # 認証情報
]


def _normalize(text: str) -> str:
    """重複判定用に表記ゆれを吸収して正規化する。"""
    return re.sub(r"\s+", "", text).strip().lower()


def is_sensitive(text: str) -> bool:
    """保存すべきでないセンシティブ情報（PII・認証情報）を含むか判定する。"""
    return any(p.search(text) for p in _SENSITIVE_PATTERNS)


def validate_memory(state: AgentState) -> AgentState:
    """保存候補を検証する。

    ポリシー（センシティブ情報）・重複をチェックし、
    保存してよいものだけを approved_memories に残す。
    """
    approved: list[str] = []
    seen = {_normalize(m) for m in state["memories"]}

    for candidate in state["memory_candidates"]:
        key = _normalize(candidate)
        if not key or key in seen:
            continue
        if is_sensitive(candidate):
            continue
        approved.append(candidate)
        seen.add(key)

    return {"approved_memories": approved}


def write_memory(state: AgentState, runtime: Runtime[Context]) -> AgentState:
    """検証済みの記憶だけを Store へ保存する。"""
    namespace = _namespace(runtime.context.user_id)

    for memory in state["approved_memories"]:
        runtime.store.put(
            namespace,
            str(uuid4()),
            {"text": memory, "source": "conversation"},
        )

    return {}
