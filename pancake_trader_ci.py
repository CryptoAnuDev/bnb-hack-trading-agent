import os
import time
import requests
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

print("🤖 Starte PancakeSwap Sniper Agent (CI)...")
print(f"🕒 Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==========================================
# 1. Wallet
# ==========================================
private_key = os.getenv("PRIVATE_KEY")
if not private_key:
    print("❌ PRIVATE_KEY nicht in .env gefunden")
    sys.exit(1)

wallet_address = Web3().eth.account.from_key(private_key).address
print(f"✅ Wallet verbunden: {wallet_address}")

# ==========================================
# 2. PancakeSwap Router (Mainnet)
# ==========================================
BSC_RPC = "https://bsc-dataseed.binance.org/"
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
    }
]

# ==========================================
# 3. Token finden (über DexScreener)
# ==========================================
def finde_token():
    """Findet einen neuen Token zum Snipen"""
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=BSC"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # BSC-Paare mit mindestens 10.000 USD Liquidität filtern
        for pair in data.get("pairs", []):
            if pair.get("chainId") != "bsc":
                continue
            
            liq = float(pair.get("liquidity", {}).get("usd", 0))
            if liq < 10000:
                continue
            
            # Bekannte Scam-Token vermeiden
            symbol = pair.get("baseToken", {}).get("symbol", "").upper()
            if any(scam in symbol for scam in ["RUG", "SCAM", "HONEYPOT", "TEST"]):
                continue
            
            # Token-Adresse holen
            token_addr = pair.get("baseToken", {}).get("address")
            if token_addr and token_addr != WBNB:
                print(f"✅ Token gefunden: {symbol} @ {token_addr}")
                print(f"   💧 Liquidität: ${liq:.2f}")
                return token_addr, symbol
                
    except Exception as e:
        print(f"❌ Fehler bei Token-Suche: {e}")
    
    return None, None

# ==========================================
# 4. Token mit BNB kaufen (direkter Swap)
# ==========================================
def kaufe_token(token_adresse, amount_bnb):
    """Kauft Token direkt mit BNB (kein USDC nötig)"""
    print(f"🚀 Kaufe Token mit {amount_bnb} BNB...")
    
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    if not w3.is_connected():
        print("❌ Keine Verbindung zu BSC")
        return None
    
    account = w3.eth.account.from_key(private_key)
    print(f"🔑 Sender: {account.address}")
    
    router = w3.eth.contract(address=PANCAKE_ROUTER, abi=ROUTER_ABI)
    amount_in_wei = int(amount_bnb * 10**18)
    
    # Transaktion bauen
    tx = router.functions.swapExactETHForTokens(
        0,  # amountOutMin = 0 (akzeptiere jede Menge)
        [WBNB, token_adresse],  # Pfad: BNB -> WBNB -> Token
        account.address,
        int(time.time()) + 1200
    ).build_transaction({
        'from': account.address,
        'value': amount_in_wei,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price,
        'nonce': w3.eth.get_transaction_count(account.address)
    })
    
    try:
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"✅ Transaktion gesendet: {tx_hash.hex()}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt['status'] == 1:
            print(f"✅ SWAP erfolgreich! Tx: {tx_hash.hex()}")
            return tx_hash.hex()
        else:
            print("❌ SWAP auf der Blockchain fehlgeschlagen")
            return None
    except Exception as e:
        print(f"❌ Transaktionsfehler: {e}")
        return None

# ==========================================
# 5. Hauptprogramm
# ==========================================
def main():
    print("\n" + "="*50)
    print("🚀 MEME-COIN SNIPER (CI-MODUS)")
    print("="*50)
    
    # 1. Token finden
    token_adresse, token_symbol = finde_token()
    if not token_adresse:
        print("❌ Kein handelbarer Token gefunden")
        sys.exit(1)
    
    # 2. Mit kleinem BNB-Betrag kaufen
    kauf_betrag = 0.0017  # ~1 USD
    print(f"\n💰 Kaufe {token_symbol} mit {kauf_betrag} BNB...")
    
    tx_hash = kaufe_token(token_adresse, kauf_betrag)
    
    if tx_hash:
        print(f"✅ Erfolg! Tx: {tx_hash}")
        print(f"📊 Token: {token_symbol}")
        print(f"🔗 https://bscscan.com/tx/{tx_hash}")
        sys.exit(0)
    else:
        print("❌ Trade fehlgeschlagen")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Vom Benutzer gestoppt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Schwerwiegender Fehler: {e}")
        sys.exit(1)