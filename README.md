# Razor Bot - High-Performance MEV Trading Bot

A Python MEV bot designed for maximum transactions per minute (TPM) on PumpPortal, focusing on speed and visibility.

## Overview

Razor Bot is an optimized MEV (Maximal Extractable Value) execution tool that interacts directly with the PumpPortal API to perform rapid buy/sell cycles on Solana tokens. The bot prioritizes transaction count and speed over profit optimization.

## Project Structure

- `razor.py` - Core logic for the bot with rapid trading cycles
- `sell_tokens.py` - Utility script to sell all tokens in a wallet
- `.env` - Configuration file for API key and wallet address
- `logs/razor_log.txt` - Transaction and error logs
- `requirements.txt` - Python dependencies

## Features

- **Maximum TPM**: Optimized for highest possible transactions per minute
- **Direct PumpPortal API Integration**: Focused solely on PumpPortal for all transactions
- **High-Speed Parameters**: Fixed high priority fee (0.001 SOL) and increased slippage (15%)
- **RPC Endpoint Rotation**: Automatic switching between multiple Solana RPC providers
- **30-Minute Execution Window**: Focused trading during the trend boost period
- **Token Liquidation**: Separate utility for selling accumulated tokens
- **Comprehensive Logging**: Records all transactions, responses, and errors

## Setup Instructions

1. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Edit the `.env` file and add your PumpPortal API key and wallet address:
   ```
   PUMPPORTAL_API_KEY=your_api_key_here
   WALLET_ADDRESS=your_wallet_address_here
   ```

3. **Ensure Sufficient SOL Balance**:
   The bot requires a minimum SOL balance to operate effectively (recommended: 0.3+ SOL)

## Usage

### Trading Bot

Run the bot with:
```
python razor.py [TOKEN_ADDRESS]
```

The bot will:
1. Execute rapid buy/sell cycles for the specified token
2. Run for exactly 30 minutes to maximize token visibility
3. Track and report transactions per minute (TPM)
4. Automatically handle errors and retry failed transactions

### Token Selling Utility

To sell all tokens in your wallet:
```
python sell_tokens.py
```

This utility will:
1. Discover all tokens in your wallet with non-zero balances
2. Attempt to sell each token with appropriate slippage
3. Provide detailed logging of all sell operations

## Performance Metrics

- **Target TPM**: 150-200 transactions per minute
- **Trade Amount**: 0.015 SOL per trade
- **Priority Fee**: 0.001 SOL (fixed high-speed fee)
- **Slippage**: 15% (to guarantee execution)
- **Execution Duration**: 30 minutes

## Risk Warning

This bot is designed for speed and transaction count, not profit optimization. Use at your own risk and only with funds you can afford to lose.

## Customization

Key parameters can be adjusted in the `razor.py` file:
- `BUY_AMOUNT_SOL`: Amount of SOL to spend per trade (default: 0.015)
- `SLIPPAGE_PERCENTAGE`: Fixed slippage percentage (default: 15%)
- `PRIORITY_FEE_SOL`: Fixed priority fee (default: 0.001 SOL)
- `EXECUTION_MINUTES`: Duration of trading session (default: 30 minutes)
