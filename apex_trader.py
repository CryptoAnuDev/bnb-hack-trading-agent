import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

AGENT_NAME = "ApeX Omni Perpetual Trader"

API_KEY = os.getenv("APEX_API_KEY")
API_SECRET = os.getenv("APEX_API_SECRET")
PASSPHRASE = os.getenv("APEX_PASSPHRASE")
APEX_OMNI_SEED = os.getenv("APEX_OMNI_SEED")
APEX_L2_KEY = os.getenv("APEX_L2_KEY", "")

SYMBOL = "BNB-USDT"
TICKER_SYMBOL = "BNBUSDT"


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


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


def init_apex_client():
    missing = []
    if not API_KEY:
        missing.append("APEX_API_KEY")
    if not API_SECRET:
        missing.append("APEX_API_SECRET")
    if not PASSPHRASE:
        missing.append("APEX_PASSPHRASE")
    if not APEX_OMNI_SEED:
        missing.append("APEX_OMNI_SEED")

    if missing:
        print(f"❌ Fehlende .env-Variablen: {', '.join(missing)}")
        print("📝 Keys generieren: https://omni.apex.exchange/keyManagement")
        print("   Benötigt: API Key + Omni Key (seeds) + Passphrase")
        return None

    try:
        from apexomni.http_private_sign import HttpPrivateSign
        from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_OMNI_MAIN_ARB

        client = HttpPrivateSign(
            APEX_OMNI_HTTP_MAIN,
            network_id=NETWORKID_OMNI_MAIN_ARB,
            zk_seeds=APEX_OMNI_SEED,
            zk_l2Key=APEX_L2_KEY,
            api_key_credentials={
                "key": API_KEY,
                "secret": API_SECRET,
                "passphrase": PASSPHRASE,
            },
        )
        client.configs_v3()
        account = client.get_account_v3()
        balance = client.get_account_balance_v3()
        print("✅ ApeX Omni Client initialisiert")
        print(f"📊 Account: {account.get('data', account)}")
        print(f"💰 Balance: {balance.get('data', balance)}")
        return client
    except ImportError:
        print("❌ apexomni nicht installiert. Führe aus: pip install apexomni")
        return None
    except Exception as e:
        print(f"❌ Fehler bei Client-Initialisierung: {e}")
        return None


def get_market_price():
    try:
        from apexomni.http_public import HttpPublic
        from apexomni.constants import APEX_OMNI_HTTP_MAIN

        public = HttpPublic(APEX_OMNI_HTTP_MAIN)
        ticker = public.ticker_v3(symbol=TICKER_SYMBOL)
        data = ticker.get("data", [])
        if data:
            return float(data[0].get("lastPrice") or data[0].get("markPrice", 0))
    except Exception as e:
        print(f"⚠️ Ticker-Abruf fehlgeschlagen: {e}")
    return None


def execute_apex_trade(client, side, leverage, size_usd):
    print(f"📤 Sende {side}-Order an ApeX Omni...")
    order_side = "BUY" if side == "LONG" else "SELL"

    price = get_market_price()
    if not price or price <= 0:
        print("❌ Konnte keinen Marktpreis für BNB abrufen")
        return None

    size_bnb = size_usd / price
    margin_rate = str(round(1 / leverage, 4))

    try:
        client.set_initial_margin_rate_v3(symbol=SYMBOL, initialMarginRate=margin_rate)
        print(f"📊 Hebel {leverage}x gesetzt (Margin Rate: {margin_rate})")
    except Exception as e:
        print(f"⚠️ Fehler beim Setzen des Hebels: {e}")

    try:
        result = client.create_order_v3(
            symbol=SYMBOL,
            side=order_side,
            type="MARKET",
            size=str(round(size_bnb, 4)),
            timestampSeconds=time.time(),
            price=str(round(price, 2)),
        )
        if result and result.get("code") == 0:
            print(f"✅ Order erfolgreich: {result}")
            return result
        print(f"❌ Order fehlgeschlagen: {result}")
        return None
    except Exception as e:
        print(f"❌ Fehler bei ApeX-Order: {e}")
        return None


def main():
    print_status_header()

    client = init_apex_client()
    if client is None:
        return

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
            result = execute_apex_trade(client, action, leverage, trade_amount)
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
