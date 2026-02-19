"""
FastAPI WebSocket server for ERPlora Bridge.

The Hub browser connects to ws://localhost:PORT/ws to communicate
with local hardware (printers, cash drawer, barcode scanner).
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import BridgeConfig
from .protocol import (
    parse_message,
    status_event,
    printers_event,
    print_complete_event,
    print_error_event,
    drawer_opened_event,
    keyboard_toggled_event,
    error_event,
    generate_job_id,
)
from .hardware.printer import PrinterManager
from .hardware.discovery import discover_all
from .hardware.drawer import open_drawer
from .hardware.scanner import ScannerManager

logger = logging.getLogger('erplora.bridge')

# Active WebSocket connections
connections: Set[WebSocket] = set()

# Global instances
config = BridgeConfig()
printer_manager = PrinterManager()
scanner_manager: ScannerManager | None = None


async def broadcast(message: str):
    """Send a message to all connected clients."""
    disconnected = set()
    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    connections.difference_update(disconnected)


def on_barcode_scanned(value: str, barcode_type: str = 'unknown'):
    """Callback when barcode scanner detects a scan."""
    from .protocol import barcode_event
    msg = barcode_event(value, barcode_type)
    # Schedule broadcast in the event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(broadcast(msg))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global scanner_manager

    logger.info(f"ERPlora Bridge v{__version__} starting on {config.host}:{config.port}")

    # Start barcode scanner listener if enabled
    if config.scanner_enabled:
        scanner_manager = ScannerManager(
            callback=on_barcode_scanned,
            timeout_ms=config.scanner_timeout_ms,
        )
        scanner_manager.start()
        logger.info("Barcode scanner listener started")

    yield

    # Shutdown
    if scanner_manager:
        scanner_manager.stop()
        logger.info("Barcode scanner listener stopped")

    logger.info("ERPlora Bridge shutting down")


app = FastAPI(
    title="ERPlora Bridge",
    version=__version__,
    lifespan=lifespan,
)

# Allow browser to connect from any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
async def health_check():
    """Health check endpoint for browser detection (fetch with 500ms timeout)."""
    printers = printer_manager.get_cached_printers()
    return {
        "status": "ok",
        "version": __version__,
        "printers": len(printers),
        "scanner": scanner_manager is not None and scanner_manager.is_running,
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint for Hub <-> Bridge communication."""
    await ws.accept()
    connections.add(ws)
    logger.info(f"Client connected (total: {len(connections)})")

    # Send initial status
    printers = printer_manager.get_cached_printers()
    await ws.send_text(status_event(
        version=__version__,
        printers=printers,
        scanner_active=scanner_manager is not None and scanner_manager.is_running,
    ))

    try:
        while True:
            raw = await ws.receive_text()
            await handle_message(ws, raw)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connections.discard(ws)
        logger.info(f"Client disconnected (total: {len(connections)})")


async def handle_message(ws: WebSocket, raw: str):
    """Route incoming messages to the appropriate handler."""
    try:
        msg = parse_message(raw)
    except ValueError as e:
        await ws.send_text(error_event(str(e), 'parse_error'))
        return

    action = msg.get('action')
    logger.debug(f"Action: {action}")

    if action == 'get_status':
        await handle_get_status(ws)
    elif action == 'discover_printers':
        await handle_discover_printers(ws)
    elif action == 'print':
        await handle_print(ws, msg)
    elif action == 'open_drawer':
        await handle_open_drawer(ws, msg)
    elif action == 'test_print':
        await handle_test_print(ws, msg)
    elif action == 'send_notification':
        await handle_send_notification(ws, msg)
    elif action == 'toggle_keyboard':
        await handle_toggle_keyboard(ws, msg)
    else:
        await ws.send_text(error_event(f"Unknown action: {action}", 'unknown_action'))


async def handle_get_status(ws: WebSocket):
    """Handle get_status command."""
    printers = printer_manager.get_cached_printers()
    await ws.send_text(status_event(
        version=__version__,
        printers=printers,
        scanner_active=scanner_manager is not None and scanner_manager.is_running,
    ))


async def handle_discover_printers(ws: WebSocket):
    """Handle discover_printers command — scans for all available hardware."""
    logger.info("Discovering printers...")

    # Run discovery in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    printers = await loop.run_in_executor(None, discover_all)

    # Update printer manager cache
    printer_manager.update_cache(printers)

    await ws.send_text(printers_event(printers))
    logger.info(f"Found {len(printers)} printer(s)")


async def handle_print(ws: WebSocket, msg: dict):
    """Handle print command."""
    printer_id = msg.get('printer_id')
    data = msg.get('data', {})
    job_id = msg.get('job_id') or generate_job_id()
    document_type = msg.get('document_type', 'receipt')

    if not printer_id:
        await ws.send_text(print_error_event(job_id, 'No printer_id specified'))
        return

    # Run print job in thread pool
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            printer_manager.print_document,
            printer_id,
            document_type,
            data,
        )
        await ws.send_text(print_complete_event(job_id))
        logger.info(f"Print job {job_id} completed on {printer_id}")
    except Exception as e:
        error_msg = str(e)
        await ws.send_text(print_error_event(job_id, error_msg))
        logger.error(f"Print job {job_id} failed: {error_msg}")


async def handle_open_drawer(ws: WebSocket, msg: dict):
    """Handle open_drawer command."""
    printer_id = msg.get('printer_id')

    if not printer_id:
        await ws.send_text(error_event('No printer_id specified', 'missing_param'))
        return

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, open_drawer, printer_id)
        await ws.send_text(drawer_opened_event(printer_id))
        logger.info(f"Cash drawer opened via {printer_id}")
    except Exception as e:
        await ws.send_text(error_event(f"Drawer error: {e}", 'drawer_error'))
        logger.error(f"Drawer error: {e}")


async def handle_test_print(ws: WebSocket, msg: dict):
    """Handle test_print command — prints a test page."""
    printer_id = msg.get('printer_id')
    job_id = generate_job_id()

    if not printer_id:
        await ws.send_text(print_error_event(job_id, 'No printer_id specified'))
        return

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            printer_manager.test_print,
            printer_id,
        )
        await ws.send_text(print_complete_event(job_id))
        logger.info(f"Test print completed on {printer_id}")
    except Exception as e:
        await ws.send_text(print_error_event(job_id, str(e)))
        logger.error(f"Test print failed: {e}")


async def handle_send_notification(ws: WebSocket, msg: dict):
    """Handle send_notification command — shows OS-level notification."""
    title = msg.get('title', 'ERPlora')
    body = msg.get('body', '')

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _show_notification, title, body)
        logger.info(f"Notification sent: {title}")
    except Exception as e:
        await ws.send_text(error_event(f"Notification error: {e}", 'notification_error'))
        logger.error(f"Notification error: {e}")


def _show_notification(title: str, body: str):
    """Show an OS-level notification (platform-specific)."""
    import platform
    import subprocess
    system = platform.system()

    if system == 'Darwin':
        script = f'display notification "{body}" with title "{title}"'
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
    elif system == 'Windows':
        ps_cmd = (
            f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null; '
            f'$n = New-Object System.Windows.Forms.NotifyIcon; '
            f'$n.Icon = [System.Drawing.SystemIcons]::Information; '
            f'$n.Visible = $true; '
            f'$n.ShowBalloonTip(5000, "{title}", "{body}", "Info"); '
            f'Start-Sleep -Seconds 6; $n.Dispose()'
        )
        subprocess.run(['powershell', '-Command', ps_cmd], check=True, capture_output=True)
    else:
        # Linux: notify-send
        subprocess.run(['notify-send', title, body], check=True, capture_output=True)


async def handle_toggle_keyboard(ws: WebSocket, msg: dict):
    """Handle toggle_keyboard command — opens/closes OS virtual keyboard."""
    visible = msg.get('visible', True)

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _toggle_keyboard, visible)
        await ws.send_text(keyboard_toggled_event(visible))
        logger.info(f"Keyboard toggled: visible={visible}")
    except Exception as e:
        await ws.send_text(error_event(f"Keyboard error: {e}", 'keyboard_error'))
        logger.error(f"Keyboard toggle error: {e}")


def _toggle_keyboard(visible: bool):
    """Toggle the OS virtual keyboard (platform-specific)."""
    import platform
    import subprocess
    system = platform.system()

    if system == 'Windows':
        if visible:
            # Kill existing instances first (TabTip stays in background on Win11)
            subprocess.run(
                ['taskkill', '/IM', 'TabTip.exe', '/F'],
                capture_output=True,
            )
            import time
            time.sleep(0.3)
            # Launch modern touch keyboard
            import os
            tabtip = os.path.join(
                os.environ.get('ProgramFiles', r'C:\Program Files'),
                'Common Files', 'microsoft shared', 'ink', 'TabTip.exe',
            )
            if os.path.exists(tabtip):
                subprocess.Popen([tabtip])
            else:
                # Fallback to legacy on-screen keyboard
                subprocess.Popen(['osk.exe'])
        else:
            # Hide: kill both possible keyboards
            subprocess.run(['taskkill', '/IM', 'TabTip.exe', '/F'], capture_output=True)
            subprocess.run(['taskkill', '/IM', 'osk.exe', '/F'], capture_output=True)

    elif system == 'Darwin':
        raise RuntimeError("Virtual keyboard not supported on macOS (no touchscreen)")

    else:
        # Linux: try onboard (GNOME on-screen keyboard)
        if visible:
            subprocess.Popen(['onboard'])
        else:
            subprocess.run(['pkill', 'onboard'], capture_output=True)
