from __future__ import annotations

from typing import Any

from guarded_agent.sandbox import DEFAULT_EXECUTION_POLICY, ExecutionPolicyName
from guarded_agent.state import DEFAULT_MODEL, Context, OpenAIModelName
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.types import Command

from .graph import build_graph


def _default_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


class Agent:
    """Goal Setting、Planning、Monitoring、HITL、Sandbox 付きエージェント。"""

    def __init__(
        self,
        model: BaseChatModel | None = None,
        *,
        tools=None,
        execution_policy: ExecutionPolicyName = DEFAULT_EXECUTION_POLICY,
        checkpointer: BaseCheckpointSaver | None = None,
        store: BaseStore | None = None,
        call_model_name: OpenAIModelName = DEFAULT_MODEL,
    ) -> None:
        self.model = model or _default_model()
        self.call_model_name = call_model_name
        self.graph = build_graph(
            self.model,
            tools=tools,
            execution_policy=execution_policy,
            checkpointer=checkpointer,
            store=store,
        )

    @staticmethod
    def _config(session_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def _context(
        self,
        user_id: str,
        model: OpenAIModelName | None,
    ) -> Context:
        return Context(user_id=user_id, model=model or self.call_model_name)

    def invoke(
        self,
        query: str | dict[str, Any] | Command,
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> dict[str, Any]:
        if isinstance(query, str):
            input_value: dict[str, Any] | Command = {
                "messages": [HumanMessage(content=query)],
                "user_request": query,
            }
        else:
            input_value = query

        return self.graph.invoke(
            input_value,
            config=self._config(session_id),
            context=self._context(user_id, model),
        )

    def resume(
        self,
        resume_value: dict[str, Any],
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> dict[str, Any]:
        return self.invoke(
            Command(resume=resume_value),
            user_id=user_id,
            session_id=session_id,
            model=model,
        )

    def run(
        self,
        query: str,
        *,
        user_id: str = "default",
        session_id: str = "default",
        model: OpenAIModelName | None = None,
    ) -> str:
        result = self.invoke(
            query,
            user_id=user_id,
            session_id=session_id,
            model=model,
        )
        if "__interrupt__" in result:
            return ""
        return str(result.get("final_answer", ""))
