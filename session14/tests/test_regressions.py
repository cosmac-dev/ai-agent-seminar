"""Regression checks without LLM calls or external services."""
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from a2a.types import (
    AgentCard,
    SendMessageRequest,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a_mcp.common.agent_executor import GenericAgentExecutor
from a2a_mcp.common.workflow import (
    Status, WorkflowExecutionError, WorkflowGraph, WorkflowNode,
)
from a2a_mcp.mcp import server


class TravelQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'travel.db'
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE hotels (name TEXT)')
            conn.execute("INSERT INTO hotels VALUES ('Demo Hotel')")
        self.patch = patch.object(server, 'SQLLITE_DB', str(self.path))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_success_returns_structured_result(self):
        self.assertEqual(server.query_travel_data('SELECT name FROM hotels'),
                         {'results': [{'name': 'Demo Hotel'}]})

    def test_missing_column_returns_serializable_error(self):
        result = server.query_travel_data('SELECT missing FROM hotels')
        self.assertIn('schema', result['error'])
        json.dumps(result)

    def test_missing_table_returns_serializable_error(self):
        result = server.query_travel_data('SELECT * FROM missing')
        self.assertIn('no such table', result['error'])
        json.dumps(result)

    def test_write_is_rejected_and_database_unchanged(self):
        self.assertIn('error', server.query_travel_data('DELETE FROM hotels'))
        self.assertEqual(server.query_travel_data('SELECT count(*) AS n FROM hotels'),
                         {'results': [{'n': 1}]})

    def test_missing_database_is_not_created(self):
        missing = Path(self.temp.name) / 'missing.db'
        with patch.object(server, 'SQLLITE_DB', str(missing)):
            self.assertIn('error', server.query_travel_data('SELECT 1'))
        self.assertFalse(missing.exists())


def event(state):
    return SimpleNamespace(root=SendStreamingMessageSuccessResponse(
        id='rpc', result=TaskStatusUpdateEvent(
            task_id='task', context_id='context',
            status=TaskStatus(state=state), final=True,
        ),
    ))


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def run_events(self, chunks):
        graph = WorkflowGraph()
        node = WorkflowNode('mock task')
        graph.add_node(node)
        async def fake_run(*args):
            for chunk in chunks:
                yield chunk
        node.run_node = fake_run
        self.graph, self.node = graph, node
        return [chunk async for chunk in graph.run_workflow()]

    async def test_completed_is_success(self):
        await self.run_events([event(TaskState.completed)])
        self.assertEqual(self.graph.state, Status.COMPLETED)

    async def test_input_required_pauses(self):
        await self.run_events([event(TaskState.input_required)])
        self.assertEqual(self.graph.state, Status.PAUSED)
        self.assertEqual(self.graph.paused_node_id, self.node.id)

    async def test_terminal_failures_do_not_become_completed(self):
        for state in (TaskState.failed, TaskState.canceled, TaskState.rejected):
            with self.subTest(state=state):
                with self.assertRaises(WorkflowExecutionError):
                    await self.run_events([event(state)])
                self.assertEqual(self.graph.state, Status.FAILED)
                self.assertEqual(self.node.state, Status.FAILED)

    async def test_rpc_error_is_failure(self):
        with self.assertRaises(WorkflowExecutionError):
            await self.run_events([SimpleNamespace(root=SimpleNamespace(error='failure'))])
        self.assertEqual(self.graph.state, Status.FAILED)

    async def test_truncated_stream_is_failure(self):
        with self.assertRaises(WorkflowExecutionError):
            await self.run_events([])
        self.assertEqual(self.graph.state, Status.FAILED)


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_error_emits_failed_without_completion(self):
        async def failing_stream(*args):
            raise WorkflowExecutionError('downstream failed')
            yield  # async generator
        agent = SimpleNamespace(agent_name='test', stream=failing_stream)
        context = SimpleNamespace(
            current_task=Task(id='task', context_id='context',
                              status=TaskStatus(state=TaskState.working)),
            get_user_input=lambda: 'test',
        )
        updater = SimpleNamespace(update_status=AsyncMock(), complete=AsyncMock(),
                                  add_artifact=AsyncMock())
        with patch('a2a_mcp.common.agent_executor.TaskUpdater', return_value=updater):
            await GenericAgentExecutor(agent).execute(context, AsyncMock())
        self.assertEqual(updater.update_status.await_args.args[0], TaskState.failed)
        self.assertTrue(updater.update_status.await_args.kwargs['final'])
        updater.complete.assert_not_awaited()
        updater.add_artifact.assert_not_awaited()


class LessonCompatibilityTests(unittest.TestCase):
    def test_json_examples_validate_against_installed_sdk(self):
        root = Path(__file__).resolve().parents[1]
        notebook = json.loads((root / 'session14_a2a.ipynb').read_text())
        models = {'message/send': SendMessageRequest,
                  'message/stream': SendStreamingMessageRequest}
        checked = 0
        for cell in notebook['cells']:
            if cell['cell_type'] != 'markdown':
                continue
            for source in re.findall(r'```json\n(.*?)\n```', ''.join(cell['source']), re.S):
                data = json.loads(source)
                model = models[data['method']] if 'method' in data else AgentCard
                model.model_validate(data)
                checked += 1
        self.assertEqual(checked, 3)

    def test_all_demo_cards_validate(self):
        root = Path(__file__).resolve().parents[1]
        cards = list((root / 'agent_cards').glob('*.json'))
        self.assertEqual(len(cards), 5)
        for path in cards:
            with self.subTest(card=path.name):
                card = AgentCard.model_validate_json(path.read_text())
                self.assertTrue(card.capabilities.streaming)


if __name__ == '__main__':
    unittest.main()
