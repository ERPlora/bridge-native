# ERPlora Bridge

Native hardware bridge for ERPlora Hub. Connects the Hub browser with local printers, cash drawers, and barcode scanners via WebSocket.

## Quick Start

```bash
cd native
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run the bridge
python -m erplora_bridge

# Or with custom port
python -m erplora_bridge --port 12321
```

The bridge opens a WebSocket server on `ws://127.0.0.1:12321/ws`. The Hub browser auto-detects and connects to it.

## How It Works

```
Hub Browser ──WebSocket──► ERPlora Bridge ──USB/Network/BT──► Printer
                                          ──ESC/POS kick──► Cash Drawer
              ◄─barcode events──          ◄──USB HID──── Barcode Scanner
```

1. The bridge runs as a background service (no GUI)
2. The Hub browser detects the bridge via `GET /status`
3. On detection, opens a WebSocket connection
4. All printer discovery, configuration, and printing is controlled from the Hub web UI
5. If the bridge is not detected, the Hub falls back to `window.print()`

## Supported Hardware

| Device | Connection | Library |
|--------|-----------|---------|
| ESC/POS Thermal Printers | USB, Network (port 9100), Bluetooth | python-escpos |
| Cash Drawer | Via printer ESC/POS kick command | python-escpos |
| Barcode Scanner (USB HID) | USB (keyboard mode) | evdev (Linux), IOKit (macOS), ctypes (Windows) |

## WebSocket Protocol

### Commands (Hub → Bridge)

```json
{"action": "get_status"}
{"action": "discover_printers"}
{"action": "print", "printer_id": "usb:0x04b8:0x0202", "document_type": "receipt", "data": {...}, "job_id": "uuid"}
{"action": "open_drawer", "printer_id": "usb:0x04b8:0x0202"}
{"action": "test_print", "printer_id": "usb:0x04b8:0x0202"}
```

### Events (Bridge → Hub)

```json
{"event": "status", "version": "0.1.0", "printers": [...], "scanner": true}
{"event": "printers", "printers": [{...}]}
{"event": "print_complete", "job_id": "uuid"}
{"event": "print_error", "job_id": "uuid", "error": "Paper out"}
{"event": "barcode", "value": "1234567890123", "type": "EAN13"}
```

## Configuration

Config is stored at:
- **macOS**: `~/Library/Application Support/ERPloraBridge/bridge_config.json`
- **Windows**: `%APPDATA%/ERPloraBridge/bridge_config.json`
- **Linux**: `~/.config/ERPloraBridge/bridge_config.json`

## Building

### macOS
```bash
pip install pyinstaller
pyinstaller build/macos/erplora_bridge.spec
# Output: dist/ERPlora Bridge.app
```

### Windows
```bash
pip install pyinstaller
pyinstaller build/windows/erplora_bridge.spec
# Output: dist/erplora-bridge.exe
```

### Android
```bash
pip install buildozer
cd native
buildozer android debug
# Output: bin/erplorabridge-0.1.0-debug.apk
```

## USB Printer Setup

### macOS
```bash
brew install libusb
```

### Windows
Install [Zadig](https://zadig.akeo.ie/) to replace the printer driver with WinUSB.

### Linux
Add udev rules for printer access:
```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", MODE="0666"' | sudo tee /etc/udev/rules.d/99-escpos.rules
sudo udevadm control --reload-rules
```
