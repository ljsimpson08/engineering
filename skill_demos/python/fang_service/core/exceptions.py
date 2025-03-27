# fang_service/core/exceptions.py

from typing import Optional, Dict, Any

class APIError(Exception):
    """Base class for API related errors."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

class RateLimitError(APIError):
    """Error raised when API rate limit is exceeded."""
    
    def __init__(self, message: str = "API rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        # Use 200 status code as requested, but include warning
        super().__init__(message, 200, details)
        self.is_warning = True

class NetworkError(APIError):
    """Error raised when network issues occur."""
    
    def __init__(self, message: str = "Network error occurred", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 503, details)

class AuthenticationError(APIError):
    """Error raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 401, details)

class DataRetrievalError(APIError):
    """Error raised when data cannot be retrieved."""
    
    def __init__(self, message: str = "Failed to retrieve data", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 500, details)

class DataNotFoundError(APIError):
    """Error raised when requested data is not found."""
    
    def __init__(self, message: str = "Data not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, 404, details)