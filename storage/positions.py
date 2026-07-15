import json
import os
import time

POSITIONS_FILE = os.getenv("POSITIONS_FILE", "positions.json")


def load_positions() -> dict:
    """Lädt alle Positionen aus der JSON-Datei."""
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_position(token_address, symbol, entry_price, amount, tx_hash, chain="bsc"):
    """Speichert eine offene Position."""
    positions = load_positions()
    positions[token_address.lower()] = {
        "symbol": symbol,
        "entry_price": entry_price,
        "amount": amount,
        "tx_hash": tx_hash,
        "chain": chain,
        "timestamp": time.time(),
        "status": "open",
    }
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2)


def close_position(token_address):
    """Markiert eine Position als geschlossen."""
    positions = load_positions()
    key = token_address.lower()
    if key in positions:
        positions[key]["status"] = "closed"
        positions[key]["closed_at"] = time.time()
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, indent=2)


def has_open_positions() -> bool:
    """Prüft, ob offene Positionen existieren."""
    return any(p.get("status") == "open" for p in load_positions().values())


def resume_open_positions(monitor_fn):
    """Nimmt offene Positionen beim Start wieder auf."""
    positions = load_positions()
    open_positions = {k: v for k, v in positions.items() if v.get("status") == "open"}
    if not open_positions:
        print("ℹ️ Keine offenen Positionen zum Wiederaufnehmen.")
        return False

    print(f"🔄 {len(open_positions)} offene Position(en) gefunden – setze Monitoring fort.")
    for addr, pos in open_positions.items():
        monitor_fn(addr, pos["entry_price"], pos.get("symbol", "?"))
    return True
