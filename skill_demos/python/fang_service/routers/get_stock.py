# fang_service/routers/get_stock.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from typing import Optional
import datetime

from fang_service.app_variables import SERVICE_API_KEY
from fang_service.core.logging_config import get_logger
from fang_service.core.stocks_cache import StocksCache

logger = get_logger(__name__)
router = APIRouter()

def verify_api_key(request: Request):
    header_key = request.headers.get("x-api-key")
    if header_key != SERVICE_API_KEY:
        logger.warning("Invalid API key attempt.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )
    return True

@router.get("/getStock")
def get_stock(symbol: str, date: str, hour: int, 
              _: bool = Depends(verify_api_key), 
              stocks_cache: StocksCache = Depends()):
    """
    Query the in-memory stock data for a specific symbol, date, and hour (0-23).
    """
    symbol = symbol.upper()
    try:
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        if not (0 <= hour <= 23):
            raise ValueError("Hour must be between 0 and 23.")

        # Build the expected key string from the cache
        # e.g. "2023-03-24 10:00:00" 
        hour_str = f"{hour:02d}:00:00"
        query_key = f"{dt.strftime('%Y-%m-%d')} {hour_str}"

        data_for_symbol = stocks_cache.get_data(symbol)
        if not data_for_symbol:
            logger.info(f"No data found in cache for symbol: {symbol}")
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        result = data_for_symbol.get(query_key)
        if not result:
            logger.info(f"No data found in cache for symbol: {symbol} at {query_key}")
            raise HTTPException(status_code=404, detail=f"No data for {symbol} at {query_key}")
        return {"symbol": symbol, "timestamp": query_key, "data": result}

    except ValueError as ve:
        logger.warning(f"Validation error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Unexpected error fetching stock data", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
