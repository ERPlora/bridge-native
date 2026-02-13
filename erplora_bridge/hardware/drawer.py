"""
Cash drawer control via ESC/POS kick commands.

Cash drawers are typically connected to the printer's DK port (pins 2 or 5).
The drawer is opened by sending an ESC/POS pulse command through the printer.
"""

import logging

from .discovery import connect_printer

logger = logging.getLogger('erplora.bridge.drawer')

# ESC/POS cash drawer kick commands
# Format: ESC p <pin> <on-time> <off-time>
# Pin 2 (connector pin 2): \x1b\x70\x00\x19\x32
# Pin 5 (connector pin 5): \x1b\x70\x01\x19\x32
KICK_PIN_2 = b'\x1b\x70\x00\x19\x32'
KICK_PIN_5 = b'\x1b\x70\x01\x19\x32'


def open_drawer(printer_id: str, pin: int = 2):
    """
    Open the cash drawer connected to the specified printer.

    Args:
        printer_id: Printer ID (e.g., 'usb:0x04b8:0x0202')
        pin: Drawer connector pin (2 or 5, default 2)
    """
    command = KICK_PIN_2 if pin == 2 else KICK_PIN_5

    printer = connect_printer(printer_id)
    try:
        printer._raw(command)
        logger.info(f"Cash drawer opened via {printer_id} (pin {pin})")
    finally:
        try:
            printer.close()
        except Exception:
            pass
