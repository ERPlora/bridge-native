"""
WebSocket protocol definitions for Hub <-> Bridge communication.

All messages are JSON objects with either an 'action' key (Hub -> Bridge)
or an 'event' key (Bridge -> Hub).
"""

from dataclasses import dataclass, field, asdict
from typing import Any
import json
import uuid


# ─── Hub → Bridge (Commands) ────────────────────────────────────────────────

ACTIONS = {
    'get_status',
    'discover_printers',
    'print',
    'open_drawer',
    'test_print',
    'send_notification',
    'toggle_keyboard',
}


def make_command(action: str, **kwargs) -> str:
    """Create a JSON command string to send to the bridge."""
    msg = {'action': action, **kwargs}
    return json.dumps(msg)


# ─── Bridge → Hub (Events) ──────────────────────────────────────────────────

def status_event(version: str, printers: list, scanner_active: bool = False) -> str:
    return json.dumps({
        'event': 'status',
        'version': version,
        'printers': printers,
        'scanner': scanner_active,
    })


def printers_event(printers: list) -> str:
    return json.dumps({
        'event': 'printers',
        'printers': printers,
    })


def print_complete_event(job_id: str) -> str:
    return json.dumps({
        'event': 'print_complete',
        'job_id': job_id,
    })


def print_error_event(job_id: str, error: str) -> str:
    return json.dumps({
        'event': 'print_error',
        'job_id': job_id,
        'error': error,
    })


def drawer_opened_event(printer_id: str) -> str:
    return json.dumps({
        'event': 'drawer_opened',
        'printer_id': printer_id,
    })


def barcode_event(value: str, barcode_type: str = 'unknown') -> str:
    return json.dumps({
        'event': 'barcode',
        'value': value,
        'type': barcode_type,
    })


def keyboard_toggled_event(visible: bool) -> str:
    return json.dumps({
        'event': 'keyboard_toggled',
        'visible': visible,
    })


def error_event(message: str, code: str = 'unknown') -> str:
    return json.dumps({
        'event': 'error',
        'message': message,
        'code': code,
    })


# ─── Parsing ────────────────────────────────────────────────────────────────

def parse_message(raw: str) -> dict:
    """Parse an incoming JSON message. Returns dict or raises ValueError."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(msg, dict):
        raise ValueError("Message must be a JSON object")

    if 'action' not in msg and 'event' not in msg:
        raise ValueError("Message must have 'action' or 'event' key")

    return msg


def generate_job_id() -> str:
    """Generate a unique job ID for print jobs."""
    return str(uuid.uuid4())


# ─── Printer info dict helper ───────────────────────────────────────────────

def printer_info(
    printer_id: str,
    name: str,
    printer_type: str,
    status: str = 'ready',
    paper_width: int = 80,
) -> dict:
    """Create a standardized printer info dict."""
    return {
        'id': printer_id,
        'name': name,
        'type': printer_type,  # 'usb', 'network', 'bluetooth'
        'status': status,      # 'ready', 'busy', 'error', 'offline'
        'paper_width': paper_width,
    }
