# fang_service/core/stocks_cache.py

import time
import threading
import datetime
from typing import Dict, Any, Optional
import concurrent.futures
from threading import RLock

from fang_service.core.data_fetcher import fetch_intraday_data, filter_data_past_72_hours
from fang_service.core.logging_config import get_logger
from fang_service.app_variables import FANG_SYMBOLS, FETCH_INTERVAL_HOURS, MAX_CACHE_AGE_HOURS

logger = get_logger(__name__)

class StocksCache:
    """
    Thread-safe in-memory cache for stock data with automatic background updates.
    
    The cache maintains a rolling window of stock data for the configured symbols,
    automatically refreshing at the configured interval. All methods are thread-safe.
    """
    
    def __init__(self):
        """Initialize an empty cache with thread synchronization."""
        # Data structure: { symbol: { "YYYY-MM-DD HH:MM:SS": { open, high, ... } } }
        self.cache: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.last_update: Optional[datetime.datetime] = None
        
        # Thread synchronization
        self._lock = RLock()
        self._updater_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Statistics
        self.update_count = 0
        self.failed_updates = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def update_cache(self) -> bool:
        """
        Fetch fresh intraday data for all configured symbols, filter to the past
        MAX_CACHE_AGE_HOURS, and store in memory. Thread-safe.
        
        Returns:
            bool: True if update was successful, False otherwise
        """
        logger.info("Updating stocks cache...")
        update_start_time = time.time()
        update_success = True
        symbols_updated = 0
        
        # Use thread lock to prevent concurrent updates
        with self._lock:
            # Use ThreadPoolExecutor for parallel fetching
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(FANG_SYMBOLS))) as executor:
                # Start all fetch tasks
                future_to_symbol = {
                    executor.submit(self._fetch_and_filter, symbol): symbol 
                    for symbol in FANG_SYMBOLS
                }
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        # Get result from the future
                        filtered_data = future.result()
                        
                        if filtered_data:
                            self.cache[symbol] = filtered_data
                            data_points = len(filtered_data)
                            symbols_updated += 1
                            logger.info(f"Updated cache for {symbol} with {data_points} data points")
                        else:
                            logger.warning(f"Failed to update cache for {symbol}")
                            update_success = False
                            
                    except Exception as e:
                        logger.error(f"Exception updating cache for {symbol}: {str(e)}", exc_info=True)
                        update_success = False
            
            # Update timestamp and statistics
            self.last_update = datetime.datetime.utcnow()
            self.update_count += 1
            if not update_success:
                self.failed_updates += 1
        
        # Calculate and log performance metrics
        update_time = time.time() - update_start_time
        logger.info(
            f"Cache update completed in {update_time:.2f}s. "
            f"Updated {symbols_updated}/{len(FANG_SYMBOLS)} symbols. "
            f"Success: {update_success}"
        )
        
        return update_success
    
    def _fetch_and_filter(self, symbol: str) -> Optional[Dict[str, Dict[str, str]]]:
        """
        Helper method to fetch and filter data for a single symbol.
        
        Args:
            symbol: Stock symbol to fetch data for
            
        Returns:
            Filtered dictionary of stock data or None on failure
        """
        try:
            raw_data = fetch_intraday_data(symbol)
            filtered = filter_data_past_72_hours(raw_data)
            return filtered
        except Exception as e:
            logger.error(f"Error in fetch_and_filter for {symbol}: {str(e)}", exc_info=True)
            return None

    def get_data(self, symbol: str) -> Dict[str, Dict[str, str]]:
        """
        Return the entire dictionary of data for a symbol from the cache.
        Thread-safe. Tracks cache hit/miss statistics.
        
        Args:
            symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
            
        Returns:
            Dictionary of stock data for the symbol, or empty dict if not found
        """
        with self._lock:
            symbol = symbol.upper()
            result = self.cache.get(symbol, {})
            
            # Update statistics
            if result:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
                
            return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache usage and performance.
        
        Returns:
            Dictionary of cache statistics
        """
        with self._lock:
            total_accesses = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_accesses * 100) if total_accesses > 0 else 0
            
            return {
                "update_count": self.update_count,
                "failed_updates": self.failed_updates,
                "last_update": self.last_update.isoformat() if self.last_update else None,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_rate_percentage": round(hit_rate, 2),
                "symbols_cached": list(self.cache.keys()),
                "total_data_points": sum(len(data) for data in self.cache.values()),
                "cache_age_seconds": (datetime.datetime.utcnow() - self.last_update).total_seconds() 
                                     if self.last_update else None
            }

    def start_background_updater(self):
        """
        Starts a background thread that updates the cache every FETCH_INTERVAL_HOURS.
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
                    sleep_interval = FETCH_INTERVAL_HOURS * 3600
                    logger.debug(f"Background updater sleeping for {sleep_interval} seconds")
                    self._stop_event.wait(timeout=sleep_interval)
                    
                logger.info("Background updater stopped")

            # Start the thread
            self._updater_thread = threading.Thread(
                target=updater,
                name="StocksCacheUpdater",
                daemon=True
            )
            self._updater_thread.start()
            logger.info("Background cache updater thread started")

    def stop_background_updater(self):
        """
        Signals the background updater thread to stop and waits for it to finish.
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
                logger.warning("Background updater did not stop gracefully")
            else:
                logger.info("Background updater stopped successfully")
                self._updater_thread = None