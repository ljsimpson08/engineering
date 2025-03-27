# fang_service/core/logging_config.py

import json
import logging
import traceback
import platform
import sys
import os
from datetime import datetime
import uuid
from typing import Dict, Any, Optional

# Constants for logging format
LOG_LEVEL_ENV = "LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT_ENV = "LOG_FORMAT"
DEFAULT_LOG_FORMAT = "json"  # Options: "json", "text"

# Create a custom JSON logger for structured logging
class JsonFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    This formatter outputs logs as JSON objects with consistent fields,
    making them easier to parse and analyze in log aggregation systems.
    It also adds contextual information like trace IDs and error details.
    """
    def format(self, record) -> str:
        """
        Format the log record as a JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        # Get the hostname for better identification in distributed environments
        hostname = platform.node()
        
        # Create a unique UID for this log entry
        log_uid = str(uuid.uuid4())
        
        # Construct the base log record
        log_record = {
            "time": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "uid": log_uid,
            "hostname": hostname,
            "pid": os.getpid(),
            # Include Datadog trace ID if available for distributed tracing
            "trace_id": getattr(record, "dd.trace_id", None),
            "error_type": None,
            "error_message": None,
            "stack_trace": None,
            "message": record.getMessage(),
        }

        # If it's an exception, populate error info
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            log_record["error_type"] = exc_type.__name__ if exc_type else None
            log_record["error_message"] = str(exc_value)
            log_record["stack_trace"] = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )

        # Add any custom attributes attached to the record
        for key, value in getattr(record, "extra_data", {}).items():
            if key not in log_record:  # Avoid overwriting standard fields
                log_record[key] = value

        # Format as JSON with consistent field ordering
        return json.dumps(log_record, sort_keys=True)

# Text formatter for human-readable logs (useful for development)
class TextFormatter(logging.Formatter):
    """Text formatter for human-readable logs."""
    
    def __init__(self, include_pid: bool = True):
        """
        Initialize the text formatter.
        
        Args:
            include_pid: Whether to include the process ID in the log format
        """
        self.include_pid = include_pid
        fmt = "%(asctime)s [%(levelname)s] "
        
        if include_pid:
            fmt += "[PID:%(process)d] "
            
        fmt += "%(name)s: %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    
    def format(self, record) -> str:
        """
        Format the log record as text.
        
        Args:
            record: The log record to format
            
        Returns:
            Text-formatted log string
        """
        formatted = super().format(record)
        
        # Add exception info if present
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            formatted += f"\nEXCEPTION: {exc_type.__name__}: {exc_value}"
            formatted += "\n" + "".join(traceback.format_exception(
                exc_type, exc_value, exc_traceback))
            
        return formatted

def get_logger(name: str = __name__, extra_data: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get a configured logger with appropriate formatter.
    
    This function returns a logger configured based on environment settings.
    It will use JSON formatting by default (for production) but can be
    configured to use text formatting (for development) via the LOG_FORMAT_ENV.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        extra_data: Additional data to attach to all log records
        
    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        # Determine log level from environment or use default
        log_level_name = os.environ.get(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL).upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        
        # Determine log format from environment or use default
        log_format = os.environ.get(LOG_FORMAT_ENV, DEFAULT_LOG_FORMAT).lower()
        
        handler = logging.StreamHandler(sys.stdout)
        
        # Select formatter based on configured format
        if log_format == "text":
            handler.setFormatter(TextFormatter())
        else:
            # Default to JSON formatter
            handler.setFormatter(JsonFormatter())
            
        logger.addHandler(handler)
        logger.setLevel(log_level)
        
        # Log startup info at debug level
        logger.debug(
            f"Logger '{name}' initialized with level={log_level_name}, format={log_format}"
        )
    
    # Return an adapter that adds extra data if provided
    if extra_data:
        return LoggerAdapter(logger, extra_data)
    
    return logger

class LoggerAdapter(logging.LoggerAdapter):
    """
    Adapter that adds extra contextual data to all log records.
    
    This allows attaching context (like request ID, user ID, etc.)
    to all log messages from a particular logger instance.
    """
    
    def process(self, msg, kwargs):
        """Process the log message to add extra data."""
        # Ensure extra_data exists in kwargs
        kwargs.setdefault("extra", {}).setdefault("extra_data", {})
        
        # Add our additional context to extra_data
        kwargs["extra"]["extra_data"].update(self.extra)
        
        return msg, kwargs