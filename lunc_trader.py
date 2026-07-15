"""
LUNC Trading Agent – RSI + SMA Crossover auf BSC via PancakeSwap.

Strategie (Phase 1):
  KAUFEN:  RSI < 30 und SMA20 > SMA50
  VERKAUFEN: RSI > 70, Take-Profit (+20 %) oder Stop-Loss (-15 %)
"""

import os
import sys
import time
from datetime import datetime

import requests
from dotenv import load_dotenv
from web3 import Web3

# UTF-8-Ausgabe für Emojis (Windows-kompatibel)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

# LUNC-spezifische Persistenz (vor Import der storage-Module setzen)
os.environ.setdefault("POSITIONS_FILE", os.getenv("LUNC_POSITIONS_FILE", "lunc_positions.json"))
os.environ.setdefault("TRADES_FILE", os.getenv("LUNC_TRADES_FILE", "lunc_trades.json"))

from storage.positions import (  # noqa: E402
    close_position,
    has_open_positions,
    load_positions,
    resume_open_positions,
    save_position,
)
from storage.trades import log_trade  # noqa: E402

AGENT_NAME = "LUNC Trading Agent"

# ── BSC / PancakeSwap ────────────────────────────────────────────────────────
BSC_RPC = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
PANCAKE_ROUTER = Web3.to_checksum_address("0x10ED43C718714eb63d5aA57B78B54704E256024E")
WBNB = Web3.to_checksum_address("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
USDC = Web3.to_checksum_address("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d")
LUNC = Web3.to_checksum_address(
    os.getenv("LUNC_TOKEN_ADDRESS", "0x156ab3346823e65129404e18c78097e01124e364")
)

# ── Binance API ──────────────────────────────────────────────────────────────
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "LUNCUSDT"

# ── Strategie & Risiko ───────────────────────────────────────────────────────
CONFIG = {
    "rsi_period": 14,
    "rsi_buy_threshold": 30,
    "rsi_sell_threshold": 70,
    "sma_short": 20,
    "sma_long": 50,
    "take_profit_percent": 20,
    "stop_loss_percent": 15,
    "max_drawdown_percent": 30,
    "position_size_usdc": float(os.getenv("LUNC_POSITION_SIZE_USDC", "5")),
    "slippage_percent": 5,
    "klines_interval": "1h",
    "klines_limit": 100,
    "monitor_interval_seconds": 30,
    "api_retries": 3,
    "api_retry_delay": 5,
}

DRY_RUN = os.getenv("LUNC_DRY_RUN", "false").lower() in ("1", "true", "yes")

ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]


# ── Hilfsfunktionen: API ─────────────────────────────────────────────────────

def api_request_with_retry(url, params=None, retries=None, delay=None):
    """HTTP GET mit Retry-Logik – bricht nicht ab bei temporären Fehlern."""
    retries = retries or CONFIG["api_retries"]
    delay = delay or CONFIG["api_retry_delay"]

    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            print(f"⚠️ HTTP {response.status_code} (Versuch {attempt + 1}/{retries})")
        except Exception as e:
            print(f"⚠️ API-Fehler (Versuch {attempt + 1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(delay)
    return None


# ── Datenabruf ───────────────────────────────────────────────────────────────

def fetch_current_price() -> float | None:
    """Aktuellen LUNC/USDT-Preis von Binance abrufen."""
    data = api_request_with_retry(BINANCE_PRICE_URL, params={"symbol": SYMBOL})
    if data and "price" in data:
        return float(data["price"])
    return None


def fetch_closes() -> list[float]:
    """Schlusskurse für RSI/SMA von Binance-Klines laden."""
    data = api_request_with_retry(
        BINANCE_KLINES_URL,
        params={
            "symbol": SYMBOL,
            "interval": CONFIG["klines_interval"],
            "limit": CONFIG["klines_limit"],
        },
    )
    if not data:
        return []
    return [float(candle[4]) for candle in data]


# ── Indikatoren ──────────────────────────────────────────────────────────────

def calculate_sma(closes: list[float], period: int) -> float | None:
    """Einfacher gleitender Durchschnitt."""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    """Relative Strength Index (Wilder-Methode, vereinfacht)."""
    if len(closes) < period + 1:
        return None

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]

    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]

    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_indicators() -> dict:
    """RSI, SMA20 und SMA50 berechnen."""
    closes = fetch_closes()
    price = fetch_current_price()

    rsi = calculate_rsi(closes, CONFIG["rsi_period"])
    sma20 = calculate_sma(closes, CONFIG["sma_short"])
    sma50 = calculate_sma(closes, CONFIG["sma_long"])

    return {
        "price": price,
        "rsi": rsi,
        "sma20": sma20,
        "sma50": sma50,
        "closes": closes,
    }


# ── Entscheidungslogik ───────────────────────────────────────────────────────

def evaluate_buy_signal(indicators: dict) -> tuple[bool, str]:
    """Prüft Kaufbedingung: RSI < 30 und SMA20 > SMA50."""
    rsi = indicators.get("rsi")
    sma20 = indicators.get("sma20")
    sma50 = indicators.get("sma50")

    if rsi is None or sma20 is None or sma50 is None:
        return False, "Unzureichende Indikatordaten"

    if rsi < CONFIG["rsi_buy_threshold"] and sma20 > sma50:
        return True, f"RSI {rsi:.1f} < {CONFIG['rsi_buy_threshold']} und SMA20 > SMA50 (Aufwärtstrend)"

    return False, f"Kein Kauf-Signal (RSI={rsi:.1f}, SMA20={sma20:.8f}, SMA50={sma50:.8f})"


def evaluate_sell_signal(indicators: dict, entry_price: float) -> tuple[bool, str]:
    """Prüft Verkaufsbedingungen: RSI > 70, TP oder SL."""
    rsi = indicators.get("rsi")
    price = indicators.get("price")

    if price is None or entry_price <= 0:
        return False, "Preisdaten fehlen"

    pnl_pct = ((price - entry_price) / entry_price) * 100

    if pnl_pct >= CONFIG["take_profit_percent"]:
        return True, f"Take-Profit (+{pnl_pct:.2f}%)"
    if pnl_pct <= -CONFIG["stop_loss_percent"]:
        return True, f"Stop-Loss ({pnl_pct:.2f}%)"
    if rsi is not None and rsi > CONFIG["rsi_sell_threshold"]:
        return True, f"RSI {rsi:.1f} > {CONFIG['rsi_sell_threshold']}"

    return False, f"Halten (PnL {pnl_pct:+.2f}%)"


def check_max_drawdown(entry_price: float, current_price: float) -> bool:
    """True wenn Max-Drawdown überschritten."""
    if entry_price <= 0:
        return False
    drawdown = ((entry_price - current_price) / entry_price) * 100
    return drawdown >= CONFIG["max_drawdown_percent"]


# ── Blockchain / PancakeSwap ─────────────────────────────────────────────────

def get_web3():
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    if not w3.is_connected():
        raise ConnectionError("Keine Verbindung zum BSC Mainnet")
    return w3


def get_account(w3):
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("PRIVATE_KEY nicht in .env gefunden")
    return w3.eth.account.from_key(private_key)


def get_token_decimals(w3, token_address):
    contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    return contract.functions.decimals().call()


def resolve_swap_path(w3, token_in, token_out, amount_in_wei):
    """Findet die beste Swap-Route (direkt oder über WBNB)."""
    router = w3.eth.contract(address=PANCAKE_ROUTER, abi=ROUTER_ABI)
    candidates = [
        [token_in, token_out],
        [token_in, WBNB, token_out],
    ]
    for path in candidates:
        try:
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            if amounts[-1] > 0:
                return path, amounts[-1]
        except Exception:
            continue
    return None, 0


def approve_token(w3, account, token_address, spender, amount_wei):
    """ERC20-Approve für PancakeSwap Router."""
    token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    nonce = w3.eth.get_transaction_count(account.address)
    tx = token.functions.approve(spender, amount_wei).build_transaction({
        "from": account.address,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
    })
    if DRY_RUN:
        print(f"🔄 [DRY-RUN] Approve {token_address} → {amount_wei}")
        return "dry-run-approve"

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return tx_hash.hex()


def swap_tokens(w3, account, token_in, token_out, amount_in_wei, label="Swap"):
    """Führt swapExactTokensForTokens auf PancakeSwap aus."""
    router = w3.eth.contract(address=PANCAKE_ROUTER, abi=ROUTER_ABI)
    path, expected_out = resolve_swap_path(w3, token_in, token_out, amount_in_wei)

    if not path:
        print(f"❌ Keine Swap-Route für {label} gefunden")
        return None

    slippage = CONFIG["slippage_percent"] / 100
    amount_out_min = int(expected_out * (1 - slippage))
    print(f"📊 Route: {' → '.join(path)} | Erwartet: {expected_out} | Min: {amount_out_min}")

    if DRY_RUN:
        fake_hash = f"dry-run-{label.lower()}-{int(time.time())}"
        print(f"🔄 [DRY-RUN] {label}: {amount_in_wei} wei → {fake_hash}")
        return fake_hash

    approve_token(w3, account, token_in, PANCAKE_ROUTER, amount_in_wei)

    nonce = w3.eth.get_transaction_count(account.address)
    tx = router.functions.swapExactTokensForTokens(
        amount_in_wei,
        amount_out_min,
        path,
        account.address,
        int(time.time()) + 1200,
    ).build_transaction({
        "from": account.address,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"✅ {label} gesendet: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] == 1:
        return tx_hash.hex()
    print(f"❌ {label} fehlgeschlagen")
    return None


def buy_lunc(amount_usdc: float, entry_price: float) -> str | None:
    """Kauft LUNC mit USDC über PancakeSwap."""
    print(f"🚀 Kaufe LUNC für {amount_usdc} USDC...")
    w3 = get_web3()
    account = get_account(w3)
    usdc_decimals = get_token_decimals(w3, USDC)
    amount_wei = int(amount_usdc * (10 ** usdc_decimals))

    usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
    balance = usdc_contract.functions.balanceOf(account.address).call()
    if balance < amount_wei:
        print(f"❌ USDC-Balance zu niedrig: {balance / 10**usdc_decimals:.4f} USDC")
        return None

    return swap_tokens(w3, account, USDC, LUNC, amount_wei, label="LUNC-Kauf")


def sell_lunc(entry_price: float, amount_percent: float = 100) -> str | None:
    """Verkauft LUNC gegen USDC."""
    print(f"📤 Verkaufe {amount_percent}% LUNC...")
    w3 = get_web3()
    account = get_account(w3)

    lunc_contract = w3.eth.contract(address=LUNC, abi=ERC20_ABI)
    balance = lunc_contract.functions.balanceOf(account.address).call()
    if balance == 0:
        print("❌ Kein LUNC-Bestand")
        return None

    amount_wei = int(balance * amount_percent / 100)
    tx_hash = swap_tokens(w3, account, LUNC, USDC, amount_wei, label="LUNC-Verkauf")

    if tx_hash:
        price = fetch_current_price()
        pnl = None
        if price and entry_price:
            pnl = ((price - entry_price) / entry_price) * CONFIG["position_size_usdc"]
        log_trade("SELL", LUNC, "LUNC", amount_percent, price or 0, tx_hash, pnl=pnl)
        close_position(LUNC)
    return tx_hash


# ── Positionsüberwachung ─────────────────────────────────────────────────────

def monitor_position(token_address: str, entry_price: float, symbol: str = "LUNC"):
    """Überwacht offene LUNC-Position auf TP/SL/RSI-Verkauf."""
    print(f"📊 Überwache {symbol}-Position @ ${entry_price:.8f}")
    print(f"   TP: +{CONFIG['take_profit_percent']}% | SL: -{CONFIG['stop_loss_percent']}%")

    while True:
        try:
            indicators = compute_indicators()
            price = indicators.get("price")

            if price:
                pnl_pct = ((price - entry_price) / entry_price) * 100
                rsi = indicators.get("rsi")
                rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
                print(f"📈 Preis: ${price:.8f} | PnL: {pnl_pct:+.2f}% | RSI: {rsi_str}")

                if check_max_drawdown(entry_price, price):
                    print(f"🛑 Max-Drawdown ({CONFIG['max_drawdown_percent']}%) – Notverkauf!")
                    sell_lunc(entry_price)
                    return True

                should_sell, reason = evaluate_sell_signal(indicators, entry_price)
                if should_sell:
                    print(f"✅ Verkaufssignal: {reason}")
                    sell_lunc(entry_price)
                    return True

            time.sleep(CONFIG["monitor_interval_seconds"])

        except KeyboardInterrupt:
            print("\n🛑 Überwachung manuell gestoppt.")
            break
        except Exception as e:
            print(f"⚠️ Fehler bei Überwachung: {e}")
            time.sleep(CONFIG["monitor_interval_seconds"])

    return False


# ── Ausgabe ──────────────────────────────────────────────────────────────────

def print_decision_banner(indicators: dict, decision: str, amount_usdc: float | None = None):
    """Einheitliche Status-Ausgabe beim Start."""
    rsi = indicators.get("rsi")
    sma20 = indicators.get("sma20")
    sma50 = indicators.get("sma50")

    rsi_str = f"{rsi:.1f}" if rsi is not None else "N/A"
    sma20_str = f"{sma20:.8f}" if sma20 is not None else "N/A"
    sma50_str = f"{sma50:.8f}" if sma50 is not None else "N/A"

    print("=" * 50)
    print("🚀 LUNC TRADING AGENT")
    if DRY_RUN:
        print("🔄 Modus: DRY-RUN (keine echten Trades)")
    print("📊 Strategie: RSI + SMA Crossover")
    print(f"📈 RSI: {rsi_str} | SMA20: {sma20_str} | SMA50: {sma50_str}")
    print(f"🧠 Entscheidung: {decision}")
    if amount_usdc is not None:
        print(f"💰 Betrag: {amount_usdc} USDC")
    print("=" * 50)


# ── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    private_key = os.getenv("PRIVATE_KEY")
    if not private_key and not DRY_RUN:
        print("❌ PRIVATE_KEY nicht in .env gefunden")
        return

    # 1. Offene Positionen wieder aufnehmen
    if has_open_positions():
        print("🔄 Offene LUNC-Position gefunden – setze Überwachung fort.")
        resume_open_positions(monitor_position)
        print("\n🏁 Lauf beendet.")
        return

    # 2. Indikatoren berechnen
    indicators = compute_indicators()
    if indicators["price"] is None:
        print("❌ Preisabfrage fehlgeschlagen – Abbruch.")
        return

    # 3. Verkaufssignal prüfen (falls LUNC-Wallet-Bestand ohne gespeicherte Position)
    try:
        w3 = get_web3()
        account = get_account(w3)
        lunc_balance = w3.eth.contract(address=LUNC, abi=ERC20_ABI).functions.balanceOf(account.address).call()
        if lunc_balance > 0:
            positions = load_positions()
            lunc_pos = positions.get(LUNC.lower())
            entry = lunc_pos["entry_price"] if lunc_pos else indicators["price"]
            should_sell, reason = evaluate_sell_signal(indicators, entry)
            if should_sell:
                print_decision_banner(indicators, "VERKAUFEN")
                print(f"📋 Grund: {reason}")
                sell_lunc(entry)
                print("\n🏁 Lauf beendet.")
                return
    except Exception as e:
        if not DRY_RUN:
            print(f"⚠️ Wallet-Check übersprungen: {e}")

    # 4. Kauf-Signal prüfen
    should_buy, buy_reason = evaluate_buy_signal(indicators)

    if should_buy:
        print_decision_banner(indicators, "KAUFEN", CONFIG["position_size_usdc"])
        print(f"📋 Grund: {buy_reason}")

        entry_price = indicators["price"]
        tx_hash = buy_lunc(CONFIG["position_size_usdc"], entry_price)

        if tx_hash:
            save_position(
                LUNC, "LUNC", entry_price,
                CONFIG["position_size_usdc"], tx_hash, chain="bsc",
            )
            log_trade(
                "BUY", LUNC, "LUNC",
                CONFIG["position_size_usdc"], entry_price, tx_hash,
            )
            print("\n🔍 Starte Positionsüberwachung...")
            monitor_position(LUNC, entry_price, "LUNC")
    else:
        print_decision_banner(indicators, "HALTEN")
        print(f"📋 Grund: {buy_reason}")

    print("\n🏁 Lauf beendet.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Agent manuell gestoppt.")
    except Exception as e:
        print(f"❌ Fehler: {e}")
