"""
Routescan/Basedscan API Configuration
Free API for Base chain - https://basedscan.io/documentation/api
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Routescan/Basedscan API configuration (FREE!)
# Routescan unified API endpoint format:
# https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api
# Documentation: https://basedscan.io/documentation/api/etherscan-like/tokens
ROUTESCAN_API_KEY = os.getenv("ROUTESCAN_API_KEY", "rs_65f982566a2ca518dfcd4c4e")
ROUTESCAN_API_KEY_AERO = os.getenv("ROUTESCAN_API_KEY_AERO", "rs_e1254323f750d4644cf0d772")  # Second key for AERO tracking
ROUTESCAN_API_URL = "https://api.routescan.io/v2/network/mainnet/evm/8453/etherscan/api"  # Base chain (8453) via Routescan

# Token address
TOKEN_ADDRESS = "0x311935cd80b76769bf2ecc9d8ab7635b2139cf82"

# Analysis parameters
MIN_ORGANIC_VOLUME = 100
ROUND_TRIP_THRESHOLD = 0.95
SAME_ADDRESS_THRESHOLD = 0.98
