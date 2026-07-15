import os
from datetime import datetime
from dotenv import load_dotenv
from bnbagent import ERC8004Agent, AgentEndpoint, EVMWalletProvider

load_dotenv()

AGENT_NAME = "ERC-8004 Agent Registration"


def print_status_header():
    print("=" * 50)
    print(f"🤖 {AGENT_NAME} – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def main():
    print_status_header()

    wallet = EVMWalletProvider(
        password=os.getenv("WALLET_PASSWORD"),
        private_key=os.getenv("PRIVATE_KEY"),
    )
    print(f"✅ Agent-Wallet verbunden: {wallet.address}")

    sdk = ERC8004Agent(network="bsc-testnet", wallet_provider=wallet)

    agent_uri = sdk.generate_agent_uri(
        name="BNB-Hack-Agent",
        description="Autonomous Trading Agent für den BNB Hack 2026 – nutzt CMC Daten und TWAK für Ausführung.",
        endpoints=[
            AgentEndpoint(
                name="ERC-8183",
                endpoint=os.getenv("AGENT_ENDPOINT_URL", "https://dein-agent-endpoint.com/api"),
                version="0.1.0",
            ),
        ],
    )

    result = sdk.register_agent(agent_uri=agent_uri)

    print("✅ Agent erfolgreich registriert!")
    print(f"🔢 Agent ID: {result['agentId']}")
    print(f"🔗 Transaction: {result['transactionHash']}")


if __name__ == "__main__":
    main()
