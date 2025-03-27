# fang_service/core/data_fetcher.py

import requests
import datetime
import time
from typing import Dict, Optional, Any
from requests.exceptions import RequestException, Timeout, HTTPError
from fang_service.app_variables import ALPHAVANTAGE_API_KEY, ALPHAVANTAGE_BASE_URL
from fang_service.core.logging_config import get_logger

logger = get_logger(__name__)

# Constants for the module
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def fetch_intraday_data(
    symbol: str, 
    interval: str = "60min", 
    output_size: str = "full",
    max_retries: int = MAX_RETRIES
) -> Optional[Dict[str, Dict[str, str]]]:
    """
    Fetch intraday stock data for a given symbol using the Alpha Vantage API.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        interval: Time interval between data points (default: 60min)
        output_size: Amount of data to retrieve (default: full)
        max_retries: Maximum number of retry attempts for failed requests
        
    Returns:
        Dictionary of time series data keyed by timestamp, or None if retrieval failed
        
    Example response structure:
    {
        "2023-03-24 10:00:00": {
            "1. open": "98.4500",
            "2. high": "98.8700",
            "3. low": "98.3600",
            "4. close": "98.7100",
            "5. volume": "2358035"
        },
        ...
    }
    """
    time_series_key = f"Time Series ({interval})"
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Prepare request parameters
            params = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": interval,
                "outputsize": output_size,
                "apikey": ALPHAVANTAGE_API_KEY
            }
            
            # Log request attempt (without API key for security)
            safe_params = {k: v for k, v in params.items() if k != "apikey"}
            safe_params["apikey"] = "***"
            logger.info(f"Fetching data from Alpha Vantage: {safe_params}")
            
            # Make the request with timeout
            response = requests.get(
                ALPHAVANTAGE_BASE_URL, 
                params=params, 
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Check for API error messages
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API error for {symbol}: {data['Error Message']}")
                return None
                
            # Check for rate limiting
            if "Note" in data and "API call frequency" in data["Note"]:
                logger.warning(f"Alpha Vantage rate limit reached: {data['Note']}")
                # Wait longer before retry if rate limited
                time.sleep(RETRY_DELAY * 5)
                retry_count += 1
                continue
                
            # Check for missing time series data
            if time_series_key not in data:
                logger.warning(f"{time_series_key} missing in response for {symbol}")
                return None
                
            # Extract and return time series data
            return data[time_series_key]
            
        except Timeout:
            logger.warning(f"Timeout fetching data for {symbol}. Attempt {retry_count + 1}/{max_retries}")
            
        except HTTPError as e:
            logger.error(f"HTTP error fetching data for {symbol}: {e.response.status_code} {e.response.reason}")
            # Don't retry for client errors (4xx), only server errors (5xx)
            if e.response.status_code < 500:
                return None
                
        except RequestException as e:
            logger.error(f"Request exception for {symbol}: {str(e)}")
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error for {symbol}: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {str(e)}", exc_info=True)
            return None
            
        # Exponential backoff for retries
        wait_time = RETRY_DELAY * (2 ** retry_count)
        logger.info(f"Retrying in {wait_time} seconds... (Attempt {retry_count + 1}/{max_retries})")
        time.sleep(wait_time)
        retry_count += 1
        
    # If we've exhausted retries
    logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
    return None

def filter_data_past_72_hours(intraday_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns only the data from the past 72 hours from the provided intraday data.
    
    Args:
        intraday_data: Dictionary of time series data keyed by timestamp strings
        
    Returns:
        Filtered dictionary containing only data from the past 72 hours
        
    Note:
        Timestamps in Alpha Vantage response are in the format: '2023-03-24 10:00:00'
    """
    if not intraday_data:
        logger.debug("No intraday data to filter")
        return {}

    # Calculate the cutoff timestamp (72 hours ago)
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=72)
    filtered = {}
    discarded_count = 0

    try:
        for timestamp_str, values in intraday_data.items():
            # Convert string time to datetime object for comparison
            dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            # Include data points newer than the cutoff
            if dt >= cutoff:
                filtered[timestamp_str] = values
            else:
                discarded_count += 1
                
        # Log summary of filtered results
        logger.info(f"Filtered data: kept {len(filtered)} records, discarded {discarded_count} older records")
        return filtered
        
    except (ValueError, TypeError) as e:
        logger.error(f"Error filtering data: {str(e)}")
        # Return what we can salvage if there's an error
        return filtered if filtered else {}