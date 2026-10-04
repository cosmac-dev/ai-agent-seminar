"""Dev Container setup guidance without installing packages or reading keys."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / '.devcontainer/session14/post-create.sh'
WRAPPER = '''
cd() {
  if [[ "$1" == "/workspaces/ai-agent-seminar/session14" ]]; then
    builtin cd "$TEST_SESSION_DIR"
  else
    builtin cd "$@"
  fi
}
id() { printf '%s\\n' vscode; }
uv() {
  [[ "$*" == "sync --locked" ]] || return 99
  return "$TEST_UV_EXIT_CODE"
}
source "$1"
'''


class PostCreateTests(unittest.TestCase):
    def run_setup(self, folder, key=None, uv_exit_code=0):
        # Do not inherit credentials, BASH_ENV or the user's shell startup files.
        env = {
            'PATH': os.defpath,
            'TEST_SESSION_DIR': str(folder),
            'TEST_UV_EXIT_CODE': str(uv_exit_code),
        }
        if key is not None:
            env['OPENAI_API_KEY'] = key
        return subprocess.run(
            ['bash', '--noprofile', '--norc', '-c', WRAPPER, 'post-create-test', str(SCRIPT)],
            env=env, text=True, capture_output=True, check=False,
        )

    def test_warning_requires_both_dotenv_and_environment_key_to_be_missing(self):
        for has_dotenv in (False, True):
            for key in (None, '', 'existing-dummy'):
                with self.subTest(dotenv=has_dotenv, key=key):
                    with tempfile.TemporaryDirectory() as folder:
                        dotenv = Path(folder, '.env')
                        if has_dotenv:
                            dotenv.write_text('OPENAI_API_KEY=dotenv-dummy\n', encoding='utf-8')
                        result = self.run_setup(folder, key)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, '')
                        if not has_dotenv and not key:
                            self.assertIn('CMC_OPENAI_API_KEY', result.stderr)
                            self.assertIn('session14/.env', result.stderr)
                            self.assertIn('Dynaconf', result.stderr)
                        else:
                            self.assertEqual(result.stderr, '')
                        self.assertNotIn('--env-file', result.stderr)
                        self.assertNotIn('existing-dummy', result.stderr)
                        self.assertNotIn('dotenv-dummy', result.stderr)
                        self.assertEqual(dotenv.exists(), has_dotenv)
                        if has_dotenv:
                            self.assertEqual(dotenv.read_text(encoding='utf-8'),
                                             'OPENAI_API_KEY=dotenv-dummy\n')

    def test_sync_failure_stops_before_key_guidance(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_setup(folder, uv_exit_code=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('uv sync --locked に失敗しました', result.stderr)
        self.assertNotIn('CMC_OPENAI_API_KEY', result.stderr)


if __name__ == '__main__':
    unittest.main()
