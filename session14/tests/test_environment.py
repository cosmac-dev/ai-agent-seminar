"""Environment precedence checks with real Dynaconf and dummy values only."""

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


SESSION = Path(__file__).resolve().parents[1]
CONFIG = SESSION / 'src/a2a_mcp/common/config.py'
VARIABLES = (
    'A2A_TEST_VALUE',
    'OPENAI_API_KEY',
    'OPENAI_MODEL',
    'OPENAI_EMBEDDING_MODEL',
    'GOOGLE_PLACES_API_KEY',
)
SCRIPT = '''
import json, os, runpy, sys
settings = runpy.run_path(sys.argv[1])['init_environment']()
names = json.loads(sys.argv[2])
result = {name: os.environ.get(name) for name in names}
result['prefixed_setting'] = settings.get('A2A_TEST_VALUE')
result['override'] = settings.get('DOTENV_OVERRIDE_FOR_DYNACONF')
if os.environ.get('OPENAI_API_KEY'):
    from openai import OpenAI
    with OpenAI() as client:
        assert client.api_key == os.environ['OPENAI_API_KEY']
print(json.dumps(result))
'''


class EnvironmentTests(unittest.TestCase):
    def test_precedence_matrix(self):
        for state in ('unset', 'empty', 'valid'):
            for has_dotenv in (False, True):
                for override in (None, 'true', 'false'):
                    with self.subTest(state=state, dotenv=has_dotenv, override=override):
                        with tempfile.TemporaryDirectory() as folder:
                            if has_dotenv:
                                Path(folder, '.env').write_text(
                                    ''.join(f'{name}=dotenv-dummy\n' for name in VARIABLES),
                                    encoding='utf-8',
                                )
                            # Do not inherit credentials or application variables.
                            env = {'PATH': os.defpath}
                            for name in ('SYSTEMROOT', 'PYTHONPATH'):
                                if name in os.environ:
                                    env[name] = os.environ[name]
                            if state != 'unset':
                                env.update({name: '' if state == 'empty' else 'existing-dummy'
                                            for name in VARIABLES})
                            if override is not None:
                                env['DOTENV_OVERRIDE_FOR_DYNACONF'] = override
                            output = subprocess.check_output(
                                [sys.executable, '-c', SCRIPT, str(CONFIG), json.dumps(VARIABLES)],
                                cwd=folder, env=env, text=True,
                            )
                            actual = json.loads(output)
                            existing = {'unset': None, 'empty': '', 'valid': 'existing-dummy'}[state]
                            expected = ('dotenv-dummy' if has_dotenv and
                                        (override != 'false' or state == 'unset') else existing)
                            for name in VARIABLES:
                                self.assertEqual(actual[name], expected)
                            self.assertEqual(actual['prefixed_setting'], expected)
                            self.assertEqual(actual['override'], override != 'false')

    def test_studio_does_not_load_dotenv_independently(self):
        config = json.loads((SESSION / 'langgraph.json').read_text(encoding='utf-8'))
        self.assertNotIn('env', config)


class StudioEnvironmentTests(unittest.TestCase):
    def test_config_dictionary_precedes_graph_initialization(self):
        from click.testing import CliRunner
        from langgraph_cli.cli import cli

        runner = CliRunner()
        for state in ('unset', 'empty', 'valid'):
            for override in (None, 'true', 'false'):
                with self.subTest(state=state, override=override):
                    with runner.isolated_filesystem():
                        Path('.env').write_text('OPENAI_API_KEY=dotenv-dummy\n', encoding='utf-8')
                        config = {
                            'dependencies': ['.'],
                            'graphs': {'demo': 'a2a_mcp.studio_graph:make_graph'},
                        }
                        if override is not None:
                            config['env'] = {'DOTENV_OVERRIDE_FOR_DYNACONF': override}
                        Path('langgraph.json').write_text(json.dumps(config), encoding='utf-8')
                        env = {'LANGGRAPH_NO_VERSION_CHECK': 'true',
                               'LANGGRAPH_CLI_NO_ANALYTICS': '1'}
                        if state != 'unset':
                            env['OPENAI_API_KEY'] = '' if state == 'empty' else 'existing-dummy'
                        observed = []

                        def graph_import_boundary(*args, **kwargs):
                            # Use the real CLI and API environment setup; replace only
                            # Uvicorn serving so no socket, browser or API call is made.
                            settings = runpy.run_path(str(CONFIG))['init_environment']()
                            observed.append((os.environ.get('OPENAI_API_KEY'),
                                             settings.get('DOTENV_OVERRIDE_FOR_DYNACONF')))

                        with patch.dict(os.environ, env, clear=True), \
                                patch('langgraph_api.cli._resolve_port', return_value=2024), \
                                patch('uvicorn.run', side_effect=graph_import_boundary):
                            result = runner.invoke(cli, ['dev', '--no-browser', '--no-reload'])
                        self.assertEqual(result.exit_code, 0, result.output or repr(result.exception))
                        expected = ('' if state == 'empty' else 'existing-dummy') \
                            if override == 'false' and state != 'unset' else 'dotenv-dummy'
                        self.assertEqual(observed, [(expected, override != 'false')])


class StdioEnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_child_receives_override_and_empty_model(self):
        from a2a_mcp.mcp import client

        captured = []

        @asynccontextmanager
        async def fake_stdio(parameters):
            captured.append(parameters.env)
            yield object(), object()

        session = MagicMock()
        session.initialize = AsyncMock()
        manager = MagicMock()
        manager.__aenter__ = AsyncMock(return_value=session)
        manager.__aexit__ = AsyncMock(return_value=False)
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'existing-dummy',
            'OPENAI_MODEL': '',
            'DOTENV_OVERRIDE_FOR_DYNACONF': 'false',
        }, clear=True), patch.object(client, 'stdio_client', fake_stdio), \
                patch.object(client, 'ClientSession', return_value=manager):
            async with client.init_session('localhost', 10100, 'stdio'):
                pass
        self.assertEqual(captured, [{
            'OPENAI_API_KEY': 'existing-dummy',
            'OPENAI_MODEL': '',
            'DOTENV_OVERRIDE_FOR_DYNACONF': 'false',
        }])


if __name__ == '__main__':
    unittest.main()
