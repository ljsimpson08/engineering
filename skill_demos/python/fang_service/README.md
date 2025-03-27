# FANG Stock Data Service

A high-performance microservice for accessing FANG (Facebook/Meta, Amazon, Netflix, Google) stock data with a RESTful API.

## Overview

This service fetches intraday stock data from Alpha Vantage for FANG companies, caches it in memory, and exposes an API endpoint to retrieve specific data points. The service is designed for high throughput and low latency, making it suitable for dashboard applications, financial analysis tools, and trading applications.

## Features

- **Real-time Stock Data**: Fetches intraday stock data from Alpha Vantage
- **In-memory Caching**: Maintains a rolling 72-hour window of stock data in memory
- **Automatic Updates**: Background thread refreshes data at configurable intervals
- **Secure API**: API key authentication for secure access
- **Comprehensive Logging**: Structured JSON logging with trace ID support
- **APM Integration**: Built-in Datadog APM support for production monitoring
- **FastAPI Backend**: High-performance async API built on FastAPI and Uvicorn

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. Clone the repository:
   ```bash
   git clone https://your-repo-url/fang_service.git
   cd fang_service
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure API keys:
   - Obtain an API key from [Alpha Vantage](https://www.alphavantage.co/support/#api-key)
   - Update `app_variables.py` with your Alpha Vantage API key and service API key
     (For production, use environment variables instead of hardcoded values)

## Configuration

Configuration is managed through `app_variables.py`:

- `ALPHAVANTAGE_API_KEY`: Your Alpha Vantage API key
- `SERVICE_API_KEY`: API key for authenticating clients to this service
- `DATADOG_ENABLED`: Toggle Datadog APM integration
- `DATADOG_SERVICE_NAME`, `DATADOG_ENV`, `DATADOG_VERSION`: Datadog configuration
- `PLATFORM`: Platform type for stats collection
- `RUN_TYPE`: "persistent" (runs continuously) or "single-run" (fetch once and exit)
- `FANG_SYMBOLS`: List of stock symbols to track
- `FETCH_INTERVAL_HOURS`: How often to refresh data from Alpha Vantage

## Usage

### Running the Service

```bash
# Development mode
python -m fang_service.main

# Production mode (using Gunicorn)
gunicorn fang_service.main:app -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8000
```

### API Endpoints

#### GET /info
Returns information about the API usage.

#### GET /getStock
Retrieves stock data for a specific symbol, date, and hour.

**Parameters:**
- `symbol`: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
- `date`: Date in YYYY-MM-DD format
- `hour`: Hour of the day (0-23)

**Headers:**
- `x-api-key`: Your service API key

**Example Request:**
```bash
curl -X GET "http://localhost:8000/getStock?symbol=AMZN&date=2023-03-24&hour=10" \
  -H "x-api-key: your-service-api-key"
```

**Example Response:**
```json
{
  "symbol": "AMZN",
  "timestamp": "2023-03-24 10:00:00",
  "data": {
    "1. open": "98.4500",
    "2. high": "98.8700",
    "3. low": "98.3600", 
    "4. close": "98.7100",
    "5. volume": "2358035"
  }
}
```

## Development

### Project Structure

```
fang_service/
├── __init__.py
├── app_variables.py
├── main.py
├── core/
│   ├── __init__.py
│   ├── data_fetcher.py
│   ├── logging_config.py
│   ├── random_tests.py
│   └── stocks_cache.py
├── routers/
│   ├── __init__.py
│   ├── get_stock.py
│   └── info.py
└── tests/
    └── test_service.py
```

### Running Tests

```bash
pytest fang_service/tests/
```

## Security Considerations

- In production, API keys should be stored in environment variables or a secrets manager
- Consider implementing rate limiting for API endpoints
- Review and update dependencies regularly for security patches

## Monitoring

The service integrates with Datadog APM for production monitoring:

- Performance metrics for API endpoints
- Trace sampling for request profiling
- Distributed tracing for microservice architecture
- Custom logs with trace correlation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributors

- Your Name <your.email@example.com>