"""
Android entry point for ERPlora Bridge.

Kivy/Buildozer requires a main.py at the app root.
This starts the WebSocket server as an Android foreground service.
"""

import os
import sys

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(__file__))


def start_service():
    """Start the bridge as an Android foreground service."""
    from erplora_bridge.server_android import main
    main()


if __name__ == '__main__':
    # When running as a service, start directly
    start_service()
