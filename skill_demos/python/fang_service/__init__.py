# fang_service/__init__.py

"""
FANG Stock Data Service

A high-performance microservice providing intraday stock data for FANG companies
(Facebook/Meta, Amazon, Netflix, Google) via a REST API.

This service fetches data from Alpha Vantage, caches it in memory, and exposes
endpoints for retrieving specific data points or all available data.
"""

__version__ = "0.1.0"
__author__ = "FANG Service Team"
__license__ = "MIT"

# Export version for easy access
VERSION = __version__

# Package metadata
PACKAGE_NAME = "fang_service"
DESCRIPTION = "FANG Stock Data Service"