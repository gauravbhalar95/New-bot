"""Private runtime registry for multiple MEGA accounts. Never commit accounts.json."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE_DIR = Path(__file__).resolve().parent
STORE_PATH = STORE_DIR / "accounts.json"


def _load():
    try:
        with STORE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def _save(data):
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = STORE_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temp_path, STORE_PATH)
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass


def add_account(email, password):
    data = _load()
    used = {int(key[1:]) for key in data if key.startswith("g") and key[1:].isdigit()}
    number = 1
    while number in used:
        number += 1
    account_id = f"g{number}"
    data[account_id] = {"email": email, "password": password}
    _save(data)
    return account_id


def list_accounts():
    data = _load()
    return [
        {"id": key, "email": value.get("email", "")}
        for key, value in sorted(data.items(), key=lambda item: int(item[0][1:]) if item[0][1:].isdigit() else 0)
    ]


def get_account(account_id):
    item = _load().get(account_id)
    if not item or not item.get("email") or not item.get("password"):
        return None
    return {"id": account_id, "email": item["email"], "password": item["password"]}
