# type: ignore

import json
import logging
import os
import re

from collections.abc import AsyncIterable
from typing import Any

from a2a_mcp.common.agent_runner import AgentRunner
from a2a_mcp.common.base_agent import BaseAgent
from a2a_mcp.common.utils import get_mcp_server_config, init_api_key
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams


logger = logging.getLogger(__name__)


class TravelAgent(BaseAgent):
    """Travel Agent backed by ADK."""

    def __init__(self, agent_name: str, description: str, instructions: str):
        init_api_key()

        super().__init__(
            agent_name=agent_name,
            description=description,
            content_types=['text', 'text/plain'],
        )

        logger.info(f'Init {self.agent_name}')

        self.instructions = instructions
        self.agent = None

    async def init_agent(self):
        logger.info(f'Initializing {self.agent_name} metadata')
        config = get_mcp_server_config()
        logger.info(f'MCP Server url={config.url}')
        tools = await MCPToolset(
            connection_params=SseServerParams(url=config.url)
        ).get_tools()

        for tool in tools:
            logger.info(f'Loaded tools {tool.name}')
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        litellm_model = (
            model if model.startswith('openai/') else f'openai/{model}'
        )
        self.agent = Agent(
            name=self.agent_name,
            instruction=self.instructions,
            model=LiteLlm(model=litellm_model),
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            tools=tools,
        )
        self.runner = AgentRunner()

    async def invoke(self, query, session_id) -> dict:
        logger.info(f'Running {self.agent_name} for session {session_id}')

        raise NotImplementedError('Please use the streraming function')

    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(
            f'Running {self.agent_name} stream for session {context_id} {task_id} - {query}'
        )

        if not query:
            raise ValueError('Query cannot be empty')

        if not self.agent:
            await self.init_agent()
        async for chunk in self.runner.run_stream(
            self.agent, query, context_id
        ):
            logger.info(f'Received chunk {chunk}')
            if isinstance(chunk, dict) and chunk.get('type') == 'final_result':
                response = chunk['response']
                yield self.get_agent_response(response)
            else:
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': f'{self.agent_name}: Processing Request...',
                }

    def format_response(self, chunk):
        if not isinstance(chunk, str):
            return chunk

        text = chunk.strip()
        fenced_blocks = re.findall(
            r'```(?:json|tool_outputs)?\s*(.*?)\s*```',
            text,
            re.DOTALL | re.IGNORECASE,
        )
        candidates = [*fenced_blocks, text]
        decoder = json.JSONDecoder()

        for candidate in candidates:
            candidate = candidate.strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            # Models may add a short explanation around an otherwise valid
            # JSON object. Decode the first complete object or array.
            for marker in ('{', '['):
                start = candidate.find(marker)
                if start < 0:
                    continue
                try:
                    data, _ = decoder.raw_decode(candidate[start:])
                    return data
                except json.JSONDecodeError:
                    continue

        return text

    def get_agent_response(self, chunk):
        logger.info(f'Response Type {type(chunk)}')
        data = self.format_response(chunk)
        logger.info(f'Formatted Response {data}')
        try:
            if isinstance(data, dict):
                if 'status' in data and data['status'] == 'input_required':
                    return {
                        'response_type': 'text',
                        'is_task_complete': False,
                        'require_user_input': True,
                        'content': data['question'],
                    }
                return {
                    'response_type': 'data',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': data,
                }
            return {
                'response_type': (
                    'text' if isinstance(data, str) else 'data'
                ),
                'is_task_complete': True,
                'require_user_input': False,
                'content': data,
            }
        except Exception as e:
            logger.error(f'Error in get_agent_response: {e}')
            return {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': 'Could not complete booking / task. Please try again.',
            }
