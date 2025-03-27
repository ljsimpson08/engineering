# fang_service/routers/health.py

import time
import datetime
import platform
import psutil
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
import os

from fang_service.core.stocks_cache import StocksCache
from fang_service.core.logging_config import get_logger
from fang_service.app_variables import (
    DATADOG_ENABLED, DATADOG_ENV, FANG_SYMBOLS,
    RUN_TYPE, FETCH_INTERVAL_HOURS
)

logger = get_logger(__name__)
router = APIRouter()

# Track service start time for uptime calculation
SERVICE_START_TIME = time.time()

@router.get("/health")
async def health_check(stocks_cache: StocksCache = Depends()):
    """
    Comprehensive health check endpoint for monitoring service status.
    
    Returns:
        Dict with health status information
    """
    # Get cache statistics
    cache_stats = stocks_cache.get_cache_stats()
    
    # Determine overall health status
    is_healthy = True
    status_reasons = []
    
    # Check if we have data for all symbols
    missing_symbols = [symbol for symbol in FANG_SYMBOLS if symbol not in cache_stats["symbols_cached"]]
    if missing_symbols:
        is_healthy = False
        status_reasons.append(f"Missing data for symbols: {', '.join(missing_symbols)}")
    
    # Check cache age (if too old, service might be having issues)
    cache_max_age_sec = FETCH_INTERVAL_HOURS * 3600 * 1.5  # 1.5x the fetch interval
    if cache_stats["cache_age_seconds"] and cache_stats["cache_age_seconds"] > cache_max_age_sec:
        is_healthy = False
        status_reasons.append(
            f"Cache is stale: {cache_stats['cache_age_seconds']//60} minutes old "
            f"(max allowed: {cache_max_age_sec//60} minutes)"
        )
    
    # Check for multiple failed updates
    if cache_stats["failed_updates"] > 3:
        is_healthy = False
        status_reasons.append(f"Multiple failed cache updates: {cache_stats['failed_updates']}")
    
    # Get system metrics
    system_metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "process_memory_mb": psutil.Process().memory_info().rss / (1024 * 1024)
    }
    
    # Service uptime calculation
    uptime_seconds = time.time() - SERVICE_START_TIME
    uptime = {
        "seconds": int(uptime_seconds),
        "minutes": int(uptime_seconds / 60),
        "hours": int(uptime_seconds / 3600),
        "days": int(uptime_seconds / 86400)
    }
    
    # Compile health response
    health_data = {
        "status": "healthy" if is_healthy else "unhealthy",
        "status_reasons": status_reasons if status_reasons else ["All checks passed"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "uptime": uptime,
        "version": __version__,
        "environment": DATADOG_ENV,
        "run_type": RUN_TYPE,
        "monitoring_enabled": DATADOG_ENABLED,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "symbols_tracked": FANG_SYMBOLS,
        "cache": cache_stats,
        "system": system_metrics
    }
    
    # Log health check if unhealthy
    if not is_healthy:
        logger.warning(f"Health check failed: {status_reasons}")
    
    # If critically unhealthy, could also return a non-200 status
    # if not is_healthy and critical_thresholds_breached:
    #     raise HTTPException(
    #         status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    #         detail={"status": "critical", "reasons": status_reasons}
    #     )
    
    return health_data


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    Returns 200 OK with minimal overhead.
    """
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}