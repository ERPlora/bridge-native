"""
Lightweight WebSocket server for Android.

Uses the `websockets` library directly (no FastAPI/uvicorn) to avoid
C extension compilation issues on Android via Buildozer.

This module provides the same protocol as server.py but with minimal
dependencies suitable for python-for-android.
"""

import asyncio
import json
import logging
from typing import Set

import websockets
from websockets.server import serve

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

logger = logging.getLogger('erplora.bridge')

connections: Set = set()
config = BridgeConfig()
printer_manager = PrinterManager()


async def broadcast(message: str):
    """Send a message to all connected clients."""
    disconnected = set()
    for ws in connections:
        try:
            await ws.send(message)
        except Exception:
            disconnected.add(ws)
    connections.difference_update(disconnected)


async def handle_client(websocket):
    """Handle a single WebSocket client connection."""
    connections.add(websocket)
    logger.info(f"Client connected (total: {len(connections)})")

    # Send initial status
    printers = printer_manager.get_cached_printers()
    await websocket.send(status_event(
        version=__version__,
        printers=printers,
        scanner_active=False,
    ))

    try:
        async for raw in websocket:
            await handle_message(websocket, raw)
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connections.discard(websocket)
        logger.info(f"Client disconnected (total: {len(connections)})")


async def handle_message(ws, raw: str):
    """Route incoming messages to the appropriate handler."""
    try:
        msg = parse_message(raw)
    except ValueError as e:
        await ws.send(error_event(str(e), 'parse_error'))
        return

    action = msg.get('action')
    logger.debug(f"Action: {action}")

    if action == 'get_status':
        printers = printer_manager.get_cached_printers()
        await ws.send(status_event(
            version=__version__,
            printers=printers,
            scanner_active=False,
        ))

    elif action == 'discover_printers':
        logger.info("Discovering printers...")
        loop = asyncio.get_event_loop()
        printers = await loop.run_in_executor(None, discover_all)
        printer_manager.update_cache(printers)
        await ws.send(printers_event(printers))
        logger.info(f"Found {len(printers)} printer(s)")

    elif action == 'print':
        printer_id = msg.get('printer_id')
        data = msg.get('data', {})
        job_id = msg.get('job_id') or generate_job_id()
        document_type = msg.get('document_type', 'receipt')

        if not printer_id:
            await ws.send(print_error_event(job_id, 'No printer_id specified'))
            return

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None, printer_manager.print_document, printer_id, document_type, data,
            )
            await ws.send(print_complete_event(job_id))
        except Exception as e:
            await ws.send(print_error_event(job_id, str(e)))

    elif action == 'open_drawer':
        printer_id = msg.get('printer_id')
        if not printer_id:
            await ws.send(error_event('No printer_id specified', 'missing_param'))
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, open_drawer, printer_id)
            await ws.send(drawer_opened_event(printer_id))
        except Exception as e:
            await ws.send(error_event(f"Drawer error: {e}", 'drawer_error'))

    elif action == 'test_print':
        printer_id = msg.get('printer_id')
        job_id = generate_job_id()
        if not printer_id:
            await ws.send(print_error_event(job_id, 'No printer_id specified'))
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, printer_manager.test_print, printer_id)
            await ws.send(print_complete_event(job_id))
        except Exception as e:
            await ws.send(print_error_event(job_id, str(e)))

    elif action == 'send_notification':
        title = msg.get('title', 'ERPlora')
        body = msg.get('body', '')
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _show_notification_android, title, body)
            logger.info(f"Notification sent: {title}")
        except Exception as e:
            await ws.send(error_event(f"Notification error: {e}", 'notification_error'))
            logger.error(f"Notification error: {e}")

    elif action == 'toggle_keyboard':
        visible = msg.get('visible', True)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _toggle_keyboard_android, visible)
            await ws.send(keyboard_toggled_event(visible))
            logger.info(f"Keyboard toggled: visible={visible}")
        except Exception as e:
            await ws.send(error_event(f"Keyboard error: {e}", 'keyboard_error'))
            logger.error(f"Keyboard toggle error: {e}")

    else:
        await ws.send(error_event(f"Unknown action: {action}", 'unknown_action'))


async def run_server(host: str = '0.0.0.0', port: int = 12321):
    """Start the WebSocket server."""
    logger.info(f"ERPlora Bridge v{__version__} (Android) on {host}:{port}")

    async with serve(handle_client, host, port):
        await asyncio.Future()  # Run forever


def main():
    """Entry point for Android service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    port = config.port
    # On Android, bind to 0.0.0.0 so the browser on the same device can connect
    asyncio.run(run_server('0.0.0.0', port))


def _show_notification_android(title: str, body: str):
    """Show an Android notification via pyjnius."""
    try:
        from jnius import autoclass

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        NotificationBuilder = autoclass('android.app.Notification$Builder')
        NotificationManager = autoclass('android.app.NotificationManager')

        activity = PythonActivity.mActivity
        manager = activity.getSystemService(Context.NOTIFICATION_SERVICE)

        # Android 8+ requires a notification channel
        if autoclass('android.os.Build$VERSION').SDK_INT >= 26:
            NotificationChannel = autoclass('android.app.NotificationChannel')
            channel = NotificationChannel(
                'erplora_bridge', 'ERPlora Bridge',
                NotificationManager.IMPORTANCE_DEFAULT
            )
            manager.createNotificationChannel(channel)
            builder = NotificationBuilder(activity, 'erplora_bridge')
        else:
            builder = NotificationBuilder(activity)

        builder.setContentTitle(title)
        builder.setContentText(body)
        builder.setSmallIcon(activity.getApplicationInfo().icon)
        builder.setAutoCancel(True)

        manager.notify(1, builder.build())
    except Exception as e:
        logger.error(f"Android notification failed: {e}")
        raise


def _toggle_keyboard_android(visible: bool):
    """Toggle the Android soft keyboard via pyjnius."""
    try:
        from jnius import autoclass

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Context = autoclass('android.content.Context')
        InputMethodManager = autoclass('android.view.inputmethod.InputMethodManager')

        activity = PythonActivity.mActivity
        imm = activity.getSystemService(Context.INPUT_METHOD_SERVICE)

        if visible:
            imm.toggleSoftInput(InputMethodManager.SHOW_FORCED, 0)
        else:
            view = activity.getCurrentFocus()
            if view:
                imm.hideSoftInputFromWindow(view.getWindowToken(), 0)
    except Exception as e:
        logger.error(f"Android keyboard toggle failed: {e}")
        raise


if __name__ == '__main__':
    main()
