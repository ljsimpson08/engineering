# Payment Tester

**Filename:** `test_rails_payment.py`  
**Description:**  
A script to test payment APIs you’ve created (particularly a Ruby on Rails–based tokenization endpoint). It runs various scenarios—valid/invalid cards, missing auth, rate limits, etc.—and prints pass/fail results to the console.

## Features

- **Auth Verification:** Checks Basic Auth (missing/invalid credentials → `401`).
- **Card Validation:** Tests valid and invalid card numbers, expecting success or error responses.
- **Parameter Validation:** Checks how the API handles missing or malformed parameters.
- **Rate Limiting Checks:** Sends multiple rapid requests to see if a `429 Too Many Requests` is triggered.
- **Health Endpoint Test:** Verifies the `/health` endpoint returns “ok”.

## Requirements

- Python 3.x
- `requests` library

```bash
    pip install requests
    Installation
    Ensure Python 3 is installed.
    Install dependencies (requests).
    Set environment variables if desired:
    bash
    Copy
    Edit
    export RAILS_APP_URL="http://localhost:3000"
    export DEVELOPMENT_USERNAME="X"
    export DEVELOPMENT_PASSWORD="development"
    Usage
    Make sure your Rails payment API is running at RAILS_APP_URL.

    Run the script:

    bash
    Copy
    Edit
    python test_rails_payment.py
    Review the console output for pass/fail results.

    Notes
    You can add or modify tests inside the script to cover more scenarios (3D Secure flows, partial refunds, etc.).
    Results use ANSI escape codes for color if your terminal supports them.