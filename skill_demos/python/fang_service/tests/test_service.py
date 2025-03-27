# fang_service/tests/test_service.py

import unittest
from unittest.mock import patch, MagicMock, call
import datetime
import json
from fastapi.testclient import TestClient

from fang_service.core.data_fetcher import fetch_intraday_data, filter_data_past_72_hours
from fang_service.core.stocks_cache import StocksCache
from fang_service.core.random_tests import run_random_tests
from fang_service.main import app
from fang_service.app_variables import SERVICE_API_KEY

class TestDataFetcher(unittest.TestCase):
    """Tests for the data_fetcher module"""
    
    @patch('fang_service.core.data_fetcher.requests.get')
    def test_fetch_intraday_data_success(self, mock_get):
        """Test successful API data fetch"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (60min)": {
                "2023-03-24 10:00:00": {
                    "1. open": "100.0000",
                    "2. high": "101.0000",
                    "3. low": "99.0000",
                    "4. close": "100.5000",
                    "5. volume": "1000000"
                }
            }
        }
        mock_get.return_value = mock_response
        
        # Call the function
        result = fetch_intraday_data("AAPL")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertIn("2023-03-24 10:00:00", result)
        self.assertEqual(result["2023-03-24 10:00:00"]["1. open"], "100.0000")
    
    @patch('fang_service.core.data_fetcher.requests.get')
    def test_fetch_intraday_data_error(self, mock_get):
        """Test API error handling"""
        # Setup mock to raise exception
        mock_get.side_effect = Exception("API Error")
        
        # Call the function
        result = fetch_intraday_data("AAPL")
        
        # Assertions
        self.assertIsNone(result)
    
    def test_filter_data_past_72_hours(self):
        """Test filtering data to past 72 hours"""
        # Create test data
        now = datetime.datetime.utcnow()
        recent_time = (now - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        old_time = (now - datetime.timedelta(hours=100)).strftime("%Y-%m-%d %H:%M:%S")
        
        test_data = {
            recent_time: {"1. open": "100.00"},
            old_time: {"1. open": "90.00"}
        }
        
        # Call the function
        result = filter_data_past_72_hours(test_data)
        
        # Assertions
        self.assertEqual(len(result), 1)
        self.assertIn(recent_time, result)
        self.assertNotIn(old_time, result)
    
    def test_filter_data_empty_input(self):
        """Test filtering with empty input"""
        self.assertEqual(filter_data_past_72_hours(None), {})
        self.assertEqual(filter_data_past_72_hours({}), {})


class TestStocksCache(unittest.TestCase):
    """Tests for the StocksCache class"""
    
    def setUp(self):
        self.cache = StocksCache()
    
    @patch('fang_service.core.stocks_cache.fetch_intraday_data')
    def test_update_cache(self, mock_fetch):
        """Test cache update functionality"""
        # Setup mock data
        mock_data = {
            "2023-03-24 10:00:00": {
                "1. open": "100.0000",
                "2. high": "101.0000",
                "3. low": "99.0000",
                "4. close": "100.5000"
            }
        }
        mock_fetch.return_value = mock_data
        
        # Call the method
        result = self.cache.update_cache()
        
        # Assertions
        self.assertTrue(result)
        self.assertIsNotNone(self.cache.last_update)
        
        # Check that fetch was called for each symbol
        from fang_service.app_variables import FANG_SYMBOLS
        self.assertEqual(mock_fetch.call_count, len(FANG_SYMBOLS))
    
    def test_get_data(self):
        """Test retrieving data from the cache"""
        # Setup test data
        test_data = {"timestamp": {"1. open": "100.00"}}
        self.cache.cache = {"AAPL": test_data}
        
        # Test retrieval
        result = self.cache.get_data("AAPL")
        self.assertEqual(result, test_data)
        
        # Test case insensitivity
        result = self.cache.get_data("aapl")
        self.assertEqual(result, test_data)
        
        # Test missing symbol
        result = self.cache.get_data("MISSING")
        self.assertEqual(result, {})
    
    @patch('fang_service.core.stocks_cache.threading.Thread')
    def test_start_background_updater(self, mock_thread):
        """Test starting background updater thread"""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Call the method
        self.cache.start_background_updater()
        
        # Assertions
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()


class TestRandomTests(unittest.TestCase):
    """Tests for the random_tests module"""
    
    @patch('fang_service.core.random_tests.random.choice')
    def test_run_random_tests_empty_cache(self, mock_choice):
        """Test handling of empty cache"""
        mock_cache = MagicMock()
        mock_cache.get_data.return_value = {}
        
        # Call the function
        run_random_tests(mock_cache)
        
        # Verify random.choice wasn't called (no data to choose from)
        mock_choice.assert_not_called()
    
    @patch('fang_service.core.random_tests.random.choice')
    def test_run_random_tests_with_data(self, mock_choice):
        """Test random tests with data in cache"""
        # Setup mock cache with data
        mock_cache = MagicMock()
        test_data = {
            "2023-03-24 10:00:00": {"1. open": "100.00"}
        }
        mock_cache.get_data.return_value = test_data
        
        # Configure random.choice to return predictable values
        mock_choice.side_effect = ["FB", "2023-03-24 10:00:00"]
        
        # Call the function with a smaller number of tests for simplicity
        run_random_tests(mock_cache, number_of_tests=1)
        
        # Verify interactions
        mock_cache.get_data.assert_called()
        self.assertEqual(mock_choice.call_count, 2)  # Called for symbol and timestamp


class TestAPI(unittest.TestCase):
    """Tests for the API endpoints"""
    
    def setUp(self):
        self.client = TestClient(app)
        self.headers = {"x-api-key": SERVICE_API_KEY}
    
    def test_info_endpoint(self):
        """Test the /info endpoint"""
        response = self.client.get("/info")
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("description", data)
        self.assertIn("endpoint", data)
        self.assertEqual(data["endpoint"], "/getStock")
    
    def test_get_stock_auth_required(self):
        """Test that authentication is required"""
        # Request without API key
        response = self.client.get("/getStock?symbol=FB&date=2023-03-24&hour=10")
        
        # Assert unauthorized
        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid or missing API key", response.json()["detail"])
    
    @patch('fang_service.routers.get_stock.StocksCache')
    def test_get_stock_valid_request(self, mock_cache_class):
        """Test a valid request to get stock data"""
        # Setup mock cache
        mock_cache = MagicMock()
        mock_cache.get_data.return_value = {
            "2023-03-24 10:00:00": {
                "1. open": "100.0000",
                "2. high": "101.0000",
                "3. low": "99.0000",
                "4. close": "100.5000"
            }
        }
        mock_cache_class.return_value = mock_cache
        
        # Make request
        response = self.client.get(
            "/getStock?symbol=FB&date=2023-03-24&hour=10", 
            headers=self.headers
        )
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["symbol"], "FB")
        self.assertEqual(data["timestamp"], "2023-03-24 10:00:00")
        self.assertIn("data", data)
    
    @patch('fang_service.routers.get_stock.StocksCache')
    def test_get_stock_not_found(self, mock_cache_class):
        """Test request for non-existent data"""
        # Setup mock cache to return empty data
        mock_cache = MagicMock()
        mock_cache.get_data.return_value = {}
        mock_cache_class.return_value = mock_cache
        
        # Make request
        response = self.client.get(
            "/getStock?symbol=NONEXISTENT&date=2023-03-24&hour=10", 
            headers=self.headers
        )
        
        # Assertions
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()