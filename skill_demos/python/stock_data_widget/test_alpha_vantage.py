# test_alpha_vantage.py

# 1. Install alpha_vantage if you haven't already:
#    pip install alpha_vantage

from alpha_vantage.timeseries import TimeSeries
import pandas as pd

# Replace this string with your actual Alpha Vantage API key
API_KEY = "XXXXXXXXXXXXXXX"

# Initialize the TimeSeries object
ts = TimeSeries(key=API_KEY, output_format='pandas')

# Define the symbols you want to fetch: 
#   FANG + MSFT + TSLA
symbols = ["META", "AMZN", "NFLX", "GOOGL", "MSFT", "TSLA"]

# Loop through each symbol, download intraday data, and display the first few rows
for symbol in symbols:
    print(f"Fetching data for {symbol}...")

    # Get intraday data (5-minute interval). You could also use '1min', '15min', '30min', etc.
    data, meta_data = ts.get_intraday(symbol=symbol, interval='5min', outputsize='compact')

    # Just show the first few rows as a test
    print(data.head())
    print("-" * 60)

# NOTE: 
# - 'outputsize="compact"' returns ~100 data points. If you need more, use 'full'.
# - Watch out for API rate limits on the free tier 
#   (currently 5 calls/minute, 500 calls/day).
# - Data will update more frequently during U.S. market hours (9:30 AM–4:00 PM ET).
