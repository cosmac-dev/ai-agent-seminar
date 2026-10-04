# type: ignore
import logging
import os

from a2a_mcp.common.types import ServerConfig
from a2a_mcp.common.config import init_environment


logger = logging.getLogger(__name__)


def init_api_key():
    """Validate the API key used by OpenAI clients."""
    init_environment()
    if not os.getenv('OPENAI_API_KEY'):
        logger.error('OPENAI_API_KEY is not set')
        raise ValueError('OPENAI_API_KEY is not set')


def config_logging():
    """Configure basic logging."""
    log_level = (
        os.getenv('A2A_LOG_LEVEL') or os.getenv('FASTMCP_LOG_LEVEL') or 'INFO'
    ).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))


def config_logger(logger):
    """Logger specific config, avoiding clutter in enabling all loggging."""
    # TODO: replace with env
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration."""
    return ServerConfig(
        host='localhost',
        port=10100,
        transport='sse',
        url='http://localhost:10100/sse',
    )
