"""
Entry point for ERPlora Bridge.

Usage:
    python -m erplora_bridge
    python -m erplora_bridge --port 12321
    erplora-bridge  (if installed via pip)
"""

import argparse
import logging
import sys

import uvicorn

from . import __version__
from .config import BridgeConfig


def setup_logging(level: str = 'info'):
    """Configure logging for the bridge."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    # Quiet down noisy loggers
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description=f'ERPlora Bridge v{__version__} — Hardware bridge for ERPlora Hub',
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=None,
        help=f'WebSocket server port (default: from config or {BridgeConfig().port})',
    )
    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Bind address (default: 127.0.0.1)',
    )
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error'],
        default=None,
        help='Logging level',
    )
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'erplora-bridge {__version__}',
    )

    args = parser.parse_args()

    config = BridgeConfig()

    port = args.port or config.port
    host = args.host or config.host
    log_level = args.log_level or config.log_level

    setup_logging(log_level)

    logger = logging.getLogger('erplora.bridge')
    logger.info(f"ERPlora Bridge v{__version__}")
    logger.info(f"Config: {config._path}")
    logger.info(f"Starting WebSocket server on {host}:{port}")

    uvicorn.run(
        'erplora_bridge.server:app',
        host=host,
        port=port,
        log_level=log_level,
        ws='websockets',
    )


if __name__ == '__main__':
    main()
