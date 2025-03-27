# fang_service/main.py

import os
import time
import signal
import atexit
import uvicorn
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from ddtrace import patch_all, tracer
#from ddtrace.contrib.fastapi import TraceMiddleware
import logging
from contextlib import asynccontextmanager

from fang_service.app_variables import (
    DATADOG_ENABLED, DATADOG_SERVICE_NAME, DATADOG_ENV, DATADOG_VERSION,
    RUN_TYPE, FANG_SYMBOLS, RATE_LIMIT_PER_MINUTE
)
from fang_service.core.logging_config import get_logger
from fang_service.core.stocks_cache import StocksCache
from fang_service.core.random_tests import run_random_tests
from fang_service import __version__

# Import routers
from fang_service.routers import info, get_stock, health

# Configure logging
logger = get_logger(__name__)
 
# === Datadog APM Setup ===
if DATADOG_ENABLED:
    try:
        # Patch all supported libraries
        patch_all()
        # Some environment variables needed for ddtrace (if not already set)
        os.environ["DD_SERVICE"] = DATADOG_SERVICE_NAME
        os.environ["DD_ENV"] = DATADOG_ENV
        os.environ["DD_VERSION"] = DATADOG_VERSION
        logger.info("Datadog APM initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Datadog APM: {e}", exc_info=True)

# Global instance for dependency injection
stocks_cache = StocksCache()

# Setup graceful shutdown
def shutdown_handler():
    """Handle graceful shutdown of resources"""
    logger.info("Shutting down service gracefully...")
    
    try:
        # Stop the background updater thread
        stocks_cache.stop_background_updater()
        logger.info("Background updater stopped")
    except Exception as e:
        logger.error(f"Error stopping background updater: {e}", exc_info=True)
    
    logger.info("Service shutdown complete")

# Register shutdown handler
atexit.register(shutdown_handler)

# Handle OS signals for graceful shutdown in containerized environments
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    shutdown_handler()
    # Give time for logs to flush
    time.sleep(1)
    os._exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# FastAPI startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application"""
    # Startup: Initialize services
    logger.info(f"Starting FANG Stock Data Service v{__version__}")
    
    # 1) Fetch data immediately upon service starting
    try:
        stocks_cache.update_cache()
    except Exception as e:
        logger.error(f"Failed to initialize cache: {e}", exc_info=True)
    
    # 2) Run random tests if data is available
    try:
        run_random_tests(stocks_cache)
    except Exception as e:
        logger.error(f"Error in random tests: {e}", exc_info=True)
    
    # 3) Start background cache updater in persistent mode
    if RUN_TYPE == "persistent":
        try:
            stocks_cache.start_background_updater()
        except Exception as e:
            logger.error(f"Failed to start background updater: {e}", exc_info=True)
    
    logger.info("Startup process complete")
    yield
    
    # Shutdown: Clean up resources
    logger.info("FastAPI shutdown event triggered")
    shutdown_handler()

# Create and configure the FastAPI app
app = FastAPI(
    title="FANG Stock Data Service",
    description="API for retrieving FANG stock data",
    version=__version__,
    lifespan=lifespan
)

# === Middleware Configuration ===

# Add the Datadog tracing middleware if enabled
if DATADOG_ENABLED:
    app.add_middleware(TraceMiddleware, service=DATADOG_SERVICE_NAME)

# Add CORS middleware to allow cross-origin requests (for dashboard integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict for production
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Simple rate limiting middleware (replace with more robust solution for production)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Basic rate limiting middleware (per-instance, not distributed)"""
    # This is a simplified implementation; use Redis or similar for distributed rate limiting
    # Real production code would use proper token bucket or leaky bucket algorithms
    
    client_ip = request.client.host
    current_minute = int(time.time() / 60)
    
    # Simple in-memory tracking (not suitable for production/multi-instance)
    if not hasattr(app, "rate_limit_counters"):
        app.rate_limit_counters = {}
    
    # Reset counters for a new minute
    if not hasattr(app, "rate_limit_last_minute"):
        app.rate_limit_last_minute = current_minute
    elif current_minute > app.rate_limit_last_minute:
        app.rate_limit_counters = {}
        app.rate_limit_last_minute = current_minute
    
    # Check and increment counter for this IP
    if client_ip in app.rate_limit_counters:
        if app.rate_limit_counters[client_ip] >= RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response(
                content='{"error": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json"
            )
        app.rate_limit_counters[client_ip] += 1
    else:
        app.rate_limit_counters[client_ip] = 1
    
    # Continue with the request
    return await call_next(request)

# === Request logging middleware ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log each request with timing information"""
    start_time = time.time()
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # Log successful requests
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"| Status: {response.status_code} "
            f"| Time: {process_time:.2f}ms"
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {request.method} {request.url.path} "
            f"| Error: {str(e)} "
            f"| Time: {process_time:.2f}ms", 
            exc_info=True
        )
        raise

# === Dependency Providers ===

# Provide the StocksCache instance as a dependency
def get_stocks_cache():
    """Provide the shared StocksCache instance"""
    return stocks_cache

# Register the dependency
app.dependency_overrides[StocksCache] = get_stocks_cache

# === Register Routers ===
app.include_router(info.router, tags=["Information"])
app.include_router(get_stock.router, tags=["Stock Data"])
app.include_router(health.router, tags=["Health"])

# === Main entry to run via "python -m fang_service.main" or "python main.py" ===
if __name__ == "__main__":
    # For local dev or container-based runs
    try:
        uvicorn.run("fang_service.main:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        shutdown_handler()