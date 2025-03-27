# fang_service/routers/info.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/info")
def get_info():
    """
    Provides usage instructions for the /getStock endpoint.
    """
    usage_instructions = {
        "description": "Fetch FANG stock data for a given date/hour within the past 72 hours.",
        "endpoint": "/getStock",
        "method": "GET",
        "query_params": {
            "symbol": "FANG company symbol (e.g., FB, AMZN, NFLX, GOOG)",
            "date": "YYYY-MM-DD (within the last 72 hours)",
            "hour": "0-23 (within the last 72 hours)"
        },
        "api_key_requirement": "Must include 'x-api-key' header with valid SERVICE_API_KEY"
    }
    return usage_instructions
