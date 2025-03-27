# fang_service/core/data_fetcher.py

import requests
import datetime
import time
import json
from typing import Dict, Optional, Any, Tuple
from requests.exceptions import RequestException, Timeout, HTTPError

from fang_service.app_variables import ALPHAVANTAGE_API_KEY, ALPHAVANTAGE_BASE_URL
from fang_service.core.logging_config import get_logger
from fang_service.core.exceptions import RateLimitError, NetworkError, DataRetrievalError, AuthenticationError

logger = get_logger(__name__)

# Constants for the module
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

def fetch_intraday_data(
    symbol: str, 
    interval: str = "60min", 
    output_size: str = "full",
    max_retries: int = MAX_RETRIES
) -> Dict[str, Dict[str, str]]:
    """
    Fetch intraday stock data for a given symbol using the Alpha Vantage API.
    
    This function makes a request to Alpha Vantage, handles errors, rate limiting,
    and retry logic to reliably fetch stock data.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        interval: Time interval between data points (default: 60min)
        output_size: Amount of data to retrieve (default: full)
        max_retries: Maximum number of retry attempts for failed requests
        
    Returns:
        Dictionary of time series data keyed by timestamp
        
    Raises:
        RateLimitError: If API rate limit is exceeded
        NetworkError: If network issues occur
        DataRetrievalError: If data cannot be retrieved
        AuthenticationError: If API key is invalid
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
                error_msg = data['Error Message']
                if "Invalid API call" in error_msg:
                    raise AuthenticationError(f"Invalid API key or request: {error_msg}")
                raise DataRetrievalError(f"Alpha Vantage API error for {symbol}: {error_msg}")
            
            # Check for API information (often includes rate limit info)
            if "Information" in data:
                info_message = data["Information"]
                logger.warning(f"Alpha Vantage API information for {symbol}: {info_message}")
                
                # Handle rate limiting info specifically
                if any(phrase in info_message.lower() for phrase in ["api call frequency", "standard api rate limit"]):
                    logger.error(f"Alpha Vantage rate limit reached: {info_message}")
                    
                    # Collect additional details for the error
                    details = {
                        "symbol": symbol,
                        "api_message": info_message,
                        "retry_after": "Unknown. Check Alpha Vantage documentation for rate limits."
                    }
                    
                    # If this is a hard rate limit (daily/monthly), signal with warning
                    if any(phrase in info_message.lower() for phrase in ["per day", "per month"]):
                        logger.error("Daily/monthly rate limit reached, cannot continue until reset")
                        if ALPHAVANTAGE_API_KEY and ALPHAVANTAGE_API_KEY.endswith("BQE9W"):  # Default key
                            details["api_key_info"] = "Using default API key which has limited quota. Consider getting your own key."
                            logger.error("Using default API key which has limited quota. Consider getting your own key.")
                        
                        raise RateLimitError(
                            message=f"Alpha Vantage rate limit reached: {info_message}",
                            details=details
                        )
                
                # Log full response for debugging
                logger.debug(f"Full Alpha Vantage response: {json.dumps(data)[:500]}...")
                
            # Check for rate limiting
            if "Note" in data and "API call frequency" in data["Note"]:
                note_message = data["Note"]
                logger.warning(f"Alpha Vantage rate limit reached: {note_message}")
                
                # Calculate retry time
                wait_time = RETRY_DELAY * (5 ** retry_count)
                
                details = {
                    "symbol": symbol,
                    "api_message": note_message,
                    "retry_after_seconds": wait_time
                }
                
                logger.info(f"Rate limit detected, waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
                retry_count += 1
                continue
                
            # Check for missing time series data
            if time_series_key not in data:
                logger.warning(f"{time_series_key} missing in response for {symbol}")
                logger.debug(f"Response keys: {list(data.keys())}")
                
                # Log a snippet of the response for debugging
                if data:
                    logger.debug(f"Response snippet: {str(data)[:500]}...")
                
                raise DataRetrievalError(
                    message=f"Invalid data format for {symbol}: {time_series_key} missing", 
                    details={"symbol": symbol, "available_keys": list(data.keys())}
                )
                
            # Extract time series data
            time_series_data = data[time_series_key]
            
            # Verify data is not empty
            if not time_series_data:
                logger.warning(f"Empty data set received for {symbol}")
                raise DataRetrievalError(
                    message=f"No data available for {symbol}",
                    details={"symbol": symbol}
                )
                
            return time_series_data
            
        except Timeout:
            logger.warning(f"Timeout fetching data for {symbol}. Attempt {retry_count + 1}/{max_retries}")
            
        except HTTPError as e:
            status_code = getattr(e.response, 'status_code', 0)
            logger.error(f"HTTP error fetching data for {symbol}: {status_code}")
            
            # Try to extract more details from the response
            try:
                error_content = e.response.text
                logger.error(f"Error response content: {error_content[:500]}")
            except:
                pass
                
            # Don't retry for client errors (4xx), only server errors (5xx)
            if status_code < 500:
                if status_code == 401 or status_code == 403:
                    raise AuthenticationError(
                        message=f"Authentication failed for Alpha Vantage API: {status_code}",
                        details={"symbol": symbol, "status_code": status_code}
                    )
                else:
                    raise DataRetrievalError(
                        message=f"Client error fetching data for {symbol}: {status_code}",
                        details={"symbol": symbol, "status_code": status_code}
                    )
                
        except RequestException as e:
            logger.error(f"Request exception for {symbol}: {str(e)}")
            if retry_count >= max_retries - 1:  # Last retry attempt
                raise NetworkError(
                    message=f"Network error connecting to Alpha Vantage API: {str(e)}",
                    details={"symbol": symbol, "error": str(e)}
                )
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error for {symbol}: {str(e)}")
            raise DataRetrievalError(
                message=f"Error parsing data for {symbol}: {str(e)}",
                details={"symbol": symbol, "error": str(e)}
            )
            
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {str(e)}", exc_info=True)
            raise DataRetrievalError(
                message=f"Unexpected error fetching data for {symbol}: {str(e)}",
                details={"symbol": symbol, "error": str(e)}
            )
            
        # Exponential backoff for retries
        wait_time = RETRY_DELAY * (2 ** retry_count)
        logger.info(f"Retrying in {wait_time} seconds... (Attempt {retry_count + 1}/{max_retries})")
        time.sleep(wait_time)
        retry_count += 1
        
    # If we've exhausted retries without raising an exception, raise one now
    logger.error(f"Failed to fetch data for {symbol} after {max_retries} attempts")
    raise NetworkError(
        message=f"Failed to fetch data for {symbol} after {max_retries} attempts",
        details={"symbol": symbol, "attempts": max_retries}
    )

def filter_data_past_72_hours(intraday_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns only the data from the past 72 hours from the provided intraday data.
    
    This function filters a dictionary of time-series data to only include entries
    from the past 72 hours, based on the current UTC time.
    
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
            dt = datetime.datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
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

def test_api_connectivity() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Test connectivity to the Alpha Vantage API.
    
    Performs a simple test query to check if the Alpha Vantage API
    is accessible and if the API key is valid.
    
    Returns:
        Tuple of (success, message, details) where:
        - success is a boolean
        - message contains details about the connection status
        - details is a dictionary with additional information
    """
    details = {
        "api_key_used": f"...{ALPHAVANTAGE_API_KEY[-4:]}",
        "api_url": ALPHAVANTAGE_BASE_URL,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        # Parameters for a minimal API call
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": "MSFT",  # Use a reliable symbol for testing
            "interval": "60min",
            "outputsize": "compact",  # Use compact to minimize data transfer
            "apikey": ALPHAVANTAGE_API_KEY
        }
        
        logger.info("Testing Alpha Vantage API connectivity")
        
        # Make the request with a shorter timeout for testing
        response = requests.get(
            ALPHAVANTAGE_BASE_URL,
            params=params,
            timeout=10
        )
        
        # Check HTTP status
        if response.status_code != 200:
            details["status_code"] = response.status_code
            return False, f"API returned status code {response.status_code}", details
        
        # Parse the response
        data = response.json()
        
        # Store partial response for inspection
        details["response_snippet"] = str(data)[:200] + "..."
        
        # Check for API error messages
        if "Error Message" in data:
            details["error"] = data['Error Message']
            return False, f"API error: {data['Error Message']}", details
        
        # Check for rate limiting or other info messages
        if "Information" in data:
            details["information"] = data["Information"]
            if any(phrase in data["Information"].lower() for phrase in ["api call frequency", "standard api rate limit"]):
                return False, f"API rate limit issue: {data['Information']}", details
            return False, f"API information: {data['Information']}", details
            
        # Check for expected data structure
        time_series_key = "Time Series (60min)"
        if time_series_key not in data:
            details["available_keys"] = list(data.keys())
            return False, f"Unexpected response format. Keys: {list(data.keys())}", details
            
        # If we have data, API is working
        if data[time_series_key]:
            first_timestamp = next(iter(data[time_series_key].keys()))
            details["latest_data_timestamp"] = first_timestamp
            return True, f"API connection successful. Latest data: {first_timestamp}", details
            
        return True, "API connection successful but no data returned", details
        
    except Timeout:
        details["error_type"] = "timeout"
        return False, "Timeout connecting to Alpha Vantage API", details
    except RequestException as e:
        details["error_type"] = "request"
        details["error"] = str(e)
        return False, f"Request error: {str(e)}", details
    except Exception as e:
        details["error_type"] = "unexpected"
        details["error"] = str(e)
        return False, f"Unexpected error: {str(e)}", details