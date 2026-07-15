import os
import secrets
from datetime import datetime
from dotenv import load_dotenv
from bnbagent import EVMWalletProvider
from eth_account import Account

load_dotenv()

AGENT_NAME = "Wallet Generator"


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def main():
    print_status_header()

    password = os.getenv("WALLET_PASSWORD")
    if not password:
        print("❌ WALLET_PASSWORD nicht in .env gefunden.")
        print("📝 Setze WALLET_PASSWORD in .env (siehe .env.example) und starte erneut.")
        return

    private_key = "0x" + secrets.token_hex(32)
    account = Account.from_key(private_key)
    EVMWalletProvider(private_key=private_key, password=password)

    print("=== Deine neue Agent-Wallet ===")
    print(f"Wallet-Adresse: {account.address}")
    print(f"Privater Schlüssel: {private_key}")
    print("\n⚠️ Bewahre den privaten Schlüssel sicher auf!")
    print("📝 Trage PRIVATE_KEY und WALLET_PASSWORD in deine lokale .env ein (niemals committen).")


if __name__ == "__main__":
    main()
