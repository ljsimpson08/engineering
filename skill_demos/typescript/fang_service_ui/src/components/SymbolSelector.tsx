/**
 * fang_service_ui/src/components/SymbolSelector.tsx
 *
 * A dropdown to select a symbol from the known FANG list.
 * Staff-level comment: In a production UI, you'd likely fetch
 * the list of symbols from the server or a config. For this example,
 * we simply hardcode the typical FANG set.
 */
import React from 'react';

interface SymbolSelectorProps {
  selectedSymbol: string;
  onSymbolChange: (symbol: string) => void;
}

const FANG_SYMBOLS = ["FB", "AMZN", "NFLX", "GOOG"];

const SymbolSelector: React.FC<SymbolSelectorProps> = ({ selectedSymbol, onSymbolChange }) => {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <label htmlFor="symbol-select">Select Symbol: </label>
      <select
        id="symbol-select"
        value={selectedSymbol}
        onChange={(e) => onSymbolChange(e.target.value)}
      >
        <option value="">-- All Symbols --</option>
        {FANG_SYMBOLS.map((sym) => (
          <option key={sym} value={sym}>
            {sym}
          </option>
        ))}
      </select>
    </div>
  );
};

export default SymbolSelector;
