# seed_database.py

import json
import os
import sys
import datetime
import random
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from fang_service.core.db_models import init_db, insert_stock_data, get_db_stats
from fang_service.app_variables import FANG_SYMBOLS

def load_seed_data(file_path):
    """Load stock data from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_test_data(symbols, hours=72):
    """
    Generate realistic test data for the given symbols and time period.
    
    Args:
        symbols: List of stock symbols
        hours: Number of hours of data to generate (going backward from now)
        
    Returns:
        Dictionary of stock data by symbol and timestamp
    """
    now = datetime.datetime.utcnow()
    
    # Initial price points for each symbol (realistic values as of 2023)
    base_prices = {
        "FB": 300.0,    # Meta (Facebook)
        "AMZN": 130.0,  # Amazon
        "NFLX": 400.0,  # Netflix
        "GOOG": 120.0   # Google
    }
    
    # Volatility factors for each symbol (percentage)
    volatility = {
        "FB": 2.0,
        "AMZN": 1.5,
        "NFLX": 3.0,
        "GOOG": 1.8
    }
    
    # Volume base (millions)
    volume_base = {
        "FB": 15,
        "AMZN": 20,
        "NFLX": 5,
        "GOOG": 12
    }
    
    data = {}
    
    for symbol in symbols:
        symbol_data = {}
        current_price = base_prices.get(symbol, 100.0)  # Default to 100 if symbol not found
        
        for hour_offset in range(hours, 0, -1):
            # Only generate data for trading hours (9:30 AM - 4:00 PM ET, Monday-Friday)
            # This is a simplification - in reality, we'd need to account for holidays
            timestamp = now - datetime.timedelta(hours=hour_offset)
            
            # Skip non-trading hours
            hour_et = (timestamp.hour - 5) % 24  # Convert UTC to ET (simplified)
            if hour_et < 9 or hour_et >= 16:
                continue
                
            # Skip weekends (0 = Monday, 6 = Sunday in Python's weekday())
            if timestamp.weekday() >= 5:  # Saturday or Sunday
                continue
            
            # Generate price movement
            symbol_volatility = volatility.get(symbol, 2.0)
            price_change_pct = random.uniform(-symbol_volatility, symbol_volatility) / 100.0
            price_change = current_price * price_change_pct
            
            # Calculate OHLCV values with some randomness
            open_price = current_price
            close_price = current_price + price_change
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.005))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.005))
            
            # Update current price for next iteration
            current_price = close_price
            
            # Generate volume with some randomness
            base_vol = volume_base.get(symbol, 10) * 1_000_000  # Convert to shares
            volume = int(base_vol * (1 + random.uniform(-0.3, 0.3)))
            
            # Format timestamp as expected by the API
            ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Store data in Alpha Vantage format
            symbol_data[ts_str] = {
                "1. open": f"{open_price:.4f}",
                "2. high": f"{high_price:.4f}",
                "3. low": f"{low_price:.4f}",
                "4. close": f"{close_price:.4f}",
                "5. volume": f"{volume}"
            }
        
        data[symbol] = symbol_data
    
    return data

def save_seed_data(data, output_file):
    """Save generated data to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Seed data saved to {output_file}")

def seed_database(data):
    """
    Seed the database with the provided data.
    
    Args:
        data: Dictionary of stock data by symbol and timestamp
        
    Returns:
        Dictionary with seeding statistics
    """
    stats = {
        "total_records": 0,
        "records_by_symbol": {},
        "success": True
    }
    
    # Initialize the database
    if not init_db():
        print("Failed to initialize database")
        stats["success"] = False
        return stats
    
    # Insert data for each symbol
    for symbol, symbol_data in data.items():
        success_count = 0
        
        for timestamp, data_point in symbol_data.items():
            if insert_stock_data(symbol, timestamp, data_point):
                success_count += 1
        
        stats["records_by_symbol"][symbol] = success_count
        stats["total_records"] += success_count
        
        print(f"Inserted {success_count} records for {symbol}")
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Seed the database with stock data')
    parser.add_argument('--generate', action='store_true', help='Generate new test data')
    parser.add_argument('--hours', type=int, default=72, help='Hours of data to generate')
    parser.add_argument('--input', type=str, default='seed_data.json', help='Input JSON file with stock data')
    parser.add_argument('--output', type=str, default='seed_data.json', help='Output file for generated data')
    
    args = parser.parse_args()
    
    if args.generate:
        print(f"Generating {args.hours} hours of test data for {', '.join(FANG_SYMBOLS)}...")
        data = generate_test_data(FANG_SYMBOLS, args.hours)
        save_seed_data(data, args.output)
    
    # Default to loading from file if it exists
    input_file = args.input
    if os.path.exists(input_file):
        print(f"Loading seed data from {input_file}...")
        data = load_seed_data(input_file)
    else:
        print(f"Input file {input_file} not found. Generating new data...")
        data = generate_test_data(FANG_SYMBOLS, args.hours)
        save_seed_data(data, args.output)
    
    print("Seeding database...")
    stats = seed_database(data)
    
    if stats["success"]:
        print(f"Database seeding completed. Inserted {stats['total_records']} records.")
        
        # Show database stats
        db_stats = get_db_stats()
        print("\nDatabase Statistics:")
        print(f"Total records: {db_stats['total_records']}")
        print(f"Records by symbol: {db_stats['records_by_symbol']}")
        print(f"Oldest record: {db_stats['oldest_record']}")
        print(f"Newest record: {db_stats['newest_record']}")
        print(f"Database size: {db_stats['db_size_bytes'] / 1024:.2f} KB")
    else:
        print("Database seeding failed.")

if __name__ == "__main__":
    main()