import os
import time
import requests
from dotenv import load_dotenv
from bnbagent import EVMWalletProvider
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import eth_account

load_dotenv()

print("🤖 Starte Hyperliquid Perpetual Trading Agent (MAINNET)...")

# ==========================================
# 1. Wallet verbinden
# ==========================================
private_key = os.getenv("PRIVATE_KEY")
if not private_key:
    print("❌ PRIVATE_KEY nicht in .env gefunden")
    exit(1)

try:
    account = eth_account.Account.from_key(private_key)
    wallet_address = account.address
    print(f"✅ Agent-Wallet verbunden: {wallet_address}")
except Exception as e:
    print(f"❌ Fehler beim Erstellen des Accounts: {e}")
    exit(1)

# ==========================================
# 2. Hyperliquid Client initialisieren
# ==========================================
try:
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    exchange = Exchange(account, constants.MAINNET_API_URL)
    print("✅ Hyperliquid Client initialisiert")
except Exception as e:
    print(f"❌ Fehler bei Client-Initialisierung: {e}")
    exit(1)

# ==========================================
# 3. Fear & Greed Daten
# ==========================================
def get_fear_and_greed():
    print("📊 Frage Fear & Greed Index ab...")
    try:
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data and "data" in data:
            latest = data["data"][0]
            value = int(latest["value"])
            classification = latest["value_classification"]
            print(f"📈 Fear & Greed: {value} – {classification}")
            return value, classification
    except Exception as e:
        print(f"⚠️ Fehler beim Abrufen der Daten: {e}")
    return None, None

# ==========================================
# 4. Risikomanager
# ==========================================
class PerpRiskManager:
    def __init__(self, max_leverage=2, max_position_usd=10):
        self.max_leverage = max_leverage
        self.max_position_usd = max_position_usd
        self.position = None

    def can_open_position(self, side, leverage, size_usd):
        print("🛡️ Führe Perp-Risikoprüfung durch...")
        if leverage > self.max_leverage:
            print(f"❌ Hebel {leverage}x überschreitet Limit von {self.max_leverage}x")
            return False
        if size_usd > self.max_position_usd:
            print(f"❌ Positionsgröße ${size_usd} überschreitet Limit von ${self.max_position_usd}")
            return False
        if self.position is not None:
            print("⚠️ Es ist bereits eine Position offen. Schließe diese zuerst.")
            return False
        print("✅ Perp-Risikoprüfung bestanden.")
        return True

    def close_position(self):
        if self.position is not None:
            print(f"🔒 Schließe {self.position['side']}-Position...")
            self.position = None
            return True
        else:
            print("ℹ️ Keine Position zum Schließen.")
            return False

# ==========================================
# 5. Hyperliquid Trade ausführen
# ==========================================
def execute_hyperliquid_trade(side, leverage, size_usd):
    print(f"📤 Sende {side}-Order an Hyperliquid...")
    coin = "BNB"
    sz = 0.01 if size_usd <= 10 else 0.02
    
    try:
        exchange.update_leverage(leverage, coin)
        print(f"📊 Hebel {leverage}x für {coin} gesetzt")
    except Exception as e:
        print(f"⚠️ Fehler beim Setzen des Hebels: {e}")
    
    try:
        if side == "LONG":
            order = exchange.order(
                coin,                # Coin-Name
                True,                # is_buy = Long
                sz,                  # Größe
                0,                   # limit_px = Market-Order
                {"limit": {"tif": "Gtc"}}
            )
        else:
            order = exchange.order(
                coin,
                False,               # is_buy = Short
                sz,
                0,
                {"limit": {"tif": "Gtc"}}
            )
        print(f"✅ Order erfolgreich: {order}")
        return order
    except Exception as e:
        print(f"❌ Fehler bei Hyperliquid-Order: {e}")
        return None

# ==========================================
# 6. Hauptprogramm
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 BNB HACK HYPERLIQUID TRADING AGENT")
    print("="*50)

    risk_mgr = PerpRiskManager(max_leverage=2, max_position_usd=10)

    value, _ = get_fear_and_greed()
    if value is None:
        print("❌ Konnte Marktdaten nicht abrufen.")
        exit(1)

    if value <= 25:
        action = "LONG"
        reason = "Extreme Fear – Eröffne Long-Position!"
        trade_amount = 10
        leverage = 2
    elif value >= 75:
        action = "SHORT"
        reason = "Extreme Greed – Eröffne Short-Position!"
        trade_amount = 10
        leverage = 2
    else:
        action = "CLOSE"
        reason = f"Neutral ({value}) – Schließe Position (falls vorhanden)."
        trade_amount = 0
        leverage = 1

    print(f"🧠 Entscheidung: {action} – {reason}")

    if action in ["LONG", "SHORT"]:
        if risk_mgr.can_open_position(action, leverage, trade_amount):
            result = execute_hyperliquid_trade(action, leverage, trade_amount)
            if result:
                risk_mgr.position = {
                    "side": action,
                    "leverage": leverage,
                    "size_usd": trade_amount,
                    "entry_price": "MARKET"
                }
                print("✅ Perp-Trade erfolgreich ausgeführt!")
            else:
                print("❌ Perp-Trade fehlgeschlagen")
        else:
            print("⛔ Perp-Handel blockiert.")
    else:
        risk_mgr.close_position()
        print("⏳ Keine neue Position.")

    print("\n🏁 Analyse beendet.")