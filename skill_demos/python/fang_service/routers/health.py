# fang_service/routers/health.py

import time
import datetime
import platform
import psutil
from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import os
import sys
import socket

from fang_service.core.db_service import StockDataService
from fang_service.core.logging_config import get_logger
from fang_service.app_variables import (
    DATADOG_ENABLED, DATADOG_ENV, FANG_SYMBOLS,
    RUN_TYPE, FETCH_INTERVAL_HOURS
)
# Import __version__ from the main package instead of app_variables
from fang_service import __version__

logger = get_logger(__name__)
router = APIRouter()

# Track service start time for uptime calculation
SERVICE_START_TIME = time.time()

# Health check models for better documentation and type checking
class UptimeInfo(BaseModel):
    """System uptime information"""
    seconds: int = Field(..., description="Total uptime in seconds")
    minutes: int = Field(..., description="Total uptime in minutes")
    hours: int = Field(..., description="Total uptime in hours")
    days: int = Field(..., description="Total uptime in days")

class SystemMetrics(BaseModel):
    """System resource utilization metrics"""
    cpu_percent: float = Field(..., description="CPU utilization percentage")
    memory_percent: float = Field(..., description="Memory utilization percentage")
    disk_percent: float = Field(..., description="Disk utilization percentage")
    process_memory_mb: float = Field(..., description="Current process memory usage in MB")

class DatabaseStats(BaseModel):
    """Database statistics"""
    update_count: int = Field(..., description="Number of database updates performed")
    failed_updates: int = Field(..., description="Number of failed database updates")
    last_update: Optional[str] = Field(None, description="ISO timestamp of last update")
    cache_hits: int = Field(..., description="Number of database query hits")
    cache_misses: int = Field(..., description="Number of database query misses")
    hit_rate_percentage: float = Field(..., description="Database hit rate percentage")
    symbols_cached: List[str] = Field(..., description="List of symbols with cached data")
    total_data_points: int = Field(..., description="Total number of data points in database")
    cache_age_seconds: Optional[float] = Field(None, description="Age of data in seconds")

class HealthResponse(BaseModel):
    """Health check response structure"""
    status: str = Field(..., description="Overall health status: healthy, degraded, or unhealthy")
    status_reasons: List[str] = Field(..., description="Reasons for current health status")
    severity: str = Field(..., description="Severity level: ok, warning, critical")
    timestamp: str = Field(..., description="ISO timestamp of health check")
    uptime: UptimeInfo = Field(..., description="Service uptime information")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Deployment environment")
    run_type: str = Field(..., description="Service run type (persistent or single-run)")
    monitoring_enabled: bool = Field(..., description="Whether monitoring is enabled")
    hostname: str = Field(..., description="Server hostname")
    platform: str = Field(..., description="Operating system platform")
    python_version: str = Field(..., description="Python version")
    symbols_tracked: List[str] = Field(..., description="Stock symbols being tracked")
    database: DatabaseStats = Field(..., description="Database statistics")
    system: SystemMetrics = Field(..., description="System resource metrics")

@router.get(
    "/health", 
    response_model=HealthResponse,
    summary="Comprehensive service health check",
    response_description="Detailed health status and metrics for the service"
)
async def health_check(response: Response, stock_service: StockDataService = Depends()) -> Dict[str, Any]:
    """
    Comprehensive health check endpoint for monitoring service status.
    
    This endpoint provides detailed information about the service's health,
    including database statistics, system resource utilization, uptime, and
    configuration. It can be used by monitoring systems to detect issues
    and by operators for troubleshooting.
    
    The health status will be one of:
    - "healthy": All checks pass
    - "degraded": Some non-critical checks are failing
    - "unhealthy": Critical checks are failing
    
    Returns:
        Dict with detailed health status information
    """
    # Get database statistics
    service_stats = stock_service.get_cache_stats()
    
    # Determine overall health status
    is_healthy = True
    is_critical = False
    status_reasons = []
    
    # Check if we have data for all symbols
    missing_symbols = [symbol for symbol in FANG_SYMBOLS if symbol not in service_stats["symbols_cached"]]
    if missing_symbols:
        is_healthy = False
        status_reasons.append(f"Missing data for symbols: {', '.join(missing_symbols)}")
    
    # Check cache age (if too old, service might be having issues)
    cache_max_age_sec = FETCH_INTERVAL_HOURS * 3600 * 1.5  # 1.5x the fetch interval
    if service_stats["cache_age_seconds"] and service_stats["cache_age_seconds"] > cache_max_age_sec:
        is_healthy = False
        status_reasons.append(
            f"Data is stale: {int(service_stats['cache_age_seconds']//60)} minutes old "
            f"(max allowed: {int(cache_max_age_sec//60)} minutes)"
        )
        
        # If cache is extremely stale (3x the interval), mark as critical
        if service_stats["cache_age_seconds"] > FETCH_INTERVAL_HOURS * 3600 * 3:
            is_critical = True
    
    # Check for multiple failed updates
    if service_stats["failed_updates"] > 3:
        is_healthy = False
        status_reasons.append(f"Multiple failed database updates: {service_stats['failed_updates']}")
        
        # If we have many failed updates, mark as critical
        if service_stats["failed_updates"] > 5:
            is_critical = True
    
    # Check system resource utilization
    system_metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "process_memory_mb": psutil.Process().memory_info().rss / (1024 * 1024)
    }
    
    # Check for resource constraints
    if system_metrics["memory_percent"] > 90:
        is_healthy = False
        status_reasons.append(f"High memory usage: {system_metrics['memory_percent']}%")
        if system_metrics["memory_percent"] > 95:
            is_critical = True
    
    if system_metrics["disk_percent"] > 90:
        is_healthy = False
        status_reasons.append(f"High disk usage: {system_metrics['disk_percent']}%")
        if system_metrics["disk_percent"] > 95:
            is_critical = True
    
    # Service uptime calculation
    uptime_seconds = time.time() - SERVICE_START_TIME
    uptime = {
        "seconds": int(uptime_seconds),
        "minutes": int(uptime_seconds / 60),
        "hours": int(uptime_seconds / 3600),
        "days": int(uptime_seconds / 86400)
    }
    
    # Get hostname for better identification in logs and monitoring
    hostname = socket.gethostname()
    
    # Determine overall status and severity
    if is_healthy:
        status = "healthy"
        severity = "ok"
        status_reasons = ["All checks passed"]
    elif is_critical:
        status = "unhealthy"
        severity = "critical"
        # Set appropriate HTTP status for critical health issues
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status = "degraded"
        severity = "warning"
    
    # Compile health response
    health_data = {
        "status": status,
        "status_reasons": status_reasons,
        "severity": severity,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "uptime": uptime,
        "version": __version__,
        "environment": DATADOG_ENV,
        "run_type": RUN_TYPE,
        "monitoring_enabled": DATADOG_ENABLED,
        "hostname": hostname,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "symbols_tracked": FANG_SYMBOLS,
        "database": service_stats,
        "system": system_metrics
    }
    
    # Log health check if not healthy
    if not is_healthy:
        log_method = logger.error if is_critical else logger.warning
        log_method(f"Health check status: {status} - {status_reasons}")
    
    return health_data


@router.get(
    "/ping", 
    summary="Simple connectivity test",
    response_description="Basic availability confirmation"
)
async def ping() -> Dict[str, Any]:
    """
    Simple ping endpoint for basic connectivity testing.
    Returns 200 OK with minimal overhead.
    
    This endpoint is useful for load balancers and basic availability monitoring.
    It performs no internal checks and responds quickly.
    
    Returns:
        Dictionary with status and timestamp
    """
    return {
        "status": "ok", 
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "service": "fang_service"
    }


@router.get(
    "/ready",
    summary="Readiness check",
    response_description="Service readiness status"
)
async def readiness_check(stock_service: StockDataService = Depends()) -> Dict[str, Any]:
    """
    Readiness check to determine if the service is ready to handle requests.
    
    This endpoint checks if the database has been populated with data.
    It's suitable for use with Kubernetes readiness probes.
    
    Returns:
        Dictionary with readiness status and details
        
    Raises:
        HTTPException 503: If the service is not ready
    """
    # Check if database has been initialized with any data
    service_stats = stock_service.get_cache_stats()
    
    if not service_stats["symbols_cached"]:
        # No symbols cached means the service isn't ready yet
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "reason": "Database not initialized with data",
                "update_count": service_stats["update_count"]
            }
        )
    
    return {
        "status": "ready",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "symbols_cached": len(service_stats["symbols_cached"]),
        "data_points": service_stats["total_data_points"]
    }