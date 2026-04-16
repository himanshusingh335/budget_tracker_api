#!/usr/bin/env python3
"""
Budget Tracker Terminal Dashboard

Single-file Textual TUI that mirrors the Flutter budget tracker app.
Supports: summary view, transactions (add/delete), budget (add/delete),
month navigation, and colourful charts.

Requirements:
    pip install textual httpx
    # or:
    conda run -n flask-test pip install textual httpx

Usage:
    python dashboard.py
    BUDGET_API_URL=http://localhost:8502 python dashboard.py
"""

import json
import os
from datetime import date, datetime

import httpx
from agents import Agent, Runner, SQLiteSession, function_tool
from agents.mcp import MCPServerStreamableHttp
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

# ── Configuration ──────────────────────────────────────────────────────────────

API_BASE = os.environ.get("BUDGET_API_URL", "http://localhost:8502")

CATEGORIES = [
    "Auto", "Entertainment", "Food", "Home",
    "Medical", "Personal Items", "Travel", "Utilities", "Other",
]

PURPLE   = "#6C47FF"
RED      = "#E74C3C"
GREEN    = "#2ECC71"
BG_DARK  = "#1a1a2e"
BG_MID   = "#16213e"
BG_CARD  = "#0f3460"

# ── Penny config ───────────────────────────────────────────────────────────────

MCP_URL = os.environ.get("BUDGET_MCP_URL", "http://raspberrypi4.tailad9f80.ts.net:8502/mcp")
PENNY_MODEL = os.environ.get("PENNY_MODEL", "gpt-5.4")
PENNY_INSTRUCTIONS = (
    "You are Penny, a concise and friendly personal budget assistant. "
    "Use the available tools to answer questions about the user's budgets and transactions. "
    "Formatting rules you must always follow:\n"
    "1. Currency: always prefix amounts with ₹ and no other symbol. Never use 'INR' or 'Rs'.\n"
    "2. Number formatting: use Indian-style comma grouping (e.g. ₹1,23,456.00 not ₹123,456.00).\n"
    "3. Structure: present any comparison, breakdown, or multi-item answer as a plain-text table "
    "using aligned columns. Use a table even for two rows if there are multiple fields.\n"
    "4. Brevity: keep prose to one sentence max; let the table carry the detail."
)


@function_tool
def get_today() -> dict:
    """Return today's date in the formats used by the Budget Tracker API."""
    today = date.today()
    return {
        "date": today.strftime("%Y-%m-%d"),
        "month_year": today.strftime("%m/%y"),
        "month": today.month,
        "year": today.year,
        "day": today.day,
    }


# ── API helpers ────────────────────────────────────────────────────────────────

async def api_get(path: str):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{API_BASE}{path}")
        r.raise_for_status()
        return r.json()


async def api_post(path: str, data: dict):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{API_BASE}{path}", json=data)
        r.raise_for_status()
        return r.json()


async def api_download(path: str, dest: str) -> str:
    """Download a file from the API and write it to dest. Returns dest."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.get(f"{API_BASE}{path}")
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
    return dest


async def api_patch(path: str, data: dict):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.patch(f"{API_BASE}{path}", json=data)
        r.raise_for_status()
        return r.json()


async def api_delete(path: str, data: dict = None):
    async with httpx.AsyncClient(timeout=10.0) as c:
        if data:
            r = await c.request("DELETE", f"{API_BASE}{path}", content=json.dumps(data), headers={"Content-Type": "application/json"})
        else:
            r = await c.delete(f"{API_BASE}{path}")
        r.raise_for_status()
        return r.json()


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_inr(s: str) -> float:
    """Parse a formatted INR string like '₹ 1,234.56' to float."""
    return float(s.replace("₹", "").replace(",", "").strip())


# ── Modals ─────────────────────────────────────────────────────────────────────

class ConfirmModal(ModalScreen):
    """Simple yes / no confirmation dialog."""

    DEFAULT_CSS = f"""
    ConfirmModal {{
        align: center middle;
    }}
    #dialog {{
        width: 54;
        height: auto;
        border: thick {PURPLE};
        background: {BG_MID};
        padding: 1 2;
    }}
    #msg {{
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }}
    #btns {{
        width: 100%;
        height: auto;
        align: center middle;
    }}
    Button {{ margin: 0 1; }}
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(self._message, id="msg")
            with Horizontal(id="btns"):
                yield Button("  Yes  ", variant="error", id="yes")
                yield Button("  No  ", variant="primary", id="no")

    @on(Button.Pressed, "#yes")
    def confirmed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def cancelled(self) -> None:
        self.dismiss(False)


class AddTransactionModal(ModalScreen):
    """Form modal to add a new transaction."""

    DEFAULT_CSS = f"""
    AddTransactionModal {{
        align: center middle;
    }}
    #dialog {{
        width: 62;
        height: auto;
        border: thick {PURPLE};
        background: {BG_MID};
        padding: 1 2;
    }}
    #ttl {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {PURPLE};
        margin-bottom: 1;
    }}
    .field-label {{ margin-top: 1; }}
    Input, Select {{ width: 100%; }}
    #btns {{
        width: 100%;
        align: center middle;
        margin-top: 1;
    }}
    Button {{ margin: 0 1; }}
    #err {{ width: 100%; text-align: center; color: {RED}; height: 1; }}
    """

    def __init__(self, today: str) -> None:
        super().__init__()
        self._today = today

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("➕  Add Transaction", id="ttl")
            yield Label("Description", classes="field-label")
            yield Input(placeholder="e.g. Lunch at canteen", id="desc")
            yield Label("Amount (₹)", classes="field-label")
            yield Input(placeholder="0.00", id="amount")
            yield Label("Category", classes="field-label")
            yield Select([(c, c) for c in CATEGORIES], prompt="Select category…", id="cat")
            yield Label("Date  (dd/MM/yy)", classes="field-label")
            yield Input(value=self._today, id="date")
            yield Label("", id="err")
            with Horizontal(id="btns"):
                yield Button("  Add  ", variant="success", id="add")
                yield Button("  Cancel  ", variant="default", id="cancel")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#add")
    def do_add(self) -> None:
        desc       = self.query_one("#desc",   Input).value.strip()
        amount_raw = self.query_one("#amount", Input).value.strip()
        cat        = self.query_one("#cat",    Select).value
        date_str   = self.query_one("#date",   Input).value.strip()
        err        = self.query_one("#err",    Label)

        if not desc:
            err.update("Description is required."); return
        if not amount_raw:
            err.update("Amount is required."); return
        if cat is Select.BLANK:
            err.update("Category is required."); return
        if not date_str:
            err.update("Date is required."); return

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            err.update("Enter a valid positive amount."); return

        try:
            dt = datetime.strptime(date_str, "%d/%m/%y")
        except ValueError:
            err.update("Date must be in dd/MM/yy format  (e.g. 29/03/26)."); return

        self.dismiss({
            "Date":        date_str,
            "Description": desc,
            "Category":    cat,
            "Expenditure": amount,
            "Year":        dt.year,
            "Month":       dt.month,
            "Day":         dt.day,
        })


class EditTransactionModal(ModalScreen):
    """Form modal to edit an existing transaction."""

    DEFAULT_CSS = f"""
    EditTransactionModal {{
        align: center middle;
    }}
    #dialog {{
        width: 62;
        height: auto;
        border: thick {PURPLE};
        background: {BG_MID};
        padding: 1 2;
    }}
    #ttl {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {PURPLE};
        margin-bottom: 1;
    }}
    .field-label {{ margin-top: 1; }}
    Input, Select {{ width: 100%; }}
    #btns {{
        width: 100%;
        align: center middle;
        margin-top: 1;
    }}
    Button {{ margin: 0 1; }}
    #err {{ width: 100%; text-align: center; color: {RED}; height: 1; }}
    """

    def __init__(self, row: dict) -> None:
        super().__init__()
        self._row = row

    def compose(self) -> ComposeResult:
        r = self._row
        with Container(id="dialog"):
            yield Label(f"✏️  Edit Transaction #{r['id']}", id="ttl")
            yield Label("Description", classes="field-label")
            yield Input(value=r["Description"], id="desc")
            yield Label("Amount (₹)", classes="field-label")
            yield Input(value=str(r["Expenditure"]), id="amount")
            yield Label("Category", classes="field-label")
            yield Select(
                [(c, c) for c in CATEGORIES],
                value=r["Category"],
                prompt="Select category…",
                id="cat",
            )
            yield Label("Date  (dd/MM/yy)", classes="field-label")
            yield Input(value=r["Date"], id="date")
            yield Label("", id="err")
            with Horizontal(id="btns"):
                yield Button("  Save  ", variant="success", id="save")
                yield Button("  Cancel  ", variant="default", id="cancel")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    def do_save(self) -> None:
        desc       = self.query_one("#desc",   Input).value.strip()
        amount_raw = self.query_one("#amount", Input).value.strip()
        cat        = self.query_one("#cat",    Select).value
        date_str   = self.query_one("#date",   Input).value.strip()
        err        = self.query_one("#err",    Label)

        if not desc:
            err.update("Description is required."); return
        if not amount_raw:
            err.update("Amount is required."); return
        if cat is Select.BLANK:
            err.update("Category is required."); return
        if not date_str:
            err.update("Date is required."); return

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            err.update("Enter a valid positive amount."); return

        try:
            dt = datetime.strptime(date_str, "%d/%m/%y")
        except ValueError:
            err.update("Date must be in dd/MM/yy format  (e.g. 29/03/26)."); return

        self.dismiss({
            "Date":        date_str,
            "Description": desc,
            "Category":    cat,
            "Expenditure": amount,
            "Year":        dt.year,
            "Month":       dt.month,
            "Day":         dt.day,
        })


class EditBudgetModal(ModalScreen):
    """Form modal to edit the amount for an existing budget entry."""

    DEFAULT_CSS = f"""
    EditBudgetModal {{
        align: center middle;
    }}
    #dialog {{
        width: 54;
        height: auto;
        border: thick {PURPLE};
        background: {BG_MID};
        padding: 1 2;
    }}
    #ttl {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {PURPLE};
        margin-bottom: 1;
    }}
    .field-label {{ margin-top: 1; }}
    Input {{ width: 100%; }}
    #btns {{
        width: 100%;
        align: center middle;
        margin-top: 1;
    }}
    Button {{ margin: 0 1; }}
    #err {{ width: 100%; text-align: center; color: {RED}; height: 1; }}
    """

    def __init__(self, row: dict, month_year: str) -> None:
        super().__init__()
        self._row        = row
        self._month_year = month_year

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(f"✏️  Edit Budget — {self._row['Category']}", id="ttl")
            yield Label("New Budget Amount (₹)", classes="field-label")
            yield Input(value=str(self._row["Budget"]), id="amount")
            yield Label("", id="err")
            with Horizontal(id="btns"):
                yield Button("  Save  ", variant="success", id="save")
                yield Button("  Cancel  ", variant="default", id="cancel")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    def do_save(self) -> None:
        amount_raw = self.query_one("#amount", Input).value.strip()
        err        = self.query_one("#err",    Label)

        if not amount_raw:
            err.update("Amount is required."); return

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            err.update("Enter a valid positive amount."); return

        self.dismiss({"MonthYear": self._month_year, "Category": self._row["Category"], "Budget": amount})


class AddBudgetModal(ModalScreen):
    """Form modal to set a monthly budget for a category."""

    DEFAULT_CSS = f"""
    AddBudgetModal {{
        align: center middle;
    }}
    #dialog {{
        width: 54;
        height: auto;
        border: thick {PURPLE};
        background: {BG_MID};
        padding: 1 2;
    }}
    #ttl {{
        width: 100%;
        text-align: center;
        text-style: bold;
        color: {PURPLE};
        margin-bottom: 1;
    }}
    .field-label {{ margin-top: 1; }}
    Input, Select {{ width: 100%; }}
    #btns {{
        width: 100%;
        align: center middle;
        margin-top: 1;
    }}
    Button {{ margin: 0 1; }}
    #err {{ width: 100%; text-align: center; color: {RED}; height: 1; }}
    """

    def __init__(self, used: list, month_year: str) -> None:
        super().__init__()
        self._available  = [c for c in CATEGORIES if c not in used]
        self._month_year = month_year

    def compose(self) -> ComposeResult:
        opts = [(c, c) for c in self._available] if self._available else [("(all categories set)", "")]
        with Container(id="dialog"):
            yield Label("💰  Set Budget", id="ttl")
            yield Label("Category", classes="field-label")
            yield Select(opts, prompt="Select category…", id="cat")
            yield Label("Budget Amount (₹)", classes="field-label")
            yield Input(placeholder="0.00", id="amount")
            yield Label("", id="err")
            with Horizontal(id="btns"):
                yield Button("  Set  ", variant="success", id="set")
                yield Button("  Cancel  ", variant="default", id="cancel")

    @on(Button.Pressed, "#cancel")
    def do_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#set")
    def do_set(self) -> None:
        cat        = self.query_one("#cat",    Select).value
        amount_raw = self.query_one("#amount", Input).value.strip()
        err        = self.query_one("#err",    Label)

        if cat is Select.BLANK or not cat:
            err.update("Category is required."); return
        if not amount_raw:
            err.update("Amount is required."); return

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except ValueError:
            err.update("Enter a valid positive amount."); return

        self.dismiss({"MonthYear": self._month_year, "Category": cat, "Budget": amount})


# ── Sub-views ──────────────────────────────────────────────────────────────────

class SummaryView(Widget):
    """Summary tab: three stat cards, ASCII bar chart, category table."""

    DEFAULT_CSS = f"""
    SummaryView {{
        height: 100%;
        overflow-y: auto;
    }}
    #cards {{
        height: 5;
        margin-bottom: 1;
    }}
    .card {{
        width: 1fr;
        height: 5;
        border: round {PURPLE};
        padding: 0 1;
        content-align: center middle;
        background: {BG_CARD};
        text-align: center;
    }}
    #chart {{
        height: auto;
        min-height: 3;
        padding: 0 1;
        margin-bottom: 1;
    }}
    #tbl {{
        height: auto;
    }}
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="cards"):
            yield Static("", classes="card", id="c-bud")
            yield Static("", classes="card", id="c-exp")
            yield Static("", classes="card", id="c-dif")
        yield Static("[dim]Loading…[/]", id="chart")
        yield DataTable(id="tbl", show_cursor=False)

    def on_mount(self) -> None:
        t = self.query_one("#tbl", DataTable)
        t.add_columns("Category", "Budget", "Expenditure", "Difference")

    def update_data(self, rows: list) -> None:
        data  = [r for r in rows if r["MonthYear"] != "Total"]
        total = next((r for r in rows if r["MonthYear"] == "Total"), None)

        # Stat cards
        if total:
            bud = parse_inr(total["Budget"])
            exp = parse_inr(total["Expenditure"])
            dif = parse_inr(total["Difference"])
            dc  = GREEN if dif >= 0 else RED
            self.query_one("#c-bud", Static).update(
                f"[bold {PURPLE}]TOTAL BUDGET[/]\n\n[bold white]₹ {bud:,.2f}[/]"
            )
            self.query_one("#c-exp", Static).update(
                f"[bold {RED}]TOTAL SPENT[/]\n\n[bold white]₹ {exp:,.2f}[/]"
            )
            self.query_one("#c-dif", Static).update(
                f"[bold {dc}]REMAINING[/]\n\n[bold {dc}]₹ {dif:,.2f}[/]"
            )
        else:
            for cid in ("#c-bud", "#c-exp", "#c-dif"):
                self.query_one(cid, Static).update("")

        # ASCII bar chart
        max_val = max((parse_inr(r["Budget"]) for r in data), default=1) or 1
        W = 30
        lines = [f"[bold {PURPLE}]Budget vs Expenditure[/]\n"]
        for r in data:
            cat = r["Category"][:14].ljust(14)
            bud = parse_inr(r["Budget"])
            exp = parse_inr(r["Expenditure"])
            bb  = "█" * int(bud / max_val * W)
            eb  = "█" * int(exp / max_val * W)
            lines.append(f"[dim]{cat}[/] [{PURPLE}]{bb:<{W}}[/] [dim]₹{bud:>9,.0f}[/]")
            lines.append(f"{'':14} [{RED}]{eb:<{W}}[/] [dim]₹{exp:>9,.0f}[/]")
            lines.append("")
        lines.append(f"[{PURPLE}]█[/] Budget   [{RED}]█[/] Expenditure")
        self.query_one("#chart", Static).update("\n".join(lines))

        # Category breakdown table
        t = self.query_one("#tbl", DataTable)
        t.clear()
        for r in data:
            dif_val = parse_inr(r["Difference"])
            t.add_row(
                r["Category"],
                Text(r["Budget"],      style=f"bold {PURPLE}"),
                Text(r["Expenditure"], style=RED),
                Text(r["Difference"],  style=GREEN if dif_val >= 0 else RED),
            )

    def show_message(self, msg: str) -> None:
        for cid in ("#c-bud", "#c-exp", "#c-dif"):
            self.query_one(cid, Static).update("")
        self.query_one("#chart", Static).update(f"[dim]{msg}[/]")
        self.query_one("#tbl", DataTable).clear()


class TransactionsView(Widget):
    """Transactions tab: scrollable table with add / delete."""

    DEFAULT_CSS = f"""
    TransactionsView {{
        height: 100%;
    }}
    #txn-tbl {{ height: 1fr; }}
    #txn-hint {{
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }}
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rows = []

    def compose(self) -> ComposeResult:
        yield DataTable(id="txn-tbl")
        yield Label("", id="txn-hint")

    def on_mount(self) -> None:
        t = self.query_one("#txn-tbl", DataTable)
        t.add_columns("ID", "Date", "Category", "Description", "Amount (₹)")
        t.cursor_type = "row"

    def update_data(self, rows: list) -> None:
        def _date_key(r):
            try:
                return datetime.strptime(r["Date"], "%d/%m/%y")
            except ValueError:
                return datetime.min
        self._rows = sorted(rows, key=_date_key, reverse=True)
        t = self.query_one("#txn-tbl", DataTable)
        t.clear()
        for r in self._rows:
            t.add_row(
                str(r["id"]),
                r["Date"],
                r["Category"],
                r["Description"],
                Text(f"₹ {r['Expenditure']:,.2f}", style=RED),
                key=str(r["id"]),
            )
        if rows:
            hint = f"[dim]{len(rows)} transaction(s)  ·  [bold]a[/bold] add   [bold]e[/bold] edit   [bold]d[/bold] delete   [bold]x[/bold] export CSV   [bold]r[/bold] refresh[/]"
        else:
            hint = "[dim]No transactions this month.  Press [bold]a[/bold] to add one.[/]"
        self.query_one("#txn-hint", Label).update(hint)

    def selected_id(self):
        t = self.query_one("#txn-tbl", DataTable)
        if not self._rows or t.cursor_row < 0:
            return None
        try:
            row = t.get_row_at(t.cursor_row)
            return int(row[0])
        except Exception:
            return None

    def selected_row(self):
        t = self.query_one("#txn-tbl", DataTable)
        if not self._rows or t.cursor_row < 0:
            return None
        try:
            row = t.get_row_at(t.cursor_row)
            txn_id = int(row[0])
            return next((r for r in self._rows if r["id"] == txn_id), None)
        except Exception:
            return None


class BudgetView(Widget):
    """Budget tab: table with add / delete."""

    DEFAULT_CSS = f"""
    BudgetView {{
        height: 100%;
    }}
    #bud-tbl {{ height: 1fr; }}
    #bud-hint {{
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }}
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rows = []

    def compose(self) -> ComposeResult:
        yield DataTable(id="bud-tbl")
        yield Label("", id="bud-hint")

    def on_mount(self) -> None:
        t = self.query_one("#bud-tbl", DataTable)
        t.add_columns("Category", "Budget (₹)")
        t.cursor_type = "row"

    def update_data(self, rows: list) -> None:
        self._rows = rows
        t = self.query_one("#bud-tbl", DataTable)
        t.clear()
        for r in rows:
            t.add_row(
                r["Category"],
                Text(f"₹ {r['Budget']:,.2f}", style=f"bold {PURPLE}"),
                key=r["Category"],
            )
        if rows:
            hint = f"[dim]{len(rows)} budget(s)  ·  [bold]a[/bold] add   [bold]e[/bold] edit   [bold]d[/bold] delete   [bold]x[/bold] export CSV   [bold]r[/bold] refresh[/]"
        else:
            hint = "[dim]No budgets set this month.  Press [bold]a[/bold] to add one.[/]"
        self.query_one("#bud-hint", Label).update(hint)

    def selected_row(self):
        t = self.query_one("#bud-tbl", DataTable)
        if not self._rows or t.cursor_row < 0:
            return None
        try:
            row = t.get_row_at(t.cursor_row)
            cat = str(row[0])
            return next((r for r in self._rows if r["Category"] == cat), None)
        except Exception:
            return None

    def used_categories(self) -> list:
        return [r["Category"] for r in self._rows]


# ── Penny chat view ───────────────────────────────────────────────────────────

class PennyView(Widget):
    """Penny tab: conversational AI chat panel backed by the MCP server."""

    DEFAULT_CSS = f"""
    PennyView {{
        height: 100%;
    }}
    #chat-log {{
        height: 1fr;
        border: round {PURPLE};
        background: {BG_CARD};
        padding: 0 1;
    }}
    #penny-status {{
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }}
    #penny-input {{
        width: 100%;
        margin-top: 1;
    }}
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._session = SQLiteSession("penny-dashboard")
        self._busy = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=False)
        yield Label("", id="penny-status")
        yield Input(placeholder="Ask Penny anything about your budget…", id="penny-input")

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold {PURPLE}]Penny[/] [dim]is ready. Ask me anything about your budget.[/]")

    @on(Input.Submitted, "#penny-input")
    def on_message_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query or self._busy:
            return
        inp = self.query_one("#penny-input", Input)
        inp.value = ""
        inp.disabled = True
        self._busy = True
        log = self.query_one("#chat-log", RichLog)
        log.write(f"\n[bold {PURPLE}]You:[/] {query}")
        self._run_penny(query)

    @work
    async def _run_penny(self, query: str) -> None:
        status = self.query_one("#penny-status", Label)
        log    = self.query_one("#chat-log", RichLog)
        status.update("[dim]Penny is thinking…[/]")
        try:
            async with MCPServerStreamableHttp(
                name="budget-tracker",
                params={"url": MCP_URL},
                cache_tools_list=True,
            ) as server:
                agent = Agent(
                    name="Penny",
                    instructions=PENNY_INSTRUCTIONS,
                    model=PENNY_MODEL,
                    tools=[get_today],
                    mcp_servers=[server],
                )
                result = await Runner.run(agent, query, session=self._session)
            log.write(f"[bold {GREEN}]Penny:[/] {result.final_output}")
        except Exception as exc:
            log.write(f"[bold {RED}]Penny:[/] Sorry, something went wrong — {exc}")
        finally:
            status.update("")
            inp = self.query_one("#penny-input", Input)
            inp.disabled = False
            self._busy = False
            inp.focus()


# ── Main App ───────────────────────────────────────────────────────────────────

class BudgetDashboard(App):
    TITLE     = "Budget Tracker"
    SUB_TITLE = "Terminal Dashboard"

    CSS = f"""
    Screen {{
        background: {BG_DARK};
    }}
    Header {{
        background: {PURPLE};
        color: white;
    }}
    Footer {{
        background: {BG_MID};
    }}
    TabbedContent {{
        height: 1fr;
    }}
    TabbedContent > ContentSwitcher {{
        height: 1fr;
    }}
    TabPane {{
        padding: 1 2;
        height: 100%;
    }}
    #month-bar {{
        height: 3;
        align: center middle;
        background: {BG_MID};
        border-bottom: solid {PURPLE};
    }}
    #month-lbl {{
        color: white;
        text-style: bold;
        width: 22;
        text-align: center;
    }}
    .nav-btn {{
        width: 5;
        min-width: 5;
        background: {PURPLE};
        color: white;
        border: none;
        height: 1;
    }}
    .nav-btn:hover {{
        background: white;
        color: {PURPLE};
    }}
    """

    BINDINGS = [
        Binding("q",     "quit",        "Quit"),
        Binding("r",     "refresh",     "Refresh"),
        Binding("a",     "add",         "Add"),
        Binding("e",     "edit",        "Edit"),
        Binding("d",     "delete",      "Delete"),
        Binding("x",     "export_csv",  "Export CSV"),
        Binding("[",     "prev_month",  "◀ Month"),
        Binding("]",     "next_month",  "Month ▶"),
        Binding("p",     "penny_tab",   "Penny"),
    ]

    def __init__(self) -> None:
        super().__init__()
        now          = datetime.now()
        self.month   = now.month
        self.year    = now.year

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="month-bar"):
            yield Button("◀", classes="nav-btn", id="prev")
            yield Label(self._label(), id="month-lbl")
            yield Button("▶", classes="nav-btn", id="next")
        with TabbedContent(id="tabs"):
            with TabPane("  Summary  ", id="tab-summary"):
                yield SummaryView(id="sv")
            with TabPane("  Transactions  ", id="tab-transactions"):
                yield TransactionsView(id="tv")
            with TabPane("  Budget  ", id="tab-budget"):
                yield BudgetView(id="bv")
            with TabPane("  Penny  ", id="tab-penny"):
                yield PennyView(id="pv")
        yield Footer()

    def on_mount(self) -> None:
        self._reload_all()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _label(self) -> str:
        return datetime(self.year, self.month, 1).strftime("%B %Y")

    def _my(self) -> str:
        """Return MonthYear string in MM/YY format."""
        return f"{self.month:02d}/{str(self.year)[-2:]}"

    def _active_tab(self) -> str:
        try:
            return self.query_one(TabbedContent).active
        except Exception:
            return ""

    # ── Data loading ───────────────────────────────────────────────────────────

    @work(exclusive=True)
    async def _reload_all(self) -> None:
        await self._fetch_summary()
        await self._fetch_transactions()
        await self._fetch_budget()

    async def _fetch_summary(self) -> None:
        sv = self.query_one("#sv", SummaryView)
        try:
            data = await api_get(f"/summary/{self.month}/{self.year}")
            sv.update_data(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                sv.show_message("No budget data for this month.  Set a budget to see the summary.")
            else:
                sv.show_message(f"API error {e.response.status_code}")
        except Exception as e:
            sv.show_message(f"Cannot reach API — is it running?  ({e})")

    async def _fetch_transactions(self) -> None:
        tv = self.query_one("#tv", TransactionsView)
        try:
            data = await api_get(f"/transactions/{self.month}/{self.year}")
            tv.update_data(data)
        except Exception:
            tv.update_data([])

    async def _fetch_budget(self) -> None:
        bv = self.query_one("#bv", BudgetView)
        try:
            data = await api_get(f"/budget/{self.month}/{self.year}")
            bv.update_data(data.get("Budgets", []))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                bv.update_data([])
            else:
                bv.update_data([])
        except Exception:
            bv.update_data([])

    # ── Month navigation ───────────────────────────────────────────────────────

    def _shift_month(self, delta: int) -> None:
        self.month += delta
        if self.month > 12:
            self.month = 1
            self.year  += 1
        elif self.month < 1:
            self.month = 12
            self.year  -= 1
        self.query_one("#month-lbl", Label).update(self._label())
        self._reload_all()

    def action_prev_month(self) -> None:
        self._shift_month(-1)

    def action_next_month(self) -> None:
        self._shift_month(1)

    @on(Button.Pressed, "#prev")
    def on_prev(self) -> None:
        self._shift_month(-1)

    @on(Button.Pressed, "#next")
    def on_next(self) -> None:
        self._shift_month(1)

    # ── Global actions ─────────────────────────────────────────────────────────

    def action_penny_tab(self) -> None:
        self.query_one(TabbedContent).active = "tab-penny"
        self.query_one("#penny-input", Input).focus()

    def action_refresh(self) -> None:
        self._reload_all()

    def action_add(self) -> None:
        tab = self._active_tab()
        if tab == "tab-transactions":
            self._open_add_transaction()
        elif tab == "tab-budget":
            self._open_add_budget()

    def action_delete(self) -> None:
        tab = self._active_tab()
        if tab == "tab-transactions":
            self._confirm_delete_transaction()
        elif tab == "tab-budget":
            self._confirm_delete_budget()

    def action_edit(self) -> None:
        tab = self._active_tab()
        if tab == "tab-transactions":
            self._open_edit_transaction()
        elif tab == "tab-budget":
            self._open_edit_budget()

    def action_export_csv(self) -> None:
        tab = self._active_tab()
        if tab == "tab-transactions":
            self._do_export_csv("/transactions/export/csv", "transactions.csv")
        elif tab == "tab-budget":
            self._do_export_csv("/budget/export/csv", "budget.csv")
        elif tab == "tab-summary":
            # export both from summary tab
            self._do_export_csv("/transactions/export/csv", "transactions.csv")
            self._do_export_csv("/budget/export/csv", "budget.csv")

    @work
    async def _do_export_csv(self, path: str, filename: str) -> None:
        try:
            dest = await api_download(path, filename)
            self.notify(f"Saved → {dest}", severity="information", timeout=6)
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    # ── Transaction CRUD ───────────────────────────────────────────────────────

    def _open_add_transaction(self) -> None:
        today = datetime.now().strftime("%d/%m/%y")
        self.push_screen(
            AddTransactionModal(today),
            lambda payload: self._post_transaction(payload) if payload else None,
        )

    @work
    async def _post_transaction(self, payload: dict) -> None:
        try:
            await api_post("/transactions", payload)
            self.notify("Transaction added.", severity="information")
            await self._fetch_transactions()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to add transaction: {e}", severity="error")

    def _confirm_delete_transaction(self) -> None:
        txn_id = self.query_one("#tv", TransactionsView).selected_id()
        if txn_id is None:
            self.notify("Select a row first.", severity="warning")
            return
        self.push_screen(
            ConfirmModal(f"Delete transaction #{txn_id}?"),
            lambda ok: self._do_delete_transaction(txn_id) if ok else None,
        )

    @work
    async def _do_delete_transaction(self, txn_id: int) -> None:
        try:
            await api_delete(f"/transactions/{txn_id}")
            self.notify("Transaction deleted.", severity="information")
            await self._fetch_transactions()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to delete: {e}", severity="error")

    def _open_edit_transaction(self) -> None:
        row = self.query_one("#tv", TransactionsView).selected_row()
        if row is None:
            self.notify("Select a row first.", severity="warning")
            return
        self.push_screen(
            EditTransactionModal(row),
            lambda payload: self._patch_transaction(row["id"], payload) if payload else None,
        )

    @work
    async def _patch_transaction(self, txn_id: int, payload: dict) -> None:
        try:
            await api_patch(f"/transactions/{txn_id}", payload)
            self.notify("Transaction updated.", severity="information")
            await self._fetch_transactions()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to update: {e}", severity="error")

    # ── Budget CRUD ────────────────────────────────────────────────────────────

    def _open_add_budget(self) -> None:
        used = self.query_one("#bv", BudgetView).used_categories()
        self.push_screen(
            AddBudgetModal(used, self._my()),
            lambda payload: self._post_budget(payload) if payload else None,
        )

    @work
    async def _post_budget(self, payload: dict) -> None:
        try:
            await api_post("/budget", payload)
            self.notify("Budget set.", severity="information")
            await self._fetch_budget()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to set budget: {e}", severity="error")

    def _confirm_delete_budget(self) -> None:
        row = self.query_one("#bv", BudgetView).selected_row()
        if row is None:
            self.notify("Select a row first.", severity="warning")
            return
        self.push_screen(
            ConfirmModal(f"Delete budget for '{row['Category']}'?"),
            lambda ok: self._do_delete_budget(row["Category"]) if ok else None,
        )

    @work
    async def _do_delete_budget(self, category: str) -> None:
        try:
            await api_delete("/budget", {"MonthYear": self._my(), "Category": category})
            self.notify("Budget deleted.", severity="information")
            await self._fetch_budget()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to delete: {e}", severity="error")

    def _open_edit_budget(self) -> None:
        row = self.query_one("#bv", BudgetView).selected_row()
        if row is None:
            self.notify("Select a row first.", severity="warning")
            return
        self.push_screen(
            EditBudgetModal(row, self._my()),
            lambda payload: self._replace_budget(row["Category"], payload) if payload else None,
        )

    @work
    async def _replace_budget(self, old_category: str, payload: dict) -> None:
        try:
            await api_delete("/budget", {"MonthYear": self._my(), "Category": old_category})
            await api_post("/budget", payload)
            self.notify("Budget updated.", severity="information")
            await self._fetch_budget()
            await self._fetch_summary()
        except Exception as e:
            self.notify(f"Failed to update: {e}", severity="error")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    BudgetDashboard().run()
