import os
import time
import requests
from dotenv import load_dotenv
from web3 import Web3
from bnbagent import EVMWalletProvider

# Lade .env (für Wallet und andere Secrets)
load_dotenv()

print("🤖 Starte Perpetual Trading Agent (MAINNET - ApolloX)...")

# ==========================================
# 1. Wallet verbinden (mit .env-Werten)
# ==========================================
wallet = EVMWalletProvider(
    password=os.getenv("WALLET_PASSWORD"),   # Dein Wallet-Passwort
    private_key=os.getenv("PRIVATE_KEY")      # Dein privater Schlüssel
)
print(f"✅ Agent-Wallet verbunden: {wallet.address}")

# ==========================================
# 2. ApolloX (AsterDEX) Client mit direkten Keys
# ==========================================
# ⚠️ HIER deine API-Keys von AsterDEX eintragen!
APOLLOX_API_KEY = "0xCED9ef0eAe71c1c7C7E0B0fB76533d365FD23e2a"        # ← HIER EINTRAGEN
APOLLOX_API_SECRET = "0xe1c1b93e0b49a30588ed1eedeefb86ce927715b8482b10db745617dcf53cfd2f"  # ← HIER EINTRAGEN

# Client initialisieren (ohne testnet-Argument)
if APOLLOX_API_KEY == "dein_api_key_hier" or APOLLOX_API_SECRET == "dein_api_secret_hier":
    print("⚠️ Bitte trage deine API-Keys in den Code ein (Zeilen 26-27)!")
    client = None
else:
    try:
        from apollox.rest_api import Client
        client = Client(key=APOLLOX_API_KEY, secret=APOLLOX_API_SECRET)  # Korrigiert!
        print("✅ ApolloX Client initialisiert")
    except ImportError:
        print("❌ ApolloX-Connector nicht installiert. Führe aus: py -m pip install apollox-connector-python")
        client = None
    except Exception as e:
        print(f"❌ Fehler bei Client-Initialisierung: {e}")
        client = None

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
# 4. Risikomanager für Perps
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
# 5. Perp-Trade ausführen
# ==========================================
def execute_perp_trade(side, leverage, size_usd):
    if client is None:
        print("⚠️ Kein API-Client. Führe Simulation aus...")
        print(f"🔄 SIMULATION: {side}-Position mit {leverage}x Hebel, ${size_usd} USD")
        return {"orderId": "sim-12345", "status": "FILLED"}

    try:
        symbol = "BNBUSDT"
        params = {
            'symbol': symbol,
            'side': side,  # "BUY" für Long, "SELL" für Short
            'type': 'MARKET',
            'quantity': size_usd,
            'leverage': leverage
        }
        print(f"📤 Sende Order: {params}")
        response = client.new_order(**params)
        print(f"✅ Order erfolgreich: {response}")
        return response
    except Exception as e:
        print(f"❌ Fehler bei ApolloX-Order: {e}")
        return None

# ==========================================
# 6. Hauptprogramm
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 BNB HACK PERPETUAL TRADING AGENT")
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
            result = execute_perp_trade(action, leverage, trade_amount)
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