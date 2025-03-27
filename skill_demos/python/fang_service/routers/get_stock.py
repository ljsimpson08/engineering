# fang_service/routers/get_stock.py

from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from typing import Dict, Any, Optional
import datetime
from pydantic import BaseModel, Field

from fang_service.app_variables import SERVICE_API_KEY
from fang_service.core.logging_config import get_logger
from fang_service.core.db_service import StockDataService

logger = get_logger(__name__)
router = APIRouter()

# Response models for better API documentation and type checking
class StockDataPoint(BaseModel):
    """Individual stock data point with OHLCV values"""
    open: str = Field(..., alias="1. open", description="Opening price")
    high: str = Field(..., alias="2. high", description="Highest price in period")
    low: str = Field(..., alias="3. low", description="Lowest price in period")
    close: str = Field(..., alias="4. close", description="Closing price")
    volume: str = Field(..., alias="5. volume", description="Trading volume")
    
    class Config:
        allow_population_by_field_name = True

class StockResponse(BaseModel):
    """Stock data response structure"""
    symbol: str = Field(..., description="Stock symbol (e.g., AMZN)")
    timestamp: str = Field(..., description="Data timestamp (e.g., 2023-03-24 10:00:00)")
    data: StockDataPoint = Field(..., description="Stock data point values")

def verify_api_key(request: Request) -> bool:
    """
    Verify the API key provided in the request headers.
    
    Args:
        request: FastAPI request object containing headers
        
    Returns:
        True if API key is valid
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    header_key = request.headers.get("x-api-key")
    
    # For security, don't provide different error messages for missing vs invalid keys
    if header_key != SERVICE_API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return True

@router.get(
    "/getStock", 
    response_model=StockResponse,
    summary="Get stock data for a specific date and hour",
    response_description="Stock data for the requested symbol, date, and hour"
)
def get_stock(
    symbol: str = Query(..., description="Stock symbol (e.g., FB, AMZN, NFLX, GOOG)"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    hour: int = Query(..., description="Hour of the day (0-23)"),
    _: bool = Depends(verify_api_key), 
    stock_service: StockDataService = Depends()
) -> Dict[str, Any]:
    """
    Query the database for stock data for a specific symbol, date, and hour (0-23).
    
    This endpoint retrieves a specific data point from the database based on the 
    symbol, date, and hour provided. The data is sourced from Alpha Vantage and
    stored in the database for performance.
    
    Authentication required via x-api-key header.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        date: Date in YYYY-MM-DD format
        hour: Hour of the day (0-23)
        
    Returns:
        Dictionary with symbol, timestamp, and stock data
        
    Raises:
        HTTPException 400: If the date or hour is invalid
        HTTPException 404: If no data is found for the specified parameters
        HTTPException 500: For unexpected server errors
    """
    symbol = symbol.upper()
    try:
        # Validate date format
        try:
            dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Expected format: YYYY-MM-DD")

        # Validate hour range
        if not (0 <= hour <= 23):
            raise ValueError(f"Hour must be between 0 and 23, got: {hour}")

        # Build the expected key string from the database
        # e.g. "2023-03-24 10:00:00" 
        hour_str = f"{hour:02d}:00:00"
        query_key = f"{dt.strftime('%Y-%m-%d')} {hour_str}"

        # Check if we have data for this symbol
        data_for_symbol = stock_service.get_data(symbol)
        if not data_for_symbol:
            available_symbols = stock_service.get_symbols_with_data()
            logger.info(f"No data found in database for symbol: {symbol}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail={
                    "message": f"No data for {symbol}",
                    "available_symbols": available_symbols
                }
            )

        # Check if we have data for this specific timestamp
        result = data_for_symbol.get(query_key)
        if not result:
            # Get available timestamps to help client troubleshoot
            available_dates = sorted(set(ts.split()[0] for ts in data_for_symbol.keys()))
            available_hours = sorted(set(int(ts.split()[1].split(':')[0]) for ts in data_for_symbol.keys()))
            
            logger.info(f"No data found for {symbol} at {query_key}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail={
                    "message": f"No data for {symbol} at {query_key}",
                    "available_dates": available_dates[:10],  # Limit to avoid excessive response size
                    "available_hours": available_hours
                }
            )
            
        return {"symbol": symbol, "timestamp": query_key, "data": result}

    except ValueError as ve:
        logger.warning(f"Validation error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(ve)
        )
    except HTTPException:
        # Re-raise HTTPExceptions (already properly formatted)
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching stock data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal server error"
        )