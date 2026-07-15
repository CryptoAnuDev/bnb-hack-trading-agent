import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from bnbagent import EVMWalletProvider

load_dotenv()

AGENT_NAME = "AsterDEX Perpetual Trader"

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_PASSWORD = os.getenv("WALLET_PASSWORD")
APOLLOX_API_KEY = os.getenv("APOLLOX_API_KEY")
APOLLOX_API_SECRET = os.getenv("APOLLOX_API_SECRET")

client = None


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def init_client():
    global client
    if not APOLLOX_API_KEY or not APOLLOX_API_SECRET:
        print("⚠️ APOLLOX_API_KEY / APOLLOX_API_SECRET nicht in .env gefunden")
        return

    try:
        from apollox.rest_api import Client
        client = Client(key=APOLLOX_API_KEY, secret=APOLLOX_API_SECRET)
        print("✅ AsterDEX Client initialisiert")
    except ImportError:
        print("❌ ApolloX-Connector nicht installiert. Führe aus: pip install apollox-connector-python")
    except Exception as e:
        print(f"❌ Fehler bei Client-Initialisierung: {e}")


def get_fear_and_greed():
    print("📊 Frage Fear & Greed Index ab...")
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
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
        print("ℹ️ Keine Position zum Schließen.")
        return False


def execute_asterdex_trade(side, leverage, size_usd):
    if client is None:
        print("⚠️ Kein API-Client verfügbar.")
        return None

    try:
        aster_side = "BUY" if side == "LONG" else "SELL"
        params = {
            "symbol": "BNBUSDT",
            "side": aster_side,
            "type": "MARKET",
            "quantity": size_usd,
            "leverage": leverage,
        }
        print(f"📤 Sende Order an AsterDEX: {params}")
        response = client.new_order(**params)
        print(f"✅ Order erfolgreich: {response}")
        return response
    except Exception as e:
        print(f"❌ Fehler bei AsterDEX-Order: {e}")
        return None


def main():
    print_status_header()

    wallet = EVMWalletProvider(password=WALLET_PASSWORD, private_key=PRIVATE_KEY)
    print(f"✅ Agent-Wallet verbunden: {wallet.address}")

    init_client()

    risk_mgr = PerpRiskManager(max_leverage=2, max_position_usd=10)

    value, _ = get_fear_and_greed()
    if value is None:
        print("❌ Konnte Marktdaten nicht abrufen.")
        return

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
            result = execute_asterdex_trade(action, leverage, trade_amount)
            if result:
                risk_mgr.position = {
                    "side": action,
                    "leverage": leverage,
                    "size_usd": trade_amount,
                    "entry_price": "MARKET",
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


if __name__ == "__main__":
    main()
