# fang_service/core/db_models.py

import os
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
import datetime
from contextlib import contextmanager
from pathlib import Path

from fang_service.core.logging_config import get_logger
from fang_service.app_variables import FANG_SYMBOLS, MAX_CACHE_AGE_HOURS

logger = get_logger(__name__)

# Default database location
DB_DIR = os.environ.get('DB_DIR', 'data')
DB_NAME = os.environ.get('DB_NAME', 'fang_stocks.db')
DB_PATH = os.path.join(DB_DIR, DB_NAME)

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)

def get_db_path() -> str:
    """Return the path to the SQLite database file."""
    return DB_PATH

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db() -> bool:
    """Initialize the database schema."""
    logger.info(f"Initializing database at {DB_PATH}")
    
    # SQL for creating tables
    create_tables_sql = """
    CREATE TABLE IF NOT EXISTS stock_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(symbol, timestamp)
    );
    
    CREATE INDEX IF NOT EXISTS idx_stock_data_symbol ON stock_data(symbol);
    CREATE INDEX IF NOT EXISTS idx_stock_data_timestamp ON stock_data(timestamp);
    """
    
    try:
        with get_db_connection() as conn:
            conn.executescript(create_tables_sql)
            conn.commit()
        logger.info("Database initialized successfully")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        return False

def insert_stock_data(symbol: str, timestamp: str, data: Dict[str, str]) -> bool:
    """
    Insert stock data into the database.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        timestamp: Timestamp string in format "YYYY-MM-DD HH:MM:SS"
        data: Dictionary with keys "1. open", "2. high", etc.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract values from the Alpha Vantage format
        open_price = float(data.get("1. open", 0))
        high_price = float(data.get("2. high", 0))
        low_price = float(data.get("3. low", 0))
        close_price = float(data.get("4. close", 0))
        volume = int(data.get("5. volume", 0))
        created_at = datetime.datetime.utcnow().isoformat() + "Z"
        
        insert_sql = """
        INSERT OR REPLACE INTO stock_data 
        (symbol, timestamp, open, high, low, close, volume, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        with get_db_connection() as conn:
            conn.execute(
                insert_sql, 
                (symbol, timestamp, open_price, high_price, low_price, close_price, volume, created_at)
            )
            conn.commit()
        return True
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error inserting stock data for {symbol} at {timestamp}: {e}")
        return False

def get_stock_data(symbol: str) -> Dict[str, Dict[str, str]]:
    """
    Get all stock data for a specific symbol.
    
    Args:
        symbol: Stock symbol (e.g., FB, AMZN, NFLX, GOOG)
        
    Returns:
        Dictionary with timestamps as keys and stock data as values
    """
    result = {}
    
    try:
        # Get recent data (within MAX_CACHE_AGE_HOURS)
        cutoff_time = (datetime.datetime.utcnow() - datetime.timedelta(hours=MAX_CACHE_AGE_HOURS))
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        
        select_sql = """
        SELECT timestamp, open, high, low, close, volume
        FROM stock_data
        WHERE symbol = ? AND timestamp >= ?
        ORDER BY timestamp DESC
        """
        
        with get_db_connection() as conn:
            rows = conn.execute(select_sql, (symbol.upper(), cutoff_str)).fetchall()
            
            for row in rows:
                # Convert back to the Alpha Vantage format expected by the existing code
                result[row['timestamp']] = {
                    "1. open": str(row['open']),
                    "2. high": str(row['high']),
                    "3. low": str(row['low']),
                    "4. close": str(row['close']),
                    "5. volume": str(row['volume'])
                }
                
        return result
    except sqlite3.Error as e:
        logger.error(f"Error retrieving stock data for {symbol}: {e}")
        return {}

def get_symbols_with_data() -> List[str]:
    """
    Get a list of symbols that have data in the database.
    
    Returns:
        List of symbols with data
    """
    try:
        select_sql = """
        SELECT DISTINCT symbol FROM stock_data
        """
        
        with get_db_connection() as conn:
            rows = conn.execute(select_sql).fetchall()
            return [row['symbol'] for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving symbols with data: {e}")
        return []

def get_available_timestamps(symbol: str = None) -> List[str]:
    """
    Get a list of all available timestamps in the database.
    
    Args:
        symbol: Optional filter by symbol
        
    Returns:
        List of timestamp strings
    """
    try:
        if symbol:
            select_sql = """
            SELECT DISTINCT timestamp FROM stock_data
            WHERE symbol = ?
            ORDER BY timestamp
            """
            params = (symbol.upper(),)
        else:
            select_sql = """
            SELECT DISTINCT timestamp FROM stock_data
            ORDER BY timestamp
            """
            params = ()
            
        with get_db_connection() as conn:
            rows = conn.execute(select_sql, params).fetchall()
            return [row['timestamp'] for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving available timestamps: {e}")
        return []

def purge_old_data() -> int:
    """
    Remove data older than MAX_CACHE_AGE_HOURS.
    
    Returns:
        Number of rows deleted
    """
    try:
        cutoff_time = (datetime.datetime.utcnow() - datetime.timedelta(hours=MAX_CACHE_AGE_HOURS))
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        
        delete_sql = """
        DELETE FROM stock_data
        WHERE timestamp < ?
        """
        
        with get_db_connection() as conn:
            cursor = conn.execute(delete_sql, (cutoff_str,))
            deleted_count = cursor.rowcount
            conn.commit()
            
        logger.info(f"Purged {deleted_count} records older than {MAX_CACHE_AGE_HOURS} hours")
        return deleted_count
    except sqlite3.Error as e:
        logger.error(f"Error purging old data: {e}")
        return 0

def get_db_stats() -> Dict[str, Any]:
    """
    Get statistics about the database.
    
    Returns:
        Dictionary with database statistics
    """
    stats = {
        "total_records": 0,
        "records_by_symbol": {},
        "oldest_record": None,
        "newest_record": None,
        "symbols_with_data": [],
        "db_path": DB_PATH,
        "db_size_bytes": 0
    }
    
    try:
        # Get file size
        if os.path.exists(DB_PATH):
            stats["db_size_bytes"] = os.path.getsize(DB_PATH)
        
        with get_db_connection() as conn:
            # Total records
            cursor = conn.execute("SELECT COUNT(*) as count FROM stock_data")
            stats["total_records"] = cursor.fetchone()['count']
            
            # Records by symbol
            cursor = conn.execute("SELECT symbol, COUNT(*) as count FROM stock_data GROUP BY symbol")
            for row in cursor.fetchall():
                stats["records_by_symbol"][row['symbol']] = row['count']
            
            # Symbols with data
            stats["symbols_with_data"] = list(stats["records_by_symbol"].keys())
            
            # Oldest and newest records
            if stats["total_records"] > 0:
                cursor = conn.execute("SELECT MIN(timestamp) as oldest FROM stock_data")
                stats["oldest_record"] = cursor.fetchone()['oldest']
                
                cursor = conn.execute("SELECT MAX(timestamp) as newest FROM stock_data")
                stats["newest_record"] = cursor.fetchone()['newest']
        
        return stats
    except sqlite3.Error as e:
        logger.error(f"Error getting database stats: {e}")
        return stats

# Initialize the database on module import
init_db()