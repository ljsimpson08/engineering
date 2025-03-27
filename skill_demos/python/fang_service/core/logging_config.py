# fang_service/core/logging_config.py

import json
import logging
import traceback
from datetime import datetime
import uuid

# Create a custom JSON logger
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            # Generate or attach a unique ID (UID) – for demonstration, we create a new one per log
            "uid": str(uuid.uuid4()),
            "trace_id": getattr(record, "dd.trace_id", None),  # If Datadog trace ID is available
            "error_type": None,
            "error_message": None,
            "stack_trace": None,
            "message": record.getMessage(),
        }

        # If it’s an exception, populate error info
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            log_record["error_type"] = str(exc_type)
            log_record["error_message"] = str(exc_value)
            log_record["stack_trace"] = "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )

        return json.dumps(log_record)

def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Avoid adding multiple handlers if logger is already configured
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
