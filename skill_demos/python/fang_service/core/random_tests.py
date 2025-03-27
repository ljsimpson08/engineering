# fang_service/core/random_tests.py

import random
import datetime
from fang_service.core.logging_config import get_logger
from fang_service.app_variables import FANG_SYMBOLS

logger = get_logger(__name__)

def run_random_tests(stocks_cache, number_of_tests=6):
    """
    Run random tests against the stocks cache to verify data availability.
    Tests randomly select symbols and timestamps to simulate real queries.
    
    Args:
        stocks_cache: StocksCache instance containing the stock data
        number_of_tests: Number of random tests to perform
    """
    logger.info("Running random tests...")

    # Verify we have symbols with data before proceeding
    symbols_with_data = []
    for symbol in FANG_SYMBOLS:
        if stocks_cache.get_data(symbol):
            symbols_with_data.append(symbol)
    
    if not symbols_with_data:
        logger.warning("No symbols have data available for random tests. Skipping.")
        return

    # Gather all timestamps from symbols that have data
    all_timestamps = set()
    for symbol in symbols_with_data:
        data = stocks_cache.get_data(symbol)
        if data:  # Extra check to ensure we have data
            all_timestamps.update(data.keys())

    if not all_timestamps:
        logger.warning("No timestamps available for random tests. Skipping.")
        return

    # Convert to sorted list for random.choice
    all_timestamps = sorted(list(all_timestamps))
    
    # Track test results for summary
    successful_tests = 0
    failed_tests = 0

    # Run the random tests
    for i in range(number_of_tests):
        # Choose a random symbol that has data
        symbol = random.choice(symbols_with_data)
        
        # Choose a random timestamp
        chosen_time = random.choice(all_timestamps)
        
        # Query from the cache
        data_point = stocks_cache.get_data(symbol).get(chosen_time)
        
        if data_point:
            logger.info(f"Test #{i+1}: Found data for {symbol} at {chosen_time}. {data_point}")
            successful_tests += 1
        else:
            logger.warning(f"Test #{i+1}: No data for {symbol} at {chosen_time}.")
            failed_tests += 1
    
    # Log summary of test results
    logger.info(f"Random tests complete: {successful_tests} successful, {failed_tests} failed")