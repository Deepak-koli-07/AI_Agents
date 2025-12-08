from pathlib import Path
import json
import uuid
from datetime import datetime
import re

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

TICKETS_PATH = STORAGE_DIR / "tickets.json"


def _ensure_tickets_file():
    if not TICKETS_PATH.exists():
        TICKETS_PATH.write_text("[]", encoding="utf-8")


def load_tickets():
    _ensure_tickets_file()
    try:
        data = json.loads(TICKETS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_tickets(tickets):
    TICKETS_PATH.write_text(json.dumps(tickets, ensure_ascii=False, indent=2), encoding="utf-8")


def create_ticket(order_id: str, issue_type: str, user_message: str, summary: str):
    tickets = load_tickets()
    ticket = {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:8].upper()}",
        "order_id": order_id,
        "issue_type": issue_type,
        "user_message": user_message,
        "summary": summary,
        "status": "OPEN",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    tickets.append(ticket)
    save_tickets(tickets)
    return ticket


# ---- helpers ----

def extract_order_id(text: str):
    """
    Find something like 6–12 digit order id in text.
    """
    match = re.search(r"\b\d{4,12}\b", text)
    return match.group(0) if match else None


def classify_issue_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["refund", "money back", "return"]):
        return "Refund Issue"
    if any(k in t for k in ["cancel", "cancellation"]):
        return "Cancellation Issue"
    if any(k in t for k in ["delivered but", "not received", "missing", "lost package"]):
        return "Delivery Issue"
    if any(k in t for k in ["login", "password", "sign in", "account access"]):
        return "Login Issue"
    return "General Support"


def extract_ticket_id(text: str):
    match = re.search(r"\bTKT-[A-Za-z0-9]{8}\b", text)
    return match.group(0) if match else None


def get_ticket_by_id(ticket_id: str):
    tickets = load_tickets()
    for t in tickets:
        if t.get("ticket_id") == ticket_id:
            return t
    return None
