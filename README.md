# BNB Hack 2026 – AI Trading Agent

[![BNB Chain](https://img.shields.io/badge/BNB_Chain-Mainnet-yellow)](https://www.bnbchain.org/)
[![Python](https://img.shields.io/badge/Python-3.14-blue)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success)]()

> 🤖 Autonomous Trading Agent for BNB Hack 2026 – Track 1: Autonomous Trading Agents  
> **CoinMarketCap × Trust Wallet × BNB Chain**

---

## 📌 Overview

This agent trades **fully autonomously** on the BNB Chain. It combines **market sentiment analysis** (Fear & Greed Index) with **fast meme-coin snipe trades**.

### Core Features

| Feature | Description |
|:---|:---|
| **Fear & Greed Strategy** | Buys on **Extreme Fear** (≤ 25), sells on **Extreme Greed** (≥ 75) |
| **Meme-Coin Sniper** | Discovers new promising BSC tokens via DexScreener API and executes automatic buys |
| **Risk Management** | Drawdown limit (30%), position limit (20%), daily loss limit (10%) |
| **Autonomous Operation** | Runs in background (manually or via GitHub Actions) |
| **Multi-Platform** | PancakeSwap (Spot) + Pump.fun (Solana) |

---

## 🛠️ Tech Stack

| Component | Technology |
|:---|:---|
| **Blockchain** | BNB Smart Chain (BSC), Solana (Pump.fun) |
| **Language** | Python 3.14 |
| **Smart Contract Interaction** | `web3.py`, `bnbagent` |
| **Token Discovery** | DexScreener API (free) |
| **DEX** | PancakeSwap Router V2 |
| **Wallet** | Trust Wallet Agent Kit (TWAK) |
| **API** | CoinMarketCap Agent Hub |

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/CryptoAnu-dev/bnb-hack-trading-agent.git
cd bnb-hack-trading-agent
