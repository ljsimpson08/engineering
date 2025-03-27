/**
 * fang_service_ui/src/components/DataDisplay.tsx
 *
 * Displays either:
 *  - All cached stock data returned by the server, OR
 *  - Data filtered by symbol, if a symbol was selected.
 */
import React from 'react';

interface DataDisplayProps {
  loading: boolean;
  error: string | null;
  data: any; // For brevity, "any". In production code, define a type interface
}

const DataDisplay: React.FC<DataDisplayProps> = ({ loading, error, data }) => {
  if (loading) return <p>Loading...</p>;
  if (error)   return <p style={{ color: 'red' }}>Error: {error}</p>;
  if (!data)   return <p>No data to display.</p>;

  // If the data is an object keyed by symbol -> timestamp -> OHLC, etc.
  // We'll just do a nested display. Adjust to your actual schema.
  return (
    <div style={{ maxHeight: '300px', overflowY: 'scroll', border: '1px solid #ccc' }}>
      {Object.keys(data).map((symbol) => {
        const timestamps = data[symbol];
        return (
          <div key={symbol}>
            <h3>{symbol}</h3>
            {Object.keys(timestamps).map((ts) => {
              const details = timestamps[ts];
              return (
                <div key={ts} style={{ marginLeft: '1rem' }}>
                  <strong>{ts}</strong> : {JSON.stringify(details)}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export default DataDisplay;
