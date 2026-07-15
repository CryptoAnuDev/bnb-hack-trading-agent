# BNB Hack 2026 – AI Trading Agent

[![BNB Chain](https://img.shields.io/badge/BNB_Chain-Mainnet-yellow)](https://www.bnbchain.org/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> Autonomous Trading Agent for BNB Hack 2026 – Track 1: Autonomous Trading Agents  
> **CoinMarketCap × Trust Wallet × BNB Chain**

---

## Overview

This project contains five autonomous trading agents for different platforms. All secrets are loaded exclusively from a local `.env` file (never commit real keys).

| Agent | File | Status |
|:---|:---|:---|
| LUNC Trader (BSC) | `lunc_trader.py` | ✅ RSI + SMA via Binance, PancakeSwap USDC↔LUNC |
| PancakeSwap Meme-Coin Sniper | `pancake_trader.py` | ✅ Main agent (TP/SL + persistence) |
| Hyperliquid Perps | `hyperliquid_trader.py` | ⚠️ Requires wallet onboarding |
| ApeX Omni Perps | `apex_trader.py` | ⚠️ SDK integrated – needs API + Omni seeds |
| AsterDEX Perps | `asterdex_trader.py` | ❌ API keys + connector required |
| Pump.fun Sniper | `pumpfun_trader.py` | ⚠️ pump-swap + DexScreener – needs Solana RPC |

---

## Project Structure

```
bnb-trading-agent/
├── .env.example          # Template for environment variables
├── .gitignore
├── README.md
├── requirements.txt
├── storage/
│   ├── __init__.py
│   ├── positions.py      # Open position persistence
│   └── trades.py         # Trade history
├── lunc_trader.py          # LUNC RSI+SMA agent (PancakeSwap)
├── pancake_trader.py     # Main BSC spot sniper
├── hyperliquid_trader.py
├── apex_trader.py
├── asterdex_trader.py
├── pumpfun_trader.py
├── create_wallet.py      # Generate a new agent wallet
├── register_agent.py     # ERC-8004 testnet registration
└── index.html            # Optional landing page
```

---

## Installation

```bash
git clone https://github.com/CryptoAnuDev/bnb-trading-agent.git
cd bnb-trading-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials (never commit .env)
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the required values:

| Variable | Required for | Description |
|:---|:---|:---|
| `WALLET_PASSWORD` | BSC agents | Wallet encryption password |
| `PRIVATE_KEY` | BSC + Hyperliquid | EVM private key (0x...) |
| `APOLLOX_API_KEY` / `APOLLOX_API_SECRET` | AsterDEX | ApolloX API credentials |
| `APEX_API_KEY` / `APEX_API_SECRET` / `APEX_PASSPHRASE` | ApeX | ApeX Omni API credentials |
| `APEX_OMNI_SEED` / `APEX_L2_KEY` | ApeX | Omni Key (seeds) from key management |
| `HYPERLIQUID_MAIN_ADDRESS` | Hyperliquid | Main wallet address (optional) |
| `SOLANA_PRIVATE_KEY` / `SOLANA_RPC_URL` | Pump.fun | Solana key (Base58) + RPC endpoint |
| `LUNC_DRY_RUN` / `LUNC_POSITION_SIZE_USDC` | LUNC | Dry-run mode and trade size (default 5 USDC) |

---

## LUNC Agent

Strategy: **RSI + SMA crossover** with Binance price data and PancakeSwap execution on BSC.

| Signal | Condition |
|:---|:---|
| Buy | RSI < 30 and SMA20 > SMA50 |
| Sell | RSI > 70, Take-Profit (+20%), or Stop-Loss (-15%) |

```bash
# Simulated run (no on-chain trades)
LUNC_DRY_RUN=true python lunc_trader.py

# Live run (requires USDC on BSC wallet)
python lunc_trader.py
```

Persistence: `lunc_positions.json`, `lunc_trades.json`

---

## Usage

```bash
# LUNC trader (RSI + SMA)
python lunc_trader.py

# Main agent (PancakeSwap sniper with TP/SL)
python pancake_trader.py

# Perpetual traders
python hyperliquid_trader.py
python apex_trader.py
python asterdex_trader.py

# Solana sniper
python pumpfun_trader.py

# Utilities
python create_wallet.py
python register_agent.py
```

---

## Persistence

The PancakeSwap agent stores data locally (gitignored):

- `positions.json` – open positions (resumed on restart)
- `trades.json` – full trade history with timestamps and PnL

---

## ApeX Omni Setup

1. Open https://omni.apex.exchange/keyManagement
2. Generate **API Key** (key, secret, passphrase)
3. Generate **Omni Key** (seeds) – save as `APEX_OMNI_SEED` in `.env`
4. Run: `python apex_trader.py`

Orders use the official `apexomni` SDK with `HttpPrivateSign` and ZK-L2 signatures.

## Pump.fun Setup

1. Create a Solana wallet (Phantom/Solflare) and export the Base58 private key
2. Use a **paid RPC** (Helius, QuickNode) – set `SOLANA_RPC_URL` in `.env`
3. Fund the wallet with SOL for trades + fees
4. Run: `python pumpfun_trader.py`

The agent discovers new tokens via DexScreener and buys via the `pump-swap` library.

---

## GitHub Actions

The workflow in `.github/workflows/trade.yml` runs `pancake_trader.py` daily. Required GitHub Secrets:

- `WALLET_PASSWORD`
- `PRIVATE_KEY`
- `TWAK_ACCESS_ID` (optional)
- `TWAK_HMAC_SECRET` (optional)

---

## Security

- **Never commit** `.env`, `positions.json`, or `trades.json`
- All agents load secrets via `os.getenv()` after `load_dotenv()`
- Use `.env.example` as the only template in the repository
- Rotate any key that was ever committed or exposed

---

## License

MIT – see [LICENSE](LICENSE).
