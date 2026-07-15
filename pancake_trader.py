import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
from bnbagent import EVMWalletProvider
from storage.positions import save_position, close_position, resume_open_positions, has_open_positions
from storage.trades import log_trade

load_dotenv()

AGENT_NAME = "PancakeSwap Meme-Coin Sniper"


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


# ==========================================
# 1. Konfiguration & Wallet
# ==========================================
wallet = EVMWalletProvider(
    password=os.getenv("WALLET_PASSWORD"),
    private_key=os.getenv("PRIVATE_KEY"),
)

# ==========================================
# 2. Token-Discovery mit DexScreener API (kostenlos)
# ==========================================
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

def get_new_bsc_tokens():
    """Ruft die neuesten Tokens auf BSC über DexScreener ab."""
    try:
        url = f"{DEXSCREENER_API}/search?q=BSC"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("pairs"):
            bsc_pairs = [p for p in data["pairs"] if p.get("chainId") == "bsc"]
            return bsc_pairs
        return []
    except Exception as e:
        print(f"❌ Fehler beim Abrufen neuer Tokens: {e}")
        return []

# ==========================================
# 3. PancakeSwap Router (MAINNET)
# ==========================================
BSC_MAINNET_RPC = "https://bsc-dataseed.binance.org/"
PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
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
]

# ==========================================
# 4. Token-Filter & Risikomanagement
# ==========================================
CONFIG = {
    "min_liquidity_usd": 10000,
    "max_pool_age_hours": 6,
    "max_slippage": 0.10,
    "buy_amount_bnb": 0.0017,  # ~1 USD
    "min_tx_count": 10,
    "take_profit_percent": 30,   # 30% Gewinn mitnehmen
    "stop_loss_percent": 15,     # 15% Verlust begrenzen
    "max_hold_time_minutes": 0   # 0 = deaktiviert
}

def is_token_attractive(token):
    """Prüft, ob ein Token die Kriterien erfüllt."""
    try:
        liq_usd = float(token.get("liquidity", {}).get("usd", 0))
        if liq_usd < CONFIG["min_liquidity_usd"]:
            return False
        
        creation_time = token.get("pairCreatedAt")
        if creation_time:
            age_hours = (time.time() - (creation_time / 1000)) / 3600
            if age_hours > CONFIG["max_pool_age_hours"]:
                return False
        
        tx_count_24h = token.get("txns", {}).get("h24", {}).get("buys", 0) + token.get("txns", {}).get("h24", {}).get("sells", 0)
        if tx_count_24h < CONFIG["min_tx_count"]:
            return False
        
        symbol = token.get("baseToken", {}).get("symbol", "").upper()
        if not symbol:
            return False
        
        known_scams = ["RUG", "SCAM", "HONEYPOT", "TEST"]
        for scam in known_scams:
            if scam in symbol:
                return False
        
        print(f"✅ Token {symbol} ist attraktiv!")
        print(f"   💧 Liquidität: ${liq_usd:.2f}")
        print(f"   🔄 Transaktionen (24h): {tx_count_24h}")
        return True
    except Exception as e:
        print(f"⚠️ Fehler beim Prüfen von Token: {e}")
        return False

# ==========================================
# 5. Trading-Funktionen
# ==========================================
def buy_token_with_bnb(token_address, amount_bnb):
    """Kauft einen Token mit BNB über PancakeSwap."""
    print(f"🚀 Kaufe Token {token_address} mit {amount_bnb} BNB (~1 USD)...")
    
    w3 = Web3(Web3.HTTPProvider(BSC_MAINNET_RPC))
    if not w3.is_connected():
        print("❌ Keine Verbindung zum BSC Mainnet")
        return None
    
    private_key = os.getenv("PRIVATE_KEY")
    account = w3.eth.account.from_key(private_key)
    
    router = w3.eth.contract(address=PANCAKE_ROUTER, abi=ROUTER_ABI)
    amount_in_wei = int(amount_bnb * 10**18)
    
    tx = router.functions.swapExactETHForTokens(
        0,
        [WBNB, token_address],
        account.address,
        int(time.time()) + 1200
    ).build_transaction({
        'from': account.address,
        'value': amount_in_wei,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address)
    })
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"✅ Kauf-Transaktion gesendet: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt['status'] == 1:
        print(f"✅ Kauf erfolgreich! Tx: {tx_hash.hex()}")
        return tx_hash.hex()
    else:
        print("❌ Kauf fehlgeschlagen")
        return None

def get_current_price_bnb(token_address):
    """Ruft den aktuellen Token-Preis in BNB über DexScreener ab."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("pairs"):
            pair = data["pairs"][0]
            price_usd = float(pair.get("priceUsd", 0))
            price_native = float(pair.get("priceNative", 0))
            if price_native > 0:
                return price_native, price_usd
            return price_usd / 600, price_usd
    except Exception as e:
        print(f"⚠️ Preisabfrage fehlgeschlagen: {e}")
    return None, None


def sell_token(token_address, amount_percent=100, symbol="?", entry_price_bnb=None):
    """Verkauft einen Token über PancakeSwap (mit ERC20-Approve)."""
    print(f"📤 Verkaufe Token {token_address} ({amount_percent}%)...")

    w3 = Web3(Web3.HTTPProvider(BSC_MAINNET_RPC))
    if not w3.is_connected():
        print("❌ Keine Verbindung zum BSC Mainnet")
        return None

    private_key = os.getenv("PRIVATE_KEY")
    account = w3.eth.account.from_key(private_key)

    router = w3.eth.contract(address=PANCAKE_ROUTER, abi=ROUTER_ABI)
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    balance = token_contract.functions.balanceOf(account.address).call()

    if balance == 0:
        print("❌ Kein Token-Bestand zum Verkaufen")
        return None

    amount_to_sell = int(balance * amount_percent / 100)
    nonce = w3.eth.get_transaction_count(account.address)

    approve_tx = token_contract.functions.approve(
        PANCAKE_ROUTER, amount_to_sell
    ).build_transaction({
        "from": account.address,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
    })
    signed_approve = account.sign_transaction(approve_tx)
    approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
    w3.eth.wait_for_transaction_receipt(approve_hash, timeout=60)
    print(f"✅ Approve bestätigt: {approve_hash.hex()}")

    tx = router.functions.swapExactTokensForETH(
        amount_to_sell,
        0,
        [token_address, WBNB],
        account.address,
        int(time.time()) + 1200,
    ).build_transaction({
        "from": account.address,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce + 1,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"✅ Verkauf-Transaktion gesendet: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] == 1:
        print(f"✅ Verkauf erfolgreich! Tx: {tx_hash.hex()}")
        exit_price_bnb, exit_price_usd = get_current_price_bnb(token_address)
        pnl = None
        if entry_price_bnb and exit_price_usd:
            pnl = ((exit_price_usd - (entry_price_bnb * 600)) / (entry_price_bnb * 600)) * CONFIG["buy_amount_bnb"] * 600
        log_trade(
            "SELL", token_address, symbol, amount_percent,
            exit_price_bnb or 0, tx_hash.hex(), pnl=pnl,
        )
        close_position(token_address)
        return tx_hash.hex()
    else:
        print("❌ Verkauf fehlgeschlagen")
        return None

def monitor_position(token_address, entry_price_bnb, symbol="?"):
    """Überwacht die Position und verkauft bei TP oder SL."""
    print(f"📊 Überwache Position: {symbol} ({token_address})")
    print(f"   Einstiegspreis: {entry_price_bnb:.6f} BNB")
    print(f"   📈 Take-Profit: +{CONFIG['take_profit_percent']}%")
    print(f"   📉 Stop-Loss: -{CONFIG['stop_loss_percent']}%")

    while True:
        try:
            price_bnb, price_usd = get_current_price_bnb(token_address)

            if price_bnb and entry_price_bnb > 0:
                price_change = ((price_bnb - entry_price_bnb) / entry_price_bnb) * 100
                print(f"📊 Aktueller Preis: ${price_usd:.4f} | Veränderung: {price_change:.2f}%")

                if price_change >= CONFIG["take_profit_percent"]:
                    print(f"✅ Take-Profit erreicht! ({price_change:.2f}%)")
                    sell_token(token_address, symbol=symbol, entry_price_bnb=entry_price_bnb)
                    return True

                if price_change <= -CONFIG["stop_loss_percent"]:
                    print(f"❌ Stop-Loss ausgelöst! ({price_change:.2f}%)")
                    sell_token(token_address, symbol=symbol, entry_price_bnb=entry_price_bnb)
                    return True

            time.sleep(30)

        except KeyboardInterrupt:
            print("\n🛑 Überwachung manuell gestoppt.")
            break
        except Exception as e:
            print(f"⚠️ Fehler bei Überwachung: {e}")
            time.sleep(60)

    return False

# ==========================================
# 6. Hauptprogramm
# ==========================================
def main():
    print_status_header()
    print(f"✅ Agent-Wallet verbunden: {wallet.address}")
    print("\n" + "=" * 50)
    print("🚀 MEME-COIN SNIPER AGENT (1 USD TRADES)")
    print("=" * 50)

    # Offene Positionen beim Start wieder aufnehmen
    if has_open_positions():
        resumed = resume_open_positions(monitor_position)
        if resumed:
            print("\n🏁 Positionsüberwachung beendet.")
            return

    # Kein neuer Kauf, solange eine Position offen ist
    if has_open_positions():
        print("⏸️ Offene Position aktiv – kein neuer Kauf.")
        return

    print("🔍 Suche nach neuen BSC-Tokens...")
    tokens = get_new_bsc_tokens()
    if not tokens:
        print("❌ Keine Tokens gefunden.")
        return

    print(f"📊 Gefundene BSC-Tokens: {len(tokens)}")

    attractive_tokens = []
    for token in tokens:
        if is_token_attractive(token):
            attractive_tokens.append(token)

    if not attractive_tokens:
        print("❌ Kein attraktiver Token gefunden.")
        return

    print(f"✅ {len(attractive_tokens)} attraktive Token gefunden!")

    best_token = max(attractive_tokens, key=lambda x: float(x.get("liquidity", {}).get("usd", 0)))
    token_address = best_token.get("baseToken", {}).get("address")
    token_symbol = best_token.get("baseToken", {}).get("symbol", "UNKNOWN")
    token_liq = float(best_token.get("liquidity", {}).get("usd", 0))
    entry_price_bnb = float(best_token.get("priceNative", 0)) or CONFIG["buy_amount_bnb"]

    print(f"\n🎯 Beste Token: {token_symbol}")
    print(f"   Adresse: {token_address}")
    print(f"   Liquidität: ${token_liq:.2f}")

    buy_amount_bnb = CONFIG["buy_amount_bnb"]
    print(f"\n💰 Kaufe Token mit {buy_amount_bnb} BNB (~1 USD)...")

    tx_hash = buy_token_with_bnb(token_address, buy_amount_bnb)
    if tx_hash:
        print(f"✅ Position für {token_symbol} eröffnet!")
        print(f"📊 Tx Hash: {tx_hash}")

        save_position(token_address, token_symbol, entry_price_bnb, buy_amount_bnb, tx_hash)
        log_trade("BUY", token_address, token_symbol, buy_amount_bnb, entry_price_bnb, tx_hash)

        print("\n🔍 Starte Positionsüberwachung...")
        monitor_position(token_address, entry_price_bnb, token_symbol)
    else:
        print("❌ Kauf fehlgeschlagen.")

    print("\n🏁 Analyse beendet.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Agent manuell gestoppt.")
    except Exception as e:
        print(f"❌ Fehler: {e}")