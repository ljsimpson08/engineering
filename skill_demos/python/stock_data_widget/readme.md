# Alpha Vantage API Test Script

**Filename:** `test_alpha_vantage.py`  
**Description:**  
A simple script to test the Alpha Vantage stock data API. It queries multiple stock tickers for intraday data (default: 5-minute intervals) and displays the first few rows using **pandas**.

## Features

- **Alpha Vantage Connection:** Uses the official `alpha_vantage` Python library.
- **Fetch Intraday Stock Data:** Retrieves data at chosen intervals (5-minute by default).
- **Pandas Integration:** Returns data as a DataFrame and prints the first few rows.
- **Quick Preview:** Validates the API key setup and data structure before building a more sophisticated application.

## Requirements

- Python 3.x
- `alpha_vantage` library
- `pandas` library

## Installation

```bash
pip install alpha_vantage pandas
Usage
Replace API_KEY in the script with your Alpha Vantage API key.

Update the symbols list to whichever stock tickers you want.

Run the script:

bash
Copy
Edit
python test_alpha_vantage.py
Check the output for a brief DataFrame preview of each symbol’s intraday data.

Copy
Edit
