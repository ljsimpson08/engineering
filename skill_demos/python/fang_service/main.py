# fang_service/main.py

import os
import time
import signal
import atexit
import uvicorn
from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
try:
    from ddtrace import patch_all, tracer
    from ddtrace.contrib.fastapi import TraceMiddleware
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False
import logging
from contextlib import asynccontextmanager
import uuid
import platform

from fang_service.app_variables import (
    DATADOG_ENABLED, DATADOG_SERVICE_NAME, DATADOG_ENV, DATADOG_VERSION,
    RUN_TYPE, FANG_SYMBOLS, RATE_LIMIT_PER_MINUTE
)
from fang_service.core.logging_config import get_logger
from fang_service.core.db_service import StockDataService
from fang_service import __version__

# Import routers
from fang_service.routers import info, get_stock, health, alldata

# Configure logging
logger = get_logger(__name__)
 
# === Datadog APM Setup ===
if DATADOG_ENABLED:
    if DATADOG_AVAILABLE:
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
            DATADOG_ENABLED = False
    else:
        logger.warning("Datadog APM requested but ddtrace package not installed")
        DATADOG_ENABLED = False

# Global instance for dependency injection
stock_service = StockDataService()

# Setup graceful shutdown
def shutdown_handler():
    """
    Handle graceful shutdown of resources.
    
    Ensures background tasks and connections are properly closed.
    Called during normal shutdown or when signaled externally.
    """
    logger.info("Shutting down service gracefully...")
    
    try:
        # Stop the background updater thread
        stock_service.stop_background_updater()
        logger.info("Background updater stopped")
    except Exception as e:
        logger.error(f"Error stopping background updater: {e}", exc_info=True)
    
    logger.info("Service shutdown complete")

# Register shutdown handler
atexit.register(shutdown_handler)

# Handle OS signals for graceful shutdown in containerized environments
def signal_handler(sig, frame):
    """
    Handle OS signals like SIGTERM and SIGINT.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
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
    """
    Manage the lifespan of the application.
    
    Handles initialization during startup and cleanup during shutdown.
    
    Args:
        app: The FastAPI application instance
    """
    # Startup: Generate a unique instance ID for this service instance
    instance_id = str(uuid.uuid4())
    app.state.instance_id = instance_id
    hostname = platform.node()
    
    # Log startup with instance identification
    logger.info(f"Starting FANG Stock Data Service v{__version__} on {hostname} [instance:{instance_id}]")
    
    # 1) Fetch data immediately upon service starting
    cache_initialized = False
    try:
        update_success = stock_service.update_cache()
        cache_initialized = update_success
        if not update_success:
            logger.warning("Initial cache update was partial or unsuccessful")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
    
    # 2) Start background cache updater in persistent mode
    if RUN_TYPE == "persistent":
        try:
            stock_service.start_background_updater()
        except Exception as e:
            logger.error(f"Failed to start background updater: {e}", exc_info=True)
    
    logger.info(f"Startup process complete - Service ready [instance:{instance_id}]")
    yield
    
    # Shutdown: Clean up resources
    logger.info(f"FastAPI shutdown event triggered [instance:{instance_id}]")
    shutdown_handler()

# Create and configure the FastAPI app
app = FastAPI(
    title="FANG Stock Data Service",
    description="API for retrieving FANG stock data",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",  # Swagger UI path
    redoc_url="/api/redoc",  # ReDoc path
    openapi_url="/api/openapi.json"  # OpenAPI schema path
)

# === Middleware Configuration ===

# Add the Datadog tracing middleware if enabled
if DATADOG_ENABLED and DATADOG_AVAILABLE:
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
    """
    Basic rate limiting middleware (per-instance, not distributed).
    
    Limits requests per minute based on RATE_LIMIT_PER_MINUTE.
    Note: This is a simplified implementation for a single instance.
    
    Args:
        request: The incoming request
        call_next: The next middleware or route handler
        
    Returns:
        The response from the next handler
    """
    # This is a simplified implementation; use Redis or similar for distributed rate limiting
    # Real production code would use proper token bucket or leaky bucket algorithms
    
    client_ip = request.client.host if request.client else "unknown"
    current_minute = int(time.time() / 60)
    
    # Simple in-memory tracking (not suitable for production/multi-instance)
    if not hasattr(app.state, "rate_limit_counters"):
        app.state.rate_limit_counters = {}
    
    # Reset counters for a new minute
    if not hasattr(app.state, "rate_limit_last_minute"):
        app.state.rate_limit_last_minute = current_minute
    elif current_minute > app.state.rate_limit_last_minute:
        app.state.rate_limit_counters = {}
        app.state.rate_limit_last_minute = current_minute
    
    # Check and increment counter for this IP
    if client_ip in app.state.rate_limit_counters:
        if app.state.rate_limit_counters[client_ip] >= RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                content={"error": "Rate limit exceeded", "retry_after": "60 seconds"},
                status_code=429,
                headers={"Retry-After": "60"}
            )
        app.state.rate_limit_counters[client_ip] += 1
    else:
        app.state.rate_limit_counters[client_ip] = 1
    
    # Continue with the request
    return await call_next(request)

# === Request logging middleware ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log each request with timing information.
    
    Args:
        request: The incoming request
        call_next: The next middleware or route handler
        
    Returns:
        The response from the next handler
    """
    # Generate a unique request ID
    request_id = str(uuid.uuid4())
    
    # Create a logger with request context
    req_logger = get_logger(
        __name__, 
        {"request_id": request_id, "client_ip": request.client.host if request.client else "unknown"}
    )
    
    # Start timing
    start_time = time.time()
    
    # Basic request info
    path = request.url.path
    query = request.url.query
    method = request.method
    
    # Log request start (debug level to keep normal logs cleaner)
    req_logger.debug(
        f"Request started: {method} {path}"
        + (f"?{query}" if query else "")
    )
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # Add request ID to response headers for troubleshooting
        response.headers["X-Request-ID"] = request_id
        
        # Log successful requests
        req_logger.info(
            f"Request: {method} {path} "
            f"| Status: {response.status_code} "
            f"| Time: {process_time:.2f}ms"
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        req_logger.error(
            f"Request failed: {method} {path} "
            f"| Error: {str(e)} "
            f"| Time: {process_time:.2f}ms", 
            exc_info=True
        )
        raise

# === Dependency Providers ===

# Provide the StockDataService instance as a dependency
def get_stock_service():
    """
    Provide the shared StockDataService instance.
    
    Returns:
        The global StockDataService instance
    """
    return stock_service

# Register the dependency
app.dependency_overrides[StockDataService] = get_stock_service

# === Register Routers ===
api_prefix = "/api"  # Adding API prefix for cleaner URLs

app.include_router(info.router, prefix=api_prefix, tags=["Information"])
app.include_router(get_stock.router, prefix=api_prefix, tags=["Stock Data"])
app.include_router(health.router, prefix=api_prefix, tags=["Health"])
app.include_router(alldata.router, prefix=api_prefix, tags=["All Data"])

# === Main entry to run via "python -m fang_service.main" or "python main.py" ===
if __name__ == "__main__":
    # For local dev or container-based runs
    try:
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "8000"))
        reload_enabled = os.environ.get("RELOAD", "true").lower() == "true"
        
        logger.info(f"Starting Uvicorn server on {host}:{port} (reload={reload_enabled})")
        uvicorn.run(
            "fang_service.main:app", 
            host=host, 
            port=port, 
            reload=reload_enabled,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        shutdown_handler()