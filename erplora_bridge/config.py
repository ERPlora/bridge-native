"""
Bridge configuration management.

Config is stored in a JSON file in the user's app data directory.
"""

import json
import os
import platform
import sys
from pathlib import Path


# Default WebSocket port
DEFAULT_PORT = 12321

# Config filename
CONFIG_FILENAME = 'bridge_config.json'


def get_config_dir() -> Path:
    """Get the platform-specific config directory for ERPlora Bridge."""
    system = platform.system()

    if system == 'Darwin':
        base = Path.home() / 'Library' / 'Application Support'
    elif system == 'Windows':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        # Linux / other
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))

    config_dir = base / 'ERPloraBridge'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the full path to the config file."""
    return get_config_dir() / CONFIG_FILENAME


def get_log_dir() -> Path:
    """Get the log directory."""
    log_dir = get_config_dir() / 'logs'
    log_dir.mkdir(exist_ok=True)
    return log_dir


# Default configuration
DEFAULT_CONFIG = {
    'port': DEFAULT_PORT,
    'host': '127.0.0.1',
    'log_level': 'info',
    'scanner_enabled': True,
    'scanner_timeout_ms': 100,  # Max time between keystrokes for a scan
}


class BridgeConfig:
    """Bridge configuration with file persistence."""

    def __init__(self):
        self._path = get_config_path()
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Load config from file, creating defaults if not exists."""
        if self._path.exists():
            try:
                with open(self._path, 'r') as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass  # Use defaults on error
        else:
            self.save()

    def save(self):
        """Persist config to file."""
        with open(self._path, 'w') as f:
            json.dump(self._data, f, indent=2)

    @property
    def port(self) -> int:
        return self._data.get('port', DEFAULT_PORT)

    @port.setter
    def port(self, value: int):
        self._data['port'] = value
        self.save()

    @property
    def host(self) -> str:
        return self._data.get('host', '127.0.0.1')

    @property
    def log_level(self) -> str:
        return self._data.get('log_level', 'info')

    @property
    def scanner_enabled(self) -> bool:
        return self._data.get('scanner_enabled', True)

    @property
    def scanner_timeout_ms(self) -> int:
        return self._data.get('scanner_timeout_ms', 100)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def __repr__(self):
        return f"BridgeConfig({self._data})"
