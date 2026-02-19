"""
Hardware discovery — find printers via USB, network, and Bluetooth.
"""

import logging
import platform
import socket
from typing import Any

from ..protocol import printer_info

logger = logging.getLogger('erplora.bridge.discovery')

# Well-known ESC/POS printer USB vendor IDs
KNOWN_PRINTER_VENDORS = {
    0x04B8: 'Epson',
    0x0519: 'Star Micronics',
    0x0DD4: 'Custom',
    0x0FE6: 'Bixolon',
    0x0493: 'Citizen',
    0x20D1: 'Sewoo',
    0x0416: 'Winbond (POS)',
    0x0483: 'STMicroelectronics',
    0x1FC9: 'NXP (POS)',
    0x28E9: 'Rongta',
    0x0C2E: 'Munbyn',
    0x1A86: 'QinHeng (CH340 serial)',
}

# Default ESC/POS network port
ESCPOS_NETWORK_PORT = 9100


def discover_all() -> list[dict]:
    """Discover all available printers (USB + network + Bluetooth).

    Runs USB and mDNS discovery (fast). Skips the slow subnet port scan
    and Bluetooth BLE scan to avoid blocking for 60+ seconds.
    """
    printers = []

    printers.extend(discover_usb())
    printers.extend(_discover_mdns())

    return printers


def discover_usb() -> list[dict]:
    """Discover USB-connected ESC/POS printers."""
    printers = []

    try:
        import usb.core
    except ImportError:
        logger.warning("pyusb not available — skipping USB discovery")
        return printers

    try:
        devices = usb.core.find(find_all=True)
        if devices is None:
            return printers

        for device in devices:
            vendor_id = device.idVendor
            product_id = device.idProduct

            vendor_name = KNOWN_PRINTER_VENDORS.get(vendor_id)
            if vendor_name is None:
                continue  # Not a known printer vendor

            printer_id = f"usb:{vendor_id:#06x}:{product_id:#06x}"

            try:
                name = device.product or f"{vendor_name} Printer"
            except Exception:
                name = f"{vendor_name} Printer"

            printers.append(printer_info(
                printer_id=printer_id,
                name=name,
                printer_type='usb',
                status='ready',
            ))
            logger.debug(f"Found USB printer: {name} ({printer_id})")

    except Exception as e:
        logger.error(f"USB discovery error: {e}")

    return printers


def discover_network(
    subnet_prefix: str | None = None,
    port: int = ESCPOS_NETWORK_PORT,
    timeout: float = 0.3,
) -> list[dict]:
    """
    Discover network printers by scanning for open port 9100.

    Also uses zeroconf/mDNS if available.
    """
    printers = []

    # mDNS discovery via zeroconf
    printers.extend(_discover_mdns())

    # Simple port scan on common subnet
    if subnet_prefix is None:
        subnet_prefix = _get_local_subnet()

    if subnet_prefix:
        for i in range(1, 255):
            ip = f"{subnet_prefix}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
                sock.close()

                if result == 0:
                    printer_id = f"network:{ip}:{port}"
                    # Check if already found via mDNS
                    if not any(p['id'] == printer_id for p in printers):
                        printers.append(printer_info(
                            printer_id=printer_id,
                            name=f"Network Printer ({ip})",
                            printer_type='network',
                            status='ready',
                        ))
                        logger.debug(f"Found network printer at {ip}:{port}")
            except Exception:
                continue

    return printers


def _discover_mdns() -> list[dict]:
    """Discover printers via mDNS/Bonjour."""
    printers = []

    try:
        from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange
        import time

        found = []

        class Listener:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    found.append(info)

            def remove_service(self, zc, type_, name):
                pass

            def update_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        listener = Listener()

        # Common printer service types
        for service_type in ['_pdl-datastream._tcp.local.', '_ipp._tcp.local.']:
            ServiceBrowser(zc, service_type, listener)

        # Wait a bit for responses
        time.sleep(1.5)

        for info in found:
            addresses = info.parsed_addresses()
            if not addresses:
                continue

            ip = addresses[0]
            port = info.port or ESCPOS_NETWORK_PORT
            name = info.name.split('.')[0] if info.name else f"mDNS Printer ({ip})"
            printer_id = f"network:{ip}:{port}"

            printers.append(printer_info(
                printer_id=printer_id,
                name=name,
                printer_type='network',
                status='ready',
            ))
            logger.debug(f"Found mDNS printer: {name} at {ip}:{port}")

        zc.close()

    except ImportError:
        logger.debug("zeroconf not available — skipping mDNS discovery")
    except Exception as e:
        logger.error(f"mDNS discovery error: {e}")

    return printers


def discover_bluetooth() -> list[dict]:
    """Discover Bluetooth printers (platform-dependent)."""
    printers = []

    # Try bleak (cross-platform BLE)
    try:
        import asyncio
        from bleak import BleakScanner

        async def _scan():
            devices = await BleakScanner.discover(timeout=3.0)
            results = []
            for d in devices:
                # Filter for printer-like devices
                name = d.name or ''
                if any(kw in name.lower() for kw in ['print', 'pos', 'thermal', 'escpos', 'star', 'epson', 'bixolon']):
                    results.append(printer_info(
                        printer_id=f"bluetooth:{d.address}",
                        name=name,
                        printer_type='bluetooth',
                        status='ready',
                    ))
            return results

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run nested event loop — skip BLE
                pass
            else:
                printers = loop.run_until_complete(_scan())
        except RuntimeError:
            printers = asyncio.run(_scan())

    except ImportError:
        logger.debug("bleak not available — skipping Bluetooth discovery")
    except Exception as e:
        logger.error(f"Bluetooth discovery error: {e}")

    return printers


def _get_local_subnet() -> str | None:
    """Get the local subnet prefix (e.g., '192.168.1')."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split('.')
        return '.'.join(parts[:3])
    except Exception:
        return None


# ─── Printer Connection ─────────────────────────────────────────────────────

def parse_printer_id(printer_id: str) -> tuple[str, dict]:
    """
    Parse a printer ID into type and connection parameters.

    Examples:
        'usb:0x04b8:0x0202'    → ('usb', {'vendor_id': 0x04b8, 'product_id': 0x0202})
        'network:192.168.1.100:9100' → ('network', {'host': '192.168.1.100', 'port': 9100})
        'bluetooth:AA:BB:CC:DD:EE:FF' → ('bluetooth', {'address': 'AA:BB:CC:DD:EE:FF'})
    """
    parts = printer_id.split(':', 1)
    ptype = parts[0]
    rest = parts[1] if len(parts) > 1 else ''

    if ptype == 'usb':
        vid, pid = rest.split(':')
        return 'usb', {'vendor_id': int(vid, 16), 'product_id': int(pid, 16)}
    elif ptype == 'network':
        host_port = rest.rsplit(':', 1)
        host = host_port[0]
        port = int(host_port[1]) if len(host_port) > 1 else ESCPOS_NETWORK_PORT
        return 'network', {'host': host, 'port': port}
    elif ptype == 'bluetooth':
        return 'bluetooth', {'address': rest}
    else:
        raise ValueError(f"Unknown printer type: {ptype}")


def connect_printer(printer_id: str) -> Any:
    """
    Connect to a printer by its ID and return an escpos printer instance.
    """
    from escpos.printer import Usb, Network

    ptype, params = parse_printer_id(printer_id)

    if ptype == 'usb':
        return Usb(params['vendor_id'], params['product_id'])
    elif ptype == 'network':
        return Network(params['host'], port=params.get('port', ESCPOS_NETWORK_PORT))
    elif ptype == 'bluetooth':
        # Bluetooth serial connection
        import serial
        return serial.Serial(params['address'])
    else:
        raise ValueError(f"Cannot connect to printer type: {ptype}")
