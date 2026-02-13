"""
ESC/POS printer management.

Handles printing receipts, kitchen orders, invoices, and other documents
to thermal printers via USB, network, or Bluetooth.
"""

import logging
from datetime import datetime
from typing import Any

from .discovery import parse_printer_id, connect_printer

logger = logging.getLogger('erplora.bridge.printer')


class PrinterManager:
    """Manages multiple printers and routes print jobs."""

    def __init__(self):
        self._cached_printers: list[dict] = []

    def get_cached_printers(self) -> list[dict]:
        """Return the last discovered printers list."""
        return self._cached_printers

    def update_cache(self, printers: list[dict]):
        """Update the cached printers list after discovery."""
        self._cached_printers = printers

    def print_document(self, printer_id: str, document_type: str, data: dict):
        """
        Print a document on the specified printer.

        Args:
            printer_id: Printer identifier (e.g., 'usb:0x04b8:0x0202', 'network:192.168.1.100:9100')
            document_type: Type of document ('receipt', 'kitchen_order', 'invoice', etc.)
            data: Document data from Hub
        """
        printer = connect_printer(printer_id)

        try:
            if document_type == 'receipt':
                self._print_receipt(printer, data)
            elif document_type == 'kitchen_order':
                self._print_kitchen_order(printer, data)
            elif document_type == 'invoice':
                self._print_invoice(printer, data)
            elif document_type == 'delivery_note':
                self._print_delivery_note(printer, data)
            elif document_type == 'barcode_label':
                self._print_barcode_label(printer, data)
            elif document_type == 'cash_session_report':
                self._print_cash_report(printer, data)
            else:
                self._print_generic(printer, data)
        finally:
            try:
                printer.close()
            except Exception:
                pass

    def test_print(self, printer_id: str):
        """Print a test page to verify printer connectivity."""
        printer = connect_printer(printer_id)
        try:
            printer.set(align='center')
            printer.text("================================\n")
            printer.set(align='center', bold=True, double_height=True)
            printer.text("ERPlora Bridge\n")
            printer.set(align='center', bold=False, double_height=False)
            printer.text("--------------------------------\n")
            printer.text("Test Print OK\n")
            printer.text(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            printer.text("--------------------------------\n")
            printer.text(f"Printer: {printer_id}\n")
            printer.text("================================\n")
            printer.cut()
        finally:
            try:
                printer.close()
            except Exception:
                pass

    # ─── Document Renderers ──────────────────────────────────────────────

    def _print_receipt(self, printer: Any, data: dict):
        """Render and print a sales receipt."""
        # Header
        printer.set(align='center', bold=True)
        business_name = data.get('business_name', 'ERPlora')
        printer.text(f"{business_name}\n")

        if data.get('business_address'):
            printer.set(align='center', bold=False, text_type='normal')
            printer.text(f"{data['business_address']}\n")

        if data.get('vat_number'):
            printer.text(f"NIF: {data['vat_number']}\n")

        if data.get('phone'):
            printer.text(f"Tel: {data['phone']}\n")

        printer.text("================================\n")

        # Receipt info
        printer.set(align='left', bold=False)
        receipt_id = data.get('receipt_id', '')
        printer.text(f"Ticket: {receipt_id}\n")
        printer.text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

        if data.get('cashier'):
            printer.text(f"Cajero: {data['cashier']}\n")

        if data.get('customer_name'):
            printer.text(f"Cliente: {data['customer_name']}\n")

        printer.text("--------------------------------\n")

        # Items
        items = data.get('items', [])
        for item in items:
            name = item.get('name', '')
            qty = item.get('quantity', 1)
            total = item.get('total', 0)

            # Line 1: quantity x name
            printer.set(align='left', bold=False)
            line = f"{qty}x {name}"
            # Pad with spaces and add total on the right
            total_str = f"{total:.2f}"
            padding = 32 - len(line) - len(total_str)
            if padding < 1:
                padding = 1
            printer.text(f"{line}{' ' * padding}{total_str}\n")

            # Notes if any
            if item.get('notes'):
                printer.set(align='left', bold=False)
                printer.text(f"  > {item['notes']}\n")

        printer.text("--------------------------------\n")

        # Totals
        if data.get('subtotal') is not None:
            self._print_total_line(printer, "Subtotal", data['subtotal'])

        if data.get('tax_amount') is not None:
            tax_label = data.get('tax_label', 'IVA')
            self._print_total_line(printer, tax_label, data['tax_amount'])

        if data.get('discount') is not None and data['discount'] > 0:
            self._print_total_line(printer, "Descuento", -data['discount'])

        printer.text("================================\n")
        printer.set(align='left', bold=True, double_height=True)
        total = data.get('total', 0)
        self._print_total_line(printer, "TOTAL", total)
        printer.set(bold=False, double_height=False)
        printer.text("================================\n")

        # Payment info
        if data.get('payment_method'):
            printer.set(align='left', bold=False)
            printer.text(f"Pago: {data['payment_method']}\n")

        if data.get('paid') is not None:
            self._print_total_line(printer, "Entregado", data['paid'])

        if data.get('change') is not None and data['change'] > 0:
            self._print_total_line(printer, "Cambio", data['change'])

        # Footer
        printer.text("\n")
        if data.get('receipt_header'):
            printer.set(align='center')
            printer.text(f"{data['receipt_header']}\n")

        if data.get('receipt_footer'):
            printer.set(align='center')
            printer.text(f"{data['receipt_footer']}\n")

        printer.set(align='center')
        printer.text("\nGracias por su compra\n\n")

        printer.cut()

    def _print_kitchen_order(self, printer: Any, data: dict):
        """Render and print a kitchen order ticket (large text for readability)."""
        # Loud header for kitchen
        printer.set(align='center', bold=True, double_height=True, double_width=True)
        printer.text("COCINA\n")

        printer.set(align='center', bold=True, double_height=True, double_width=False)
        order_number = data.get('receipt_id', data.get('order_number', ''))
        printer.text(f"#{order_number}\n")

        printer.set(align='center', bold=False, double_height=False)
        printer.text("================================\n")

        # Table and waiter
        if data.get('table'):
            printer.set(align='left', bold=True, double_height=True)
            printer.text(f"Mesa: {data['table']}\n")

        printer.set(align='left', bold=False, double_height=False)
        if data.get('waiter'):
            printer.text(f"Camarero: {data['waiter']}\n")

        printer.text(f"Hora: {datetime.now().strftime('%H:%M')}\n")
        printer.text("--------------------------------\n")

        # Items — big text for kitchen readability
        items = data.get('items', [])
        for item in items:
            qty = item.get('quantity', 1)
            name = item.get('name', '')

            printer.set(align='left', bold=True, double_height=True)
            printer.text(f"{qty}x {name}\n")

            if item.get('notes'):
                printer.set(align='left', bold=False, double_height=False)
                printer.text(f"   >> {item['notes']}\n")

        printer.text("================================\n")

        # Priority
        priority = data.get('priority', 'NORMAL')
        if priority == 'HIGH':
            printer.set(align='center', bold=True, double_height=True)
            printer.text("!! URGENTE !!\n")

        printer.text("\n")
        printer.cut()

    def _print_invoice(self, printer: Any, data: dict):
        """Render and print an invoice (similar to receipt with more detail)."""
        # Use receipt renderer as base — invoices on thermal are similar
        self._print_receipt(printer, data)

    def _print_delivery_note(self, printer: Any, data: dict):
        """Render and print a delivery note."""
        printer.set(align='center', bold=True)
        printer.text("ALBARAN\n")
        printer.text("================================\n")

        printer.set(align='left', bold=False)
        printer.text(f"N: {data.get('receipt_id', '')}\n")
        printer.text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

        if data.get('customer_name'):
            printer.text(f"Cliente: {data['customer_name']}\n")
        if data.get('delivery_address'):
            printer.text(f"Dir: {data['delivery_address']}\n")

        printer.text("--------------------------------\n")

        items = data.get('items', [])
        for item in items:
            qty = item.get('quantity', 1)
            name = item.get('name', '')
            printer.text(f"{qty}x {name}\n")

        printer.text("================================\n")
        printer.text("\nFirma: _______________\n\n")
        printer.cut()

    def _print_barcode_label(self, printer: Any, data: dict):
        """Print a barcode label."""
        printer.set(align='center', bold=True)
        printer.text(f"{data.get('product_name', '')}\n")

        barcode_value = data.get('barcode', '')
        if barcode_value:
            try:
                printer.barcode(barcode_value, 'EAN13', width=2, height=80)
            except Exception:
                printer.text(f"[{barcode_value}]\n")

        if data.get('price') is not None:
            printer.set(align='center', bold=True, double_height=True)
            printer.text(f"{data['price']:.2f}\n")

        printer.cut()

    def _print_cash_report(self, printer: Any, data: dict):
        """Print a cash session report."""
        printer.set(align='center', bold=True)
        printer.text("CIERRE DE CAJA\n")
        printer.text("================================\n")

        printer.set(align='left', bold=False)
        printer.text(f"Sesion: {data.get('receipt_id', '')}\n")
        printer.text(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

        if data.get('cashier'):
            printer.text(f"Cajero: {data['cashier']}\n")

        printer.text("--------------------------------\n")

        self._print_total_line(printer, "Apertura", data.get('opening_balance', 0))
        self._print_total_line(printer, "Cierre", data.get('closing_balance', 0))

        diff = (data.get('closing_balance', 0) or 0) - (data.get('opening_balance', 0) or 0)
        self._print_total_line(printer, "Diferencia", diff)

        printer.text("--------------------------------\n")

        transactions = data.get('transactions', [])
        for tx in transactions:
            label = tx.get('label', tx.get('type', ''))
            amount = tx.get('amount', 0)
            self._print_total_line(printer, label, amount)

        printer.text("================================\n\n")
        printer.cut()

    def _print_generic(self, printer: Any, data: dict):
        """Print a generic document with whatever data is provided."""
        printer.set(align='center', bold=True)
        printer.text(f"{data.get('title', 'Documento')}\n")
        printer.text("================================\n")

        printer.set(align='left', bold=False)
        for key, value in data.items():
            if key in ('title', 'receipt_id'):
                continue
            printer.text(f"{key}: {value}\n")

        printer.text("================================\n\n")
        printer.cut()

    # ─── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _print_total_line(printer: Any, label: str, amount: float):
        """Print a right-aligned total line: 'Label         12.50'"""
        amount_str = f"{amount:.2f}"
        padding = 32 - len(label) - len(amount_str)
        if padding < 1:
            padding = 1
        printer.text(f"{label}{' ' * padding}{amount_str}\n")
