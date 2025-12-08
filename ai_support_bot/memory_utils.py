from pathlib import Path
import json

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

MEMORY_PATH = STORAGE_DIR / "memory.json"


def _ensure_memory_file():
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text("[]", encoding="utf-8")


def load_memory():
    _ensure_memory_file()
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def save_memory(turns):
    MEMORY_PATH.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8")


def add_turn_to_memory(user_message: str, assistant_message: str):
    history = load_memory()
    history.append({"user": user_message, "assistant": assistant_message})
    save_memory(history)
