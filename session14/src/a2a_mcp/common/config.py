"""Load the session's .env before clients read process environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dynaconf import Dynaconf


@lru_cache(maxsize=1)
def init_environment():
    """Prefer .env by default; honor Dynaconf's explicit override setting."""
    os.environ.setdefault('DOTENV_OVERRIDE_FOR_DYNACONF', 'true')
    settings = Dynaconf(
        load_dotenv=True,
        dotenv_path=str(Path.cwd() / '.env'),
        envvar_prefix=False,
        settings_files=[],
    )
    # Dynaconf is lazy. Force loading now, including the updates to os.environ
    # that OpenAI, LangChain and LiteLLM clients consume.
    settings.get('DOTENV_OVERRIDE_FOR_DYNACONF')
    return settings
