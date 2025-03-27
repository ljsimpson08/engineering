# fang_service/routers/alldata.py

from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import Dict, Any, List, Optional
import datetime

from fang_service.app_variables import SERVICE_API_KEY, FANG_SYMBOLS, ALPHAVANTAGE_API_KEY
from fang_service.core.logging_config import get_logger
from fang_service.core.db_service import StockDataService
from fang_service.routers.get_stock import verify_api_key

logger = get_logger(__name__)
router = APIRouter()

@router.get("/allData", summary="Get data for all FANG stocks")
def get_all_data(
    response: Response,
    _: bool = Depends(verify_api_key),
    stock_service: StockDataService = Depends()
) -> Dict[str, Any]:
    """
    Retrieve all available stock data for all configured FANG symbols.
    
    Returns a dictionary with each symbol as a key and its time series data as values.
    If no data is found for any symbol, returns a message indicating no data was found.
    
    Authentication required via x-api-key header.
    
    Returns:
        Dictionary of stock data by symbol, or message if no data found
    """
    result = {}
    service_stats = stock_service.get_cache_stats()
    
    # Check if DB has been initialized
    if service_stats["update_count"] == 0:
        logger.warning("Database has never been updated - initialization may have failed")
        # Force HTTP 200 response
        response.status_code = status.HTTP_200_OK
        return {
            "message": "no data found",
            "reason": "database has not been initialized",
            "status": service_stats,
            "api_key_info": f"Using API key ending in ...{ALPHAVANTAGE_API_KEY[-4:]}",
            "likely_cause": "Alpha Vantage API rate limits or invalid API key"
        }
    
    # Check if DB update is stale
    if service_stats["last_update"]:
        last_update = datetime.datetime.fromisoformat(service_stats["last_update"].replace("Z", "+00:00"))
        cache_age_hours = (datetime.datetime.utcnow() - last_update).total_seconds() / 3600
        if cache_age_hours > 3:  # If DB hasn't been updated in over 3 hours
            logger.warning(f"Data is stale - last updated {cache_age_hours:.1f} hours ago")
    
    # Gather data for all configured FANG symbols
    symbols_with_data = []
    for symbol in FANG_SYMBOLS:
        data = stock_service.get_data(symbol)
        if data:
            result[symbol] = data
            symbols_with_data.append(symbol)
    
    # Log helpful diagnostic info about which symbols have data
    if symbols_with_data:
        logger.info(f"Found data for {len(symbols_with_data)}/{len(FANG_SYMBOLS)} symbols: {', '.join(symbols_with_data)}")
    
    # If no data found, return a 200 response with a message
    if not result:
        logger.warning("No data available for any symbols")
        missing_symbols = [s for s in FANG_SYMBOLS if s not in symbols_with_data]
        
        # Explicitly set 200 OK status code
        response.status_code = status.HTTP_200_OK
        
        return {
            "message": "no data found",
            "symbols_checked": FANG_SYMBOLS,
            "missing_symbols": missing_symbols,
            "cache_age_hours": cache_age_hours if "cache_age_hours" in locals() else None,
            "api_key_info": f"Using API key ending in ...{ALPHAVANTAGE_API_KEY[-4:]}",
            "help": "The default API key may be rate-limited. Try using your own API key by setting the ALPHAVANTAGE_API_KEY environment variable.",
            "documentation": "https://www.alphavantage.co/documentation/"
        }
    
    # Successfully found data - return with 200 OK
    response.status_code = status.HTTP_200_OK
    return result

@router.get("/symbolData/{symbol}", summary="Get all data for a specific symbol")
def get_symbol_data(
    symbol: str, 
    response: Response,
    _: bool = Depends(verify_api_key),
    stock_service: StockDataService = Depends()
) -> Dict[str, Any]:
    """
    Get all available stock data for a specific symbol.
    
    Retrieves the complete time series data for the requested symbol.
    Returns a detailed error message if no data is found for the symbol.
    
    Authentication required via x-api-key header.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        
    Returns:
        Dictionary with symbol as the key and its time series data as the value
    """
    symbol = symbol.upper()
    
    # Get data for the specified symbol
    data = stock_service.get_data(symbol)
    
    # Check if we have data for this symbol
    if not data:
        # Get list of symbols that do have data for more helpful error message
        symbols_with_data = stock_service.get_symbols_with_data()
        
        logger.info(f"No data found in database for symbol: {symbol}")
        
        # Force HTTP 200 OK status code
        response.status_code = status.HTTP_200_OK
        
        return {
            "message": f"No data found for {symbol}",
            "available_symbols": symbols_with_data,
            "requested_symbol": symbol,
            "api_key_info": f"Using API key ending in ...{ALPHAVANTAGE_API_KEY[-4:]}",
            "help": "The default API key may be rate-limited. Try using your own API key by setting the ALPHAVANTAGE_API_KEY environment variable.",
            "alpha_vantage_status": "Please check Alpha Vantage rate limits and API key validity"
        }
    
    # Return data in the expected format with 200 OK
    response.status_code = status.HTTP_200_OK
    return {symbol: data}

@router.get("/availableSymbols", summary="Get list of symbols with available data")
def get_available_symbols(
    response: Response,
    _: bool = Depends(verify_api_key),
    stock_service: StockDataService = Depends()
) -> Dict[str, List[str]]:
    """
    Get a list of all symbols that currently have data in the database.
    
    This endpoint is useful for discovering which symbols have data
    before making requests to /symbolData/{symbol} or /getStock.
    
    Authentication required via x-api-key header.
    
    Returns:
        Dictionary with list of available symbols
    """
    symbols = stock_service.get_symbols_with_data()
    
    # Always return HTTP 200 OK
    response.status_code = status.HTTP_200_OK
    
    if not symbols:
        return {
            "available_symbols": [],
            "message": "No symbols have data available",
            "api_key_info": f"Using API key ending in ...{ALPHAVANTAGE_API_KEY[-4:]}",
            "help": "The default API key may be rate-limited. Try using your own API key by setting the ALPHAVANTAGE_API_KEY environment variable."
        }
    
    return {"available_symbols": symbols}

@router.get("/status", summary="Get API data status")
def get_api_status(
    response: Response,
    stock_service: StockDataService = Depends()
) -> Dict[str, Any]:
    """
    Get detailed information about the data status and API configuration.
    
    This endpoint provides detailed diagnostic information about the 
    Alpha Vantage API connection, database status, and available data.
    It's useful for troubleshooting data access issues.
    
    Returns:
        Dictionary with API and data status information
    """
    service_stats = stock_service.get_cache_stats()
    symbols_with_data = stock_service.get_symbols_with_data()
    
    cache_age_seconds = service_stats.get("cache_age_seconds")
    cache_age_hours = cache_age_seconds / 3600 if cache_age_seconds else None
    
    # Always return HTTP 200 OK
    response.status_code = status.HTTP_200_OK
    
    return {
        "alpha_vantage": {
            "api_key_used": f"...{ALPHAVANTAGE_API_KEY[-4:]}",
            "base_url": "https://www.alphavantage.co/query",
            "documentation": "https://www.alphavantage.co/documentation/"
        },
        "database": {
            "status": "empty" if not symbols_with_data else "populated",
            "symbols_with_data": symbols_with_data,
            "symbols_missing": [s for s in FANG_SYMBOLS if s not in symbols_with_data],
            "update_count": service_stats["update_count"],
            "failed_updates": service_stats["failed_updates"],
            "last_update": service_stats["last_update"],
            "cache_age_hours": round(cache_age_hours, 2) if cache_age_hours else None,
            "db_stats": service_stats.get("db_stats", {})
        },
        "diagnostics": {
            "possible_issues": [
                "Alpha Vantage API rate limiting (25 requests/day for free tier)",
                "Invalid API key",
                "Network connectivity issues",
                "API response format changes"
            ],
            "resolution_steps": [
                "Set your own Alpha Vantage API key via the ALPHAVANTAGE_API_KEY environment variable",
                "Subscribe to a premium Alpha Vantage plan for higher rate limits",
                "Check network connectivity to alphavantage.co",
                "Verify API key validity at https://www.alphavantage.co/support/#api-key"
            ]
        },
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }