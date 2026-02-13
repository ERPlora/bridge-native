"""
Barcode scanner input handler.

USB barcode scanners typically work as HID keyboard devices — they send
keystrokes very rapidly. This module detects rapid keystroke sequences
and identifies them as barcode scans.

The scanner runs in a background thread and calls a callback function
when a barcode is detected.
"""

import logging
import platform
import threading
import time
from typing import Callable

logger = logging.getLogger('erplora.bridge.scanner')


class ScannerManager:
    """
    Listens for barcode scanner input and emits events.

    Barcode scanners send characters very fast (entire barcode in < 100ms),
    ending with Enter/Return. We detect this pattern to distinguish scans
    from normal keyboard input.
    """

    def __init__(
        self,
        callback: Callable[[str, str], None],
        timeout_ms: int = 100,
    ):
        """
        Args:
            callback: Function called with (barcode_value, barcode_type) on scan
            timeout_ms: Max time between keystrokes to be considered a scan
        """
        self._callback = callback
        self._timeout = timeout_ms / 1000.0  # Convert to seconds
        self._thread: threading.Thread | None = None
        self._running = False
        self._buffer = ''
        self._last_keystroke_time = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        """Start listening for barcode scans in a background thread."""
        if self._running:
            return

        system = platform.system()

        if system == 'Darwin':
            self._start_macos()
        elif system == 'Linux':
            self._start_linux()
        elif system == 'Windows':
            self._start_windows()
        else:
            logger.warning(f"Scanner not supported on {system}")

    def stop(self):
        """Stop the scanner listener."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _on_char(self, char: str):
        """Process a character from the scanner input."""
        now = time.time()

        # If too much time passed since last char, reset buffer
        if self._buffer and (now - self._last_keystroke_time) > self._timeout:
            self._buffer = ''

        self._last_keystroke_time = now

        if char in ('\n', '\r'):
            # End of scan — process buffer
            if len(self._buffer) >= 4:  # Minimum barcode length
                barcode = self._buffer.strip()
                barcode_type = self._detect_barcode_type(barcode)
                logger.info(f"Barcode scanned: {barcode} ({barcode_type})")
                self._callback(barcode, barcode_type)
            self._buffer = ''
        else:
            self._buffer += char

    @staticmethod
    def _detect_barcode_type(value: str) -> str:
        """Guess the barcode type from the value."""
        if value.isdigit():
            length = len(value)
            if length == 13:
                return 'EAN13'
            elif length == 8:
                return 'EAN8'
            elif length == 12:
                return 'UPC-A'
            elif length == 14:
                return 'GTIN-14'
        if len(value) <= 43 and all(c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%' for c in value.upper()):
            return 'CODE39'
        return 'CODE128'  # Default assumption

    # ─── Platform-specific listeners ─────────────────────────────────────

    def _start_macos(self):
        """macOS: Use a simple stdin-based approach or IOKit HID."""
        # For development, we use a simpler approach: read from a dedicated
        # HID device file or use keyboard hook. In production, this would
        # use IOKit via pyobjc for dedicated HID device reading.
        #
        # For now, scanners connected via USB HID work as keyboard input,
        # which the browser captures directly. This background listener
        # is for cases where the browser doesn't have focus.
        self._running = True
        logger.info("Scanner listener started (macOS — keyboard mode)")

        # The browser handles keyboard-mode scanners natively via JS.
        # This thread monitors for non-keyboard HID devices if needed.
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name='scanner-monitor',
        )
        self._thread.start()

    def _start_linux(self):
        """Linux: Read from /dev/input/ device via evdev."""
        self._running = True

        def _read_evdev():
            try:
                import evdev
            except ImportError:
                logger.warning("evdev not available — scanner disabled on Linux")
                return

            # Find scanner device (usually has 'scanner' or 'barcode' in name)
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            scanner_device = None

            for dev in devices:
                name_lower = dev.name.lower()
                if any(kw in name_lower for kw in ['scanner', 'barcode', 'reader', 'hid']):
                    scanner_device = dev
                    break

            if not scanner_device:
                logger.info("No dedicated scanner device found (scanners may work via keyboard)")
                return

            logger.info(f"Listening on scanner device: {scanner_device.name}")

            scancodes = {
                2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
                7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
                28: '\n',
            }

            for event in scanner_device.read_loop():
                if not self._running:
                    break
                if event.type == 1 and event.value == 1:  # KEY_DOWN
                    char = scancodes.get(event.code, '')
                    if char:
                        self._on_char(char)

        self._thread = threading.Thread(target=_read_evdev, daemon=True, name='scanner-evdev')
        self._thread.start()

    def _start_windows(self):
        """Windows: Use keyboard hook to detect rapid input."""
        self._running = True

        def _keyboard_hook():
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32

                WH_KEYBOARD_LL = 13
                WM_KEYDOWN = 0x0100

                HOOKPROC = ctypes.CFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_int,
                    wintypes.WPARAM,
                    wintypes.LPARAM,
                )

                @HOOKPROC
                def low_level_handler(nCode, wParam, lParam):
                    if nCode >= 0 and wParam == WM_KEYDOWN:
                        vk_code = ctypes.cast(lParam, ctypes.POINTER(ctypes.c_ulong)).contents.value
                        # Map virtual key codes to characters
                        if 0x30 <= vk_code <= 0x39:  # 0-9
                            self._on_char(chr(vk_code))
                        elif 0x41 <= vk_code <= 0x5A:  # A-Z
                            self._on_char(chr(vk_code))
                        elif vk_code == 0x0D:  # Enter
                            self._on_char('\n')
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)

                hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, low_level_handler, None, 0)

                msg = wintypes.MSG()
                while self._running:
                    if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                    time.sleep(0.01)

                user32.UnhookWindowsHookEx(hook)

            except Exception as e:
                logger.error(f"Windows keyboard hook error: {e}")

        self._thread = threading.Thread(target=_keyboard_hook, daemon=True, name='scanner-kbhook')
        self._thread.start()

    def _monitor_loop(self):
        """Generic monitor loop — keeps thread alive, can be extended."""
        while self._running:
            time.sleep(1.0)
