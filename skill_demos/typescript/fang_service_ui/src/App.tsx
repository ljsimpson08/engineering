
import React, { useState } from 'react';
import axios from 'axios';
import { logJSON } from './logger';
import SymbolSelector from './components/SymbolSelector';
import DataDisplay from './components/DataDisplay';

// Adjust this to your actual FastAPI base URL
const BASE_API_URL = 'http://localhost:8000';
const API_KEY = '8f4b9e7d1c6a2305f8e9d7b6c5a4e3f2d1c0b9a8f7e6d5c4b3a2918f7e6d5c4';

// Define interfaces for your data structures
interface StockDataPoint {
  "1. open": string;
  "2. high": string;
  "3. low": string;
  "4. close": string;
  "5. volume": string;
  // Add any other fields your API returns
}

interface StockTimeSeries {
  [timestamp: string]: StockDataPoint;
}

interface StockDataResponse {
  [symbol: string]: StockTimeSeries;
}

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [stockData, setStockData] = useState<StockDataResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Example of logging in JSON format
  React.useEffect(() => {
    logJSON('info', 'React App mounted');
  }, []);

  const handleSymbolChange = (symbol: string) => {
    setSelectedSymbol(symbol);
    setStockData(null);
    setError(null);
  };

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);

    try {
      logJSON('info', 'Fetching all FANG data');
      // Example route: GET /allData -> returns { FB: {...}, AMZN: {...}, ... }
      const response = await axios.get<StockDataResponse>(`${BASE_API_URL}/api/allData`, {
        headers: {
          'x-api-key': API_KEY
        }
      });
      setStockData(response.data);
      logJSON('info', 'Fetch all data success', { symbols: Object.keys(response.data) });
    } catch (err: any) {
      logJSON('error', 'Error fetching all data', { error: err.toString() });
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchSymbolData = async () => {
    if (!selectedSymbol) return;

    setLoading(true);
    setError(null);

    try {
      logJSON('info', `Fetching data for symbol=${selectedSymbol}`);
      // Example route: GET /symbolData/<SYMBOL> -> returns { <SYMBOL>: {...} }
      const response = await axios.get<StockDataResponse>(`${BASE_API_URL}/api/symbolData/${selectedSymbol}`, {
        headers: {
          'x-api-key': API_KEY
        }
      });
      setStockData(response.data);
      logJSON('info', 'Fetch symbol data success', { symbol: selectedSymbol });
    } catch (err: any) {
      logJSON('error', 'Error fetching symbol data', { error: err.toString() });
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h1>FANG Service UI</h1>
      <button onClick={fetchAllData}>Fetch ALL Data</button>

      <SymbolSelector
        selectedSymbol={selectedSymbol}
        onSymbolChange={handleSymbolChange}
      />

      {selectedSymbol && (
        <button onClick={fetchSymbolData}>Fetch Data for {selectedSymbol}</button>
      )}

      <DataDisplay loading={loading} error={error} data={stockData} />
    </div>
  );
}

export default App;