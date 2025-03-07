#!/usr/bin/env python3
"""
Razor Bot - High-Transaction Pump Executor
Objective: Execute as many transactions as possible in 30 minutes to boost token visibility.
"""

import os
import time
import logging
import requests
import random
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/razor_log.txt"), logging.StreamHandler()],
)
logger = logging.getLogger("razor")

# Load environment variables
load_dotenv()
API_KEY = os.getenv("PUMPPORTAL_API_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# Constants
PUMPPORTAL_API_URL = "https://pumpportal.fun/api"  # Base API endpoint
BUY_AMOUNT_SOL = 0.015  # Amount of SOL to spend per trade
SLIPPAGE_PERCENTAGE = 15  # High slippage to ensure execution
PRIORITY_FEE = 0.001  # Fixed high priority fee for speed
MAX_RETRIES = 3  # Maximum number of retries for failed trades
RETRY_DELAY = 0.1  # Minimal delay between retries (seconds)
CYCLE_DURATION = 30 * 60  # 30 minutes in seconds

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

class RazorBot:
    def __init__(self):
        # Create a persistent session for faster HTTP requests
        self.session = requests.Session()
        
        # Pre-configure common headers for all requests
        self.session.headers.update({
            'User-Agent': 'RazorBot/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Cache API key in session params for all requests
        self.api_params = {"api-key": API_KEY}
        
        # RPC endpoint management
        self.current_rpc_index = 0
        
        # Performance tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.start_time = time.time()
        
        # Verify API key is set
        if not API_KEY:
            logger.error("PUMPPORTAL_API_KEY not set in .env file")
            sys.exit(1)
        
        logger.info("Razor Bot initialized")
        logger.info(f"Using {len(SOLANA_RPC_ENDPOINTS)} RPC endpoints")
        
    def format_token_address(self, token_address):
        """
        Format token address for PumpPortal API
        """
        token_address = token_address.strip()
        logger.info(f"Using token address: {token_address}")
        return token_address
        
    def rotate_rpc_endpoint(self):
        """
        Rotate to the next RPC endpoint
        """
        self.current_rpc_index = (self.current_rpc_index + 1) % len(SOLANA_RPC_ENDPOINTS)
        endpoint = SOLANA_RPC_ENDPOINTS[self.current_rpc_index]
        logger.info(f"Rotating to RPC endpoint: {endpoint}")
        return endpoint
    
    def get_current_rpc_endpoint(self):
        """
        Get the current RPC endpoint
        """
        return SOLANA_RPC_ENDPOINTS[self.current_rpc_index]
        
    def buy_token(self, token_address):
        """Buy token using PumpPortal API"""
        # Format token address for PumpPortal API
        formatted_token = self.format_token_address(token_address)
        
        payload = {
            "action": "buy",
            "mint": formatted_token,
            "amount": str(BUY_AMOUNT_SOL),
            "denominatedInSol": "true",
            "slippage": str(SLIPPAGE_PERCENTAGE),
            "priorityFee": str(PRIORITY_FEE),
            "rpcEndpoint": self.get_current_rpc_endpoint(),
            "skipPreflight": "true"
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Buying token {formatted_token} - Attempt {attempt}/{MAX_RETRIES}")
                
                response = self.session.post(
                    f"{PUMPPORTAL_API_URL}/trade",
                    params=self.api_params,
                    json=payload,
                    timeout=10  # Add timeout to prevent hanging
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    logger.warning("Rate limit hit on PumpPortal API")
                    self.rotate_rpc_endpoint()
                    payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    time.sleep(RETRY_DELAY)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # Check for success - either explicit success flag or signature with empty errors
                if ("success" in data and data["success"]) or ("signature" in data and data.get("errors", []) == []):
                    logger.info(f"Successfully bought token {formatted_token}")
                    if "txid" in data:
                        logger.info(f"Transaction signature: {data['txid']}")
                    elif "signature" in data:
                        logger.info(f"Transaction signature: {data['signature']}")
                    
                    self.successful_trades += 1
                    self.total_trades += 1
                    return data
                else:
                    error_msg = data.get('error', 'Unknown error')
                    if 'errors' in data and isinstance(data['errors'], list) and data['errors']:
                        error_msg = ', '.join(data['errors'])
                    logger.warning(f"Buy unsuccessful: {error_msg}")
                    
                    # If there's an RPC error, rotate endpoint
                    if "rpc" in error_msg.lower() or "timeout" in error_msg.lower():
                        self.rotate_rpc_endpoint()
                        payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    
                    time.sleep(RETRY_DELAY)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error buying token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Error buying token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                
        logger.error(f"Failed to buy token {formatted_token} after {MAX_RETRIES} attempts")
        self.failed_trades += 1
        self.total_trades += 1
        return None

    def sell_token(self, token_address, amount=None):
        """Sell token using PumpPortal API"""
        # Format token address for PumpPortal API
        formatted_token = self.format_token_address(token_address)
        
        payload = {
            "action": "sell",
            "mint": formatted_token,
            "amount": "100%" if amount is None else str(amount),
            "denominatedInSol": "false",
            "slippage": str(SLIPPAGE_PERCENTAGE),
            "priorityFee": str(PRIORITY_FEE),
            "rpcEndpoint": self.get_current_rpc_endpoint(),
            "skipPreflight": "true"
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Selling token {formatted_token} - Attempt {attempt}/{MAX_RETRIES}")
                
                response = self.session.post(
                    f"{PUMPPORTAL_API_URL}/trade",
                    params=self.api_params,
                    json=payload,
                    timeout=10  # Add timeout to prevent hanging
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    logger.warning("Rate limit hit on PumpPortal API")
                    self.rotate_rpc_endpoint()
                    payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    time.sleep(RETRY_DELAY)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # Check for success - either explicit success flag or signature with empty errors
                if ("success" in data and data["success"]) or ("signature" in data and data.get("errors", []) == []):
                    logger.info(f"Successfully sold token {formatted_token}")
                    if "txid" in data:
                        logger.info(f"Transaction signature: {data['txid']}")
                    elif "signature" in data:
                        logger.info(f"Transaction signature: {data['signature']}")
                    
                    self.successful_trades += 1
                    self.total_trades += 1
                    return data
                else:
                    error_msg = data.get('error', 'Unknown error')
                    if 'errors' in data and isinstance(data['errors'], list) and data['errors']:
                        error_msg = ', '.join(data['errors'])
                    logger.warning(f"Sell unsuccessful: {error_msg}")
                    
                    # If there's an RPC error, rotate endpoint
                    if "rpc" in error_msg.lower() or "timeout" in error_msg.lower():
                        self.rotate_rpc_endpoint()
                        payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                    
                    time.sleep(RETRY_DELAY)
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error selling token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"Error selling token (attempt {attempt}): {str(e)}")
                self.rotate_rpc_endpoint()
                payload["rpcEndpoint"] = self.get_current_rpc_endpoint()
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                
        logger.error(f"Failed to sell token {formatted_token} after {MAX_RETRIES} attempts")
        self.failed_trades += 1
        self.total_trades += 1
        return None

    def execute_trade_cycle(self, token_address):
        """Execute a complete buy-sell cycle for a token"""
        # Format token address for logging
        formatted_token = self.format_token_address(token_address)
        logger.info(f"Starting trade cycle for token {formatted_token}")
        
        # Buy token
        buy_result = self.buy_token(token_address)
        if not buy_result:
            logger.error("Buy operation failed, skipping sell")
            return False
            
        # Extract token amount received from buy result if available
        token_amount = None
        if buy_result and "amount_out" in buy_result:
            token_amount = buy_result["amount_out"]
            
        # Sell token immediately without waiting
        sell_result = self.sell_token(token_address, token_amount)
        if not sell_result:
            logger.error("Sell operation failed")
            return False
            
        logger.info(f"Completed trade cycle for token {formatted_token}")
        return True
        
    def run(self, token_address, max_duration=CYCLE_DURATION):
        """Run the bot for a specified duration"""
        logger.info(f"Starting Razor Bot in high-TPM mode for {max_duration/60:.1f} minutes")
        logger.info(f"Target token: {token_address}")
        logger.info(f"Trade amount: {BUY_AMOUNT_SOL} SOL")
        logger.info(f"Slippage: {SLIPPAGE_PERCENTAGE}%")
        logger.info(f"Priority fee: {PRIORITY_FEE} SOL")
        
        cycle_count = 0
        self.start_time = time.time()
        end_time = self.start_time + max_duration
        
        try:
            while time.time() < end_time:
                # Execute trade cycle
                success = self.execute_trade_cycle(token_address)
                cycle_count += 1
                
                # Log progress
                elapsed = time.time() - self.start_time
                remaining = max_duration - elapsed
                tpm = (self.total_trades / elapsed) * 60 if elapsed > 0 else 0
                
                logger.info(f"Cycle {cycle_count} completed. Success: {success}")
                logger.info(f"Stats: {self.successful_trades}/{self.total_trades} successful trades ({tpm:.1f} TPM)")
                logger.info(f"Time remaining: {remaining/60:.1f} minutes")
                
                # No delay between cycles for maximum TPM
        
        except KeyboardInterrupt:
            logger.info("Bot execution interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
        finally:
            # Final stats
            total_time = time.time() - self.start_time
            final_tpm = (self.total_trades / total_time) * 60 if total_time > 0 else 0
            success_rate = (self.successful_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
            
            logger.info("=== Final Statistics ===")
            logger.info(f"Duration: {total_time/60:.1f} minutes")
            logger.info(f"Total trades: {self.total_trades}")
            logger.info(f"Successful trades: {self.successful_trades} ({success_rate:.1f}%)")
            logger.info(f"Failed trades: {self.failed_trades}")
            logger.info(f"Transactions per minute: {final_tpm:.1f}")
            
            return {
                "duration": total_time,
                "total_trades": self.total_trades,
                "successful_trades": self.successful_trades,
                "failed_trades": self.failed_trades,
                "tpm": final_tpm
            }

if __name__ == "__main__":
    try:
        # Get token address from command line or use default
        token_address = sys.argv[1] if len(sys.argv) > 1 else input("Enter token address: ")
        
        # Run the bot
        bot = RazorBot()
        bot.run(token_address)
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
