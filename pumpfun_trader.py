import os
import json
import asyncio
from decimal import Decimal
from datetime import datetime

import aiohttp
import requests
from dotenv import load_dotenv
from pump_swap import PumpSwap, lamports_to_tokens, usd_to_lamports

load_dotenv()

AGENT_NAME = "Pump.fun Sniper"

SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SEEN_MINTS_FILE = os.getenv("SEEN_MINTS_FILE", "seen_pump_mints.json")

DEXSCREENER_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens"

CONFIG = {
    "buy_amount_usd": 1.0,
    "poll_interval_seconds": 30,
    "min_liquidity_usd": 5000,
    "slippage_percent": 10.0,
    "max_tokens_per_run": 1,
}


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def load_seen_mints() -> set:
    if os.path.exists(SEEN_MINTS_FILE):
        with open(SEEN_MINTS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_mints(seen: set):
    with open(SEEN_MINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def fetch_latest_pump_mints():
    """Findet neue Pump.fun-Token über DexScreener."""
    try:
        response = requests.get(DEXSCREENER_LATEST, timeout=10)
        response.raise_for_status()
        profiles = response.json()
    except Exception as e:
        print(f"⚠️ DexScreener nicht erreichbar: {e}")
        return []

    mints = []
    for profile in profiles:
        if profile.get("chainId") != "solana":
            continue
        address = profile.get("tokenAddress", "")
        if address.lower().endswith("pump"):
            mints.append(address)
    return mints


def get_token_liquidity_usd(mint_address):
    """Ruft Liquidität und Preis über DexScreener ab."""
    try:
        response = requests.get(f"{DEXSCREENER_TOKEN}/{mint_address}", timeout=10)
        data = response.json()
        pairs = data.get("pairs") or []
        if not pairs:
            return 0, Decimal("0")

        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        liquidity = float(best.get("liquidity", {}).get("usd", 0) or 0)
        price_usd = Decimal(str(best.get("priceUsd", "0") or "0"))
        return liquidity, price_usd
    except Exception as e:
        print(f"⚠️ Token-Info fehlgeschlagen: {e}")
        return 0, Decimal("0")


async def buy_pump_token(pump_swap, mint_address, sol_price_usd):
    """Kauft einen Token über pump-swap auf der Bonding Curve."""
    print(f"🚀 Kaufe {mint_address} (~${CONFIG['buy_amount_usd']})...")

    liquidity, token_price = get_token_liquidity_usd(mint_address)
    if liquidity < CONFIG["min_liquidity_usd"]:
        print(f"⏳ Liquidität zu niedrig (${liquidity:.2f})")
        return None

    if token_price <= 0:
        token_price = Decimal("0.0000000280")

    try:
        bonding_curve, _ = await pump_swap.get_bonding_curve_pda(mint_address)
        sol_lamports = await usd_to_lamports(int(CONFIG["buy_amount_usd"]), Decimal(str(sol_price_usd)))
        token_amount = await lamports_to_tokens(sol_lamports, token_price)

        result = await pump_swap.pump_buy(
            mint_address=mint_address,
            bonding_curve_pda=bonding_curve,
            sol_amount=sol_lamports,
            token_amount=token_amount,
            sim=False,
            slippage=CONFIG["slippage_percent"],
        )

        result_json = result.to_json()
        parsed = json.loads(result_json)
        tx_id = parsed.get("result")
        if tx_id:
            print(f"✅ Kauf erfolgreich! Tx: {tx_id}")
            return tx_id

        print(f"❌ Kauf fehlgeschlagen: {result_json}")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Kauf: {e}")
        return None


async def monitor_loop(pump_swap, sol_price_usd, seen_mints):
    bought = 0

    while True:
        latest_mints = fetch_latest_pump_mints()
        new_mints = [m for m in latest_mints if m not in seen_mints]

        if new_mints:
            print(f"\n🆕 {len(new_mints)} neue Pump.fun-Token gefunden")

        for mint in new_mints:
            seen_mints.add(mint)
            save_seen_mints(seen_mints)

            print(f"\n🔍 Prüfe Token: {mint}")
            tx = await buy_pump_token(pump_swap, mint, sol_price_usd)
            if tx:
                bought += 1
                if bought >= CONFIG["max_tokens_per_run"]:
                    print(f"\n✅ {bought} Kauf/Käufe abgeschlossen – beende Lauf.")
                    return

        await asyncio.sleep(CONFIG["poll_interval_seconds"])


async def main():
    print_status_header()

    if not SOLANA_PRIVATE_KEY:
        print("❌ SOLANA_PRIVATE_KEY nicht in .env gefunden")
        print("📝 Siehe .env.example")
        return

    seen_mints = load_seen_mints()
    print(f"ℹ️ {len(seen_mints)} bereits bekannte Mints geladen")

    async with aiohttp.ClientSession() as session:
        pump_swap = PumpSwap(
            session=session,
            priv_key=SOLANA_PRIVATE_KEY,
            rpc_endpoint=SOLANA_RPC_URL,
            debug=False,
        )

        try:
            sol_price_usd = float(pump_swap.get_solana_price_usd())
            print(f"✅ PumpSwap initialisiert | SOL ≈ ${sol_price_usd:.2f}")
        except Exception as e:
            print(f"❌ PumpSwap-Initialisierung fehlgeschlagen: {e}")
            return

        print("\n🔍 Überwache DexScreener auf neue Pump.fun-Token...")
        print("   Drücke Strg+C zum Beenden.\n")

        try:
            await monitor_loop(pump_swap, sol_price_usd, seen_mints)
        except KeyboardInterrupt:
            print("\n🛑 Agent manuell gestoppt.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Agent beendet.")
