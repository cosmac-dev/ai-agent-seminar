"""Reusable A2A client helpers for Notebook and LangGraph Studio."""

import json
import os

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    MessageSendParams,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)


DEFAULT_ORCHESTRATOR_URL = 'http://localhost:10101'


@dataclass
class OrchestratorResult:
    """Result of one streaming interaction with the Orchestrator."""

    context_id: str | None
    task_id: str | None
    state: str | None
    response: str
    events: list[dict[str, Any]]


def describe_parts(parts) -> str:
    """Convert A2A message or artifact parts into displayable text."""
    contents = []
    for part in parts:
        root = part.root
        if root.kind == 'text':
            contents.append(root.text)
        elif root.kind == 'data':
            contents.append(
                json.dumps(root.data, ensure_ascii=False, indent=2)
            )
    return '\n'.join(contents)


async def send_orchestrator_message(
    text: str,
    context_id: str | None = None,
    task_id: str | None = None,
    orchestrator_url: str | None = None,
) -> OrchestratorResult:
    """Send a message to the Orchestrator and collect its A2A event stream."""
    url = orchestrator_url or os.getenv(
        'A2A_ORCHESTRATOR_URL',
        DEFAULT_ORCHESTRATOR_URL,
    )
    message: dict[str, Any] = {
        'role': 'user',
        'parts': [{'kind': 'text', 'text': text}],
        'messageId': uuid4().hex,
    }
    if context_id:
        message['contextId'] = context_id
    if task_id:
        message['taskId'] = task_id

    state = None
    events: list[dict[str, Any]] = []
    status_messages: list[str] = []
    artifact_messages: list[str] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as httpx_client:
        card = await A2ACardResolver(
            httpx_client,
            url,
        ).get_agent_card()
        client = A2AClient(httpx_client, card)
        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )

        async for chunk in client.send_message_streaming(request):
            if not isinstance(
                chunk.root,
                SendStreamingMessageSuccessResponse,
            ):
                error = str(chunk.root.error)
                errors.append(error)
                events.append({'type': 'error', 'content': error})
                continue

            event = chunk.root.result
            if isinstance(event, Task):
                context_id = event.context_id
                task_id = event.id
                state = event.status.state.value
                events.append(
                    {
                        'type': 'task',
                        'state': state,
                        'context_id': context_id,
                        'task_id': task_id,
                    }
                )
            elif isinstance(event, TaskStatusUpdateEvent):
                state = event.status.state.value
                content = ''
                if event.status.message:
                    content = describe_parts(event.status.message.parts)
                    if content:
                        status_messages.append(content)
                events.append(
                    {
                        'type': 'status',
                        'state': state,
                        'content': content,
                    }
                )
            elif isinstance(event, TaskArtifactUpdateEvent):
                content = describe_parts(event.artifact.parts)
                if content:
                    artifact_messages.append(content)
                events.append(
                    {
                        'type': 'artifact',
                        'name': event.artifact.name,
                        'content': content,
                    }
                )

    if errors:
        state = 'failed'
        response = errors[-1]
    elif state in ('failed', 'canceled', 'rejected'):
        response = status_messages[-1] if status_messages else f'Task ended as {state}.'
    elif state == 'input-required' and status_messages:
        response = status_messages[-1]
    elif artifact_messages:
        response = artifact_messages[-1]
    elif status_messages:
        response = status_messages[-1]
    elif errors:
        response = errors[-1]
    else:
        response = 'The Orchestrator returned no displayable response.'

    return OrchestratorResult(
        context_id=context_id,
        task_id=task_id,
        state=state,
        response=response,
        events=events,
    )
