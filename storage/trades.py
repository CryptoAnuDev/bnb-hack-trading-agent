import json
import os
import time

TRADES_FILE = os.getenv("TRADES_FILE", "trades.json")


def log_trade(action, token_address, symbol, amount, price, tx_hash, pnl=None, chain="bsc"):
    """Protokolliert einen Trade in der JSON-Historie."""
    trades = []
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            trades = json.load(f)

    trades.append({
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "token_address": token_address,
        "symbol": symbol,
        "amount": amount,
        "price": price,
        "tx_hash": tx_hash,
        "pnl_usd": pnl,
        "chain": chain,
    })

    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2)
