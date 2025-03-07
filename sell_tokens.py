#!/usr/bin/env python3
"""
Sell Tokens Script - Liquidate all tokens in wallet
"""

import os
import time
import logging
import requests
import sys
from dotenv import load_dotenv

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/sell_log.txt"), logging.StreamHandler()],
)
logger = logging.getLogger("token_seller")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("PUMPPORTAL_API_KEY")

# Constants
PUMPPORTAL_API_URL = "https://pumpportal.fun/api"  # Base API endpoint
SLIPPAGE_PERCENTAGE = 15  # High slippage to ensure execution
PRIORITY_FEE = 0.0005  # Lower priority fee to save SOL
MAX_RETRIES = 5  # Maximum number of retries for failed trades

# Solana RPC endpoints for rotation
SOLANA_RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana",
    "https://solana-mainnet.g.alchemy.com/v2/demo",
    "https://mainnet.solana.blockdaemon.tech",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://mainnet.helius-rpc.com/?api-key=1d8740dc-e5f4-421c-b823-e1bad1889eff"
]

class TokenSeller:
    def __init__(self):
        # Create a persistent session for faster HTTP requests
        self.session = requests.Session()
        
        # Pre-configure common headers for all requests
        self.session.headers.update({
            'User-Agent': 'TokenSeller/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Cache API key in session params for all requests
        self.api_params = {"api-key": API_KEY}
        
        # RPC endpoint management
        self.current_rpc_index = 0
        
        # Verify API key is set
        if not API_KEY:
            logger.error("PUMPPORTAL_API_KEY not set in .env file")
            sys.exit(1)
        
        logger.info("Token Seller initialized")
        
    def get_current_rpc_endpoint(self):
        """Get the current RPC endpoint"""
        return SOLANA_RPC_ENDPOINTS[self.current_rpc_index]
        
    def rotate_rpc_endpoint(self):
        """Rotate to the next RPC endpoint"""
        self.current_rpc_index = (self.current_rpc_index + 1) % len(SOLANA_RPC_ENDPOINTS)
        endpoint = SOLANA_RPC_ENDPOINTS[self.current_rpc_index]
        logger.info(f"Rotating to RPC endpoint: {endpoint}")
        return endpoint
        
    def sell_token(self, token_address):
        """Sell token using PumpPortal API"""
        token_address = token_address.strip()
        logger.info(f"Attempting to sell token: {token_address}")
        
        payload = {
            "action": "sell",
            "mint": token_address,
            "amount": "100%",  # Sell all tokens
            "denominatedInSol": "false",
            "slippage": str(SLIPPAGE_PERCENTAGE),
            "priorityFee": str(PRIORITY_FEE),
            "rpcEndpoint": self.get_current_rpc_endpoint(),
            "skipPreflight": "true"
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Selling token {token_address} - Attempt {attempt}/{MAX_RETRIES}")
                
                response = self.session.post(
                    f"{PUMPPORTAL_API_URL}/trade",
                    params=self.api_params,
                    json=payload,
                    timeout=15  # Longer timeout for selling
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    logger.warning("Rate limit hit on PumpPortal API")
                    self.rotate_rpc_endpoint()
                    payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    time.sleep(2)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # Check for success - either explicit success flag or signature with empty errors
                if ("success" in data and data["success"]) or ("signature" in data and data.get("errors", []) == []):
                    logger.info(f"Successfully sold token {token_address}")
                    if "txid" in data:
                        logger.info(f"Transaction signature: {data['txid']}")
                    elif "signature" in data:
                        logger.info(f"Transaction signature: {data['signature']}")
                    return True
                else:
                    error_msg = data.get('error', 'Unknown error')
                    if 'errors' in data and isinstance(data['errors'], list) and data['errors']:
                        error_msg = ', '.join(data['errors'])
                    logger.warning(f"Sell unsuccessful: {error_msg}")
                    
                    # If there's an RPC error, rotate endpoint
                    if "rpc" in error_msg.lower() or "timeout" in error_msg.lower():
                        self.rotate_rpc_endpoint()
                        payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    
                    time.sleep(2)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error selling token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(2)
            except Exception as e:
                logger.error(f"Error selling token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                
        logger.error(f"Failed to sell token {token_address} after {MAX_RETRIES} attempts")
        return False

    def get_wallet_tokens(self, wallet_address):
        """Get all tokens in the wallet"""
        logger.info(f"Checking tokens in wallet: {wallet_address}")
        
        try:
            # Use Solana RPC to get token accounts
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = self.session.post(
                self.get_current_rpc_endpoint(),
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            tokens = []
            if "result" in data and "value" in data["result"]:
                for account in data["result"]["value"]:
                    try:
                        token_data = account["account"]["data"]["parsed"]["info"]
                        mint = token_data["mint"]
                        amount = token_data["tokenAmount"]["uiAmount"]
                        if amount > 0:  # Only include tokens with non-zero balance
                            tokens.append({
                                "mint": mint,
                                "amount": amount
                            })
                    except (KeyError, TypeError):
                        continue
            
            logger.info(f"Found {len(tokens)} tokens with non-zero balance")
            return tokens
        except Exception as e:
            logger.error(f"Error getting wallet tokens: {str(e)}")
            return []

    def sell_all_tokens(self, wallet_address):
        """Sell all tokens in the wallet"""
        tokens = self.get_wallet_tokens(wallet_address)
        
        if not tokens:
            logger.info("No tokens found to sell")
            return
        
        logger.info(f"Attempting to sell {len(tokens)} tokens")
        
        for token in tokens:
            mint = token["mint"]
            amount = token["amount"]
            logger.info(f"Selling {amount} of token {mint}")
            success = self.sell_token(mint)
            if success:
                logger.info(f"Successfully sold token {mint}")
            else:
                logger.error(f"Failed to sell token {mint}")
            
            # Wait a bit between sells to avoid rate limiting
            time.sleep(2)
        
        logger.info("Finished selling all tokens")

if __name__ == "__main__":
    try:
        # Get wallet address from .env
        wallet_address = os.getenv("WALLET_ADDRESS")
        if not wallet_address:
            wallet_address = input("Enter wallet address: ")
        
        # Create seller and sell all tokens
        seller = TokenSeller()
        
        # If token address is provided as argument, sell just that token
        if len(sys.argv) > 1:
            token_address = sys.argv[1]
            logger.info(f"Selling specific token: {token_address}")
            seller.sell_token(token_address)
        else:
            # Otherwise sell all tokens in the wallet
            logger.info(f"Selling all tokens in wallet: {wallet_address}")
            seller.sell_all_tokens(wallet_address)
            
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
