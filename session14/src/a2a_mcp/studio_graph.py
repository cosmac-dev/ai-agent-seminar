"""LangGraph gateway that lets Studio act as an A2A client UI."""

from typing import Any

from a2a_mcp.common.a2a_client import send_orchestrator_message
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph


class StudioState(MessagesState, total=False):
    """Conversation state shared between Studio and the A2A Orchestrator."""

    context_id: str | None
    task_id: str | None
    task_state: str | None
    a2a_events: list[dict[str, Any]]


def message_text(content: str | list[str | dict[str, Any]]) -> str:
    """Normalize LangGraph Studio text and content-block messages."""
    if isinstance(content, str):
        return content

    texts = []
    for block in content:
        if isinstance(block, str):
            texts.append(block)
        elif isinstance(block, dict):
            text = block.get('text')
            if isinstance(text, str):
                texts.append(text)
    if not texts:
        raise ValueError('A text message is required')
    return '\n'.join(texts)


async def call_orchestrator(state: StudioState) -> dict[str, Any]:
    """Forward the latest Studio message to the A2A Orchestrator."""
    user_message = next(
        (
            message
            for message in reversed(state['messages'])
            if isinstance(message, HumanMessage)
        ),
        None,
    )
    if user_message is None:
        raise ValueError('A user message is required')
    text = message_text(user_message.content)

    is_resume = state.get('task_state') == 'input-required'
    result = await send_orchestrator_message(
        text,
        context_id=state.get('context_id') if is_resume else None,
        task_id=state.get('task_id') if is_resume else None,
    )

    return {
        'messages': [AIMessage(content=result.response)],
        'context_id': result.context_id,
        'task_id': result.task_id,
        'task_state': result.state,
        'a2a_events': result.events,
    }


def make_graph():
    """Build the Studio UI gateway without changing the A2A agents."""
    builder = StateGraph(StudioState)
    builder.add_node('orchestrator', call_orchestrator)
    builder.add_edge(START, 'orchestrator')
    builder.add_edge('orchestrator', END)
    return builder.compile()
