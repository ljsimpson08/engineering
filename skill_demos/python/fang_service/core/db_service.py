# fang_service/core/db_service.py

import time
import threading
import datetime
from typing import Dict, Any, Optional, List
import concurrent.futures

from fang_service.core.data_fetcher import fetch_intraday_data
from fang_service.core.logging_config import get_logger
from fang_service.app_variables import FANG_SYMBOLS, FETCH_INTERVAL_HOURS
from fang_service.core.db_models import (
    get_stock_data, insert_stock_data, get_symbols_with_data,
    purge_old_data, get_db_stats
)
from fang_service.core.exceptions import RateLimitError, NetworkError, DataRetrievalError

logger = get_logger(__name__)

class StockDataService:
    """
    Service for managing stock data in SQLite database with automatic background updates.
    
    This service manages stock data with a SQLite database backend, replacing the 
    in-memory cache with persistent storage. It maintains the same interface as
    the original StocksCache class for compatibility with the existing code.
    """
    
    def __init__(self):
        """Initialize the data service with thread synchronization."""
        self.last_update: Optional[datetime.datetime] = None
        
        # Thread synchronization
        self._lock = threading.RLock()  # Reentrant lock allows nested locking from same thread
        self._updater_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Statistics for monitoring and debugging
        self.update_count = 0
        self.failed_updates = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def update_cache(self) -> bool:
        """
        Fetch fresh intraday data for all configured symbols and store in the database.
        
        Uses a thread pool to parallelize fetching data for multiple symbols,
        significantly improving update performance.
        
        Returns:
            bool: True if update was successful (all symbols updated), False otherwise
        """
        logger.info("Updating stock database...")
        update_start_time = time.time()
        update_success = True
        symbols_updated = 0
        
        # Use thread lock to prevent concurrent updates
        with self._lock:
            max_workers = min(10, len(FANG_SYMBOLS))  # Limit max concurrency
            # Use ThreadPoolExecutor for parallel fetching
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Start all fetch tasks
                future_to_symbol = {
                    executor.submit(self._fetch_and_store, symbol): symbol 
                    for symbol in FANG_SYMBOLS
                }
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        # Get result from the future
                        success, count = future.result()
                        
                        if success:
                            symbols_updated += 1
                            logger.info(f"Updated database for {symbol} with {count} data points")
                        else:
                            logger.warning(f"Failed to update database for {symbol}")
                            update_success = False
                            
                    except Exception as e:
                        logger.error(f"Exception updating database for {symbol}: {str(e)}", exc_info=True)
                        update_success = False
            
            # Purge old data
            purge_old_data()
            
            # Update timestamp and statistics
            self.last_update = datetime.datetime.utcnow()
            self.update_count += 1
            if not update_success:
                self.failed_updates += 1
        
        # Calculate and log performance metrics
        update_time = time.time() - update_start_time
        logger.info(
            f"Database update completed in {update_time:.2f}s. "
            f"Updated {symbols_updated}/{len(FANG_SYMBOLS)} symbols. "
            f"Success: {update_success}"
        )
        
        return update_success
    
    def _fetch_and_store(self, symbol: str) -> tuple[bool, int]:
        """
        Helper method to fetch data for a single symbol and store in the database.
        
        This method is designed to be run in a thread pool to parallelize
        fetching data for multiple symbols.
        
        Args:
            symbol: Stock symbol to fetch data for
            
        Returns:
            Tuple of (success, data_points_count)
        """
        try:
            # Fetch data from Alpha Vantage
            raw_data = fetch_intraday_data(symbol)
            if not raw_data:
                return False, 0
                
            # Store each data point in the database
            success_count = 0
            for timestamp, data_point in raw_data.items():
                if insert_stock_data(symbol, timestamp, data_point):
                    success_count += 1
                    
            return True, success_count
        except RateLimitError as e:
            # Handle rate limiting with a warning instead of an error
            logger.warning(f"Rate limit encountered for {symbol}: {e.message}")
            # Return a partial success if we got some data
            return success_count > 0, success_count
        except (NetworkError, DataRetrievalError) as e:
            logger.error(f"Error in fetch_and_store for {symbol}: {e.message}")
            return False, 0
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_store for {symbol}: {str(e)}", exc_info=True)
            return False, 0

    def get_data(self, symbol: str) -> Dict[str, Dict[str, str]]:
        """
        Return data for a symbol from the database.
        
        Args:
            symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
            
        Returns:
            Dictionary of stock data for the symbol, or empty dict if not found
        """
        with self._lock:
            symbol = symbol.upper()
            result = get_stock_data(symbol)
            
            # Update statistics
            if result:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
                
            return result

    def get_symbols_with_data(self) -> List[str]:
        """
        Return a list of symbols that have data in the database.
        
        Returns:
            List of symbols with data
        """
        with self._lock:
            return get_symbols_with_data()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the database and service usage.
        
        Returns:
            Dictionary of database and service statistics
        """
        with self._lock:
            # Get database stats
            db_stats = get_db_stats()
            
            # Calculate cache hit rate
            total_accesses = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_accesses * 100) if total_accesses > 0 else 0
            
            # Calculate cache age in seconds if last_update exists
            cache_age_seconds = None
            if self.last_update:
                cache_age_seconds = (datetime.datetime.utcnow() - self.last_update).total_seconds()
            
            # Combine service stats with database stats
            return {
                "update_count": self.update_count,
                "failed_updates": self.failed_updates,
                "last_update": self.last_update.isoformat() if self.last_update else None,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate_percentage": round(hit_rate, 2),
                "symbols_cached": db_stats["symbols_with_data"],
                "total_data_points": db_stats["total_records"],
                "cache_age_seconds": cache_age_seconds,
                "db_stats": db_stats
            }

    def start_background_updater(self):
        """
        Starts a background thread that updates the database every FETCH_INTERVAL_HOURS.
        Thread-safe, ensures only one updater thread is running.
        """
        with self._lock:
            if self._updater_thread and self._updater_thread.is_alive():
                logger.warning("Background updater already running")
                return
                
            # Reset stop event
            self._stop_event.clear()
            
            # Define the updater function
            def updater():
                logger.info(f"Background updater started with {FETCH_INTERVAL_HOURS} hour interval")
                
                while not self._stop_event.is_set():
                    try:
                        self.update_cache()
                    except Exception as e:
                        logger.error(f"Error in background updater: {str(e)}", exc_info=True)
                        
                    # Sleep with interruption support
                    sleep_interval = FETCH_INTERVAL_HOURS * 3600  # Convert hours to seconds
                    logger.debug(f"Background updater sleeping for {sleep_interval} seconds")
                    
                    # Wait with timeout allows for clean shutdown
                    self._stop_event.wait(timeout=sleep_interval)
                    
                logger.info("Background updater stopped")

            # Start the thread
            self._updater_thread = threading.Thread(
                target=updater,
                name="StockDataUpdater",
                daemon=True  # Daemon thread will terminate when main program exits
            )
            self._updater_thread.start()
            logger.info("Background database updater thread started")

    def stop_background_updater(self):
        """
        Signals the background updater thread to stop and waits for it to finish.
        Ensures graceful shutdown of background thread.
        """
        with self._lock:
            if not self._updater_thread or not self._updater_thread.is_alive():
                logger.warning("No active background updater to stop")
                return
                
            logger.info("Stopping background updater...")
            self._stop_event.set()
            
            # Wait for the thread to finish with timeout
            self._updater_thread.join(timeout=10.0)
            
            if self._updater_thread.is_alive():
                logger.warning("Background updater did not stop gracefully within timeout")
            else:
                logger.info("Background updater stopped successfully")
                self._updater_thread = None