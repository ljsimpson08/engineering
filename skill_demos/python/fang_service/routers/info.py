# fang_service/routers/info.py

from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import platform
import sys

from fang_service.app_variables import FANG_SYMBOLS, MAX_CACHE_AGE_HOURS
from fang_service import __version__  # Import from main package
from fang_service.core.db_service import StockDataService

router = APIRouter()

# Pydantic models for response validation and documentation
class QueryParam(BaseModel):
    """Documentation for a query parameter"""
    name: str = Field(..., description="Parameter name")
    description: str = Field(..., description="Parameter description")
    type: str = Field(..., description="Parameter data type")
    required: bool = Field(..., description="Whether the parameter is required")
    example: str = Field(..., description="Example parameter value")

class EndpointInfo(BaseModel):
    """Documentation for an API endpoint"""
    endpoint: str = Field(..., description="API endpoint path")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    description: str = Field(..., description="Endpoint description")
    query_params: List[QueryParam] = Field([], description="Query parameters")
    auth_required: bool = Field(..., description="Whether authentication is required")
    rate_limited: bool = Field(..., description="Whether the endpoint is rate-limited")

class APIInfo(BaseModel):
    """API information and documentation"""
    name: str = Field(..., description="API name")
    version: str = Field(..., description="API version")
    description: str = Field(..., description="API description")
    base_url: str = Field(..., description="Base URL for API endpoints")
    endpoints: List[EndpointInfo] = Field(..., description="Available endpoints")
    auth_instructions: str = Field(..., description="Authentication instructions")
    data_window_hours: int = Field(..., description="Hours of data kept in database")
    symbols_tracked: List[str] = Field(..., description="Stock symbols being tracked")
    generated_at: str = Field(..., description="Timestamp when this info was generated")

@router.get(
    "/info", 
    response_model=APIInfo,
    summary="Get API documentation",
    response_description="Information about API usage and endpoints"
)
def get_info(stock_service: StockDataService = Depends()) -> Dict[str, Any]:
    """
    Provides comprehensive documentation for the FANG Stock Data API.
    
    Returns detailed information about available endpoints, parameters,
    authentication requirements, and data availability.
    
    Returns:
        Dictionary with API documentation
    """
    # Get timestamp for documentation generation
    generated_at = datetime.utcnow().isoformat() + "Z"
    
    # Get available symbols from database for more helpful documentation
    available_symbols = stock_service.get_symbols_with_data()
    
    # Calculate the data availability window
    data_start = datetime.utcnow() - timedelta(hours=MAX_CACHE_AGE_HOURS)
    data_start_str = data_start.strftime("%Y-%m-%d")
    data_end_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Comprehensive API documentation
    api_info = {
        "name": "FANG Stock Data API",
        "version": __version__,
        "description": "API for retrieving intraday stock data for FANG companies (Facebook/Meta, Amazon, Netflix, Google)",
        "base_url": "/api",
        "endpoints": [
            {
                "endpoint": "/getStock",
                "method": "GET",
                "description": "Fetch stock data for a specific symbol, date, and hour",
                "query_params": [
                    {
                        "name": "symbol",
                        "description": f"FANG company symbol (available: {', '.join(available_symbols) if available_symbols else FANG_SYMBOLS})",
                        "type": "string",
                        "required": True,
                        "example": "AMZN"
                    },
                    {
                        "name": "date",
                        "description": f"Date in YYYY-MM-DD format (within {data_start_str} to {data_end_str})",
                        "type": "string",
                        "required": True,
                        "example": datetime.utcnow().strftime("%Y-%m-%d")
                    },
                    {
                        "name": "hour",
                        "description": "Hour of the day (0-23)",
                        "type": "integer",
                        "required": True,
                        "example": "10"
                    }
                ],
                "auth_required": True,
                "rate_limited": True
            },
            {
                "endpoint": "/allData",
                "method": "GET",
                "description": "Fetch all available stock data for all FANG symbols",
                "query_params": [],
                "auth_required": True,
                "rate_limited": True
            },
            {
                "endpoint": "/symbolData/{symbol}",
                "method": "GET",
                "description": "Fetch all available stock data for a specific symbol",
                "query_params": [
                    {
                        "name": "symbol",
                        "description": f"FANG company symbol (available: {', '.join(available_symbols) if available_symbols else FANG_SYMBOLS})",
                        "type": "string",
                        "required": True,
                        "example": "NFLX"
                    }
                ],
                "auth_required": True,
                "rate_limited": True
            },
            {
                "endpoint": "/availableSymbols",
                "method": "GET",
                "description": "Get a list of symbols with available data",
                "query_params": [],
                "auth_required": True,
                "rate_limited": False
            },
            {
                "endpoint": "/health",
                "method": "GET",
                "description": "Get detailed service health information",
                "query_params": [],
                "auth_required": False,
                "rate_limited": False
            },
            {
                "endpoint": "/ping",
                "method": "GET",
                "description": "Simple connectivity test",
                "query_params": [],
                "auth_required": False,
                "rate_limited": False
            },
            {
                "endpoint": "/ready",
                "method": "GET",
                "description": "Check if service is ready to handle requests",
                "query_params": [],
                "auth_required": False,
                "rate_limited": False
            },
            {
                "endpoint": "/status",
                "method": "GET",
                "description": "Get detailed information about the data status",
                "query_params": [],
                "auth_required": False,
                "rate_limited": False
            }
        ],
        "auth_instructions": "Include 'x-api-key' header with your SERVICE_API_KEY",
        "data_window_hours": MAX_CACHE_AGE_HOURS,
        "symbols_tracked": FANG_SYMBOLS,
        "generated_at": generated_at
    }
    
    return api_info

@router.get(
    "/system",
    summary="Get service system information",
    response_description="System and environment information"
)
def get_system_info() -> Dict[str, Any]:
    """
    Provides system and environment information about the service.
    
    This endpoint returns technical details about the service's runtime
    environment, which can be useful for debugging and support.
    
    Returns:
        Dictionary with system information
    """
    # Environment information
    python_version = sys.version
    python_implementation = platform.python_implementation()
    
    # System information
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor() or "Unknown",
        "architecture": platform.architecture()[0],
        "hostname": platform.node(),
        "python": {
            "version": python_version,
            "implementation": python_implementation,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro
            }
        },
        "service": {
            "version": __version__,
            "symbols_tracked": FANG_SYMBOLS,
            "data_window_hours": MAX_CACHE_AGE_HOURS
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    return system_info