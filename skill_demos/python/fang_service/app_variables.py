# fang_service/app_variables.py

import os
from typing import List

# API Keys with environment variable fallbacks for security
# Default values are for development only - NEVER use these in production
ALPHAVANTAGE_API_KEY = os.environ.get(
    "ALPHAVANTAGE_API_KEY", 
    "BDJ3XW1R415Q71VW"  # Fallback for development only
)

SERVICE_API_KEY = os.environ.get(
    "SERVICE_API_KEY",
    "8f4b9e7d1c6a2305f8e9d7b6c5a4e3f2d1c0b9a8f7e6d5c4b3a2918f7e6d5c4"  # Fallback for development only
)

# Datadog APM configuration
DATADOG_ENABLED = os.environ.get("DATADOG_ENABLED", "false").lower() == "true"
DATADOG_SERVICE_NAME = os.environ.get("DATADOG_SERVICE_NAME", "fang_service")
DATADOG_ENV = os.environ.get("DATADOG_ENV", "dev")
DATADOG_VERSION = os.environ.get("DATADOG_VERSION", "1.0.0")

# Platform detection for stats collection
# Options: "windows", "linux", "none"
PLATFORM = os.environ.get("PLATFORM", "windows")

# Run type: "persistent" (continuous running) or "single-run" (fetch once)
RUN_TYPE = os.environ.get("RUN_TYPE", "persistent")

# List of FANG stocks to track
# Commonly: FB (META), AMZN, NFLX, GOOG, or adjust as needed
DEFAULT_SYMBOLS = ["FB", "AMZN", "NFLX", "GOOG"]
FANG_SYMBOLS: List[str] = os.environ.get("FANG_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",")

# How often (in hours) we fetch new data from the API
FETCH_INTERVAL_HOURS = int(os.environ.get("FETCH_INTERVAL_HOURS", "1"))

# Alpha Vantage API base URL
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# API rate limiting (requests per minute)
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))

# Cache settings
MAX_CACHE_AGE_HOURS = 72  # How far back to keep data