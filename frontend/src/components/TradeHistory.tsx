import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface TradeHistoryProps {
  apiUrl: string;
}

const TradeHistory: React.FC<TradeHistoryProps> = () => {
  // Mock data - will be replaced with real API calls
  const trades = [
    {
      id: 'TRADE247',
      symbol: 'BTCUSDT',
      side: 'LONG',
      entry: 42500.00,
      exit: 42850.00,
      pnl: 350.00,
      pnlPct: 0.82,
      duration: 145,
      reason: 'take_profit',
      timestamp: '2025-10-15 14:32:15',
    },
    {
      id: 'TRADE246',
      symbol: 'ETHUSDT',
      side: 'LONG',
      entry: 2985.50,
      exit: 2945.20,
      pnl: -40.30,
      pnlPct: -1.35,
      duration: 95,
      reason: 'stop_loss',
      timestamp: '2025-10-15 13:15:42',
    },
    {
      id: 'TRADE245',
      symbol: 'BNBUSDT',
      side: 'LONG',
      entry: 315.80,
      exit: 322.50,
      pnl: 67.00,
      pnlPct: 2.12,
      duration: 210,
      reason: 'take_profit',
      timestamp: '2025-10-15 11:48:23',
    },
    {
      id: 'TRADE244',
      symbol: 'SOLUSDT',
      side: 'LONG',
      entry: 98.45,
      exit: 101.20,
      pnl: 27.50,
      pnlPct: 2.79,
      duration: 180,
      reason: 'signal',
      timestamp: '2025-10-15 10:22:08',
    },
    {
      id: 'TRADE243',
      symbol: 'BTCUSDT',
      side: 'LONG',
      entry: 42100.00,
      exit: 41850.00,
      pnl: -25.00,
      pnlPct: -0.59,
      duration: 75,
      reason: 'stop_loss',
      timestamp: '2025-10-15 09:05:31',
    },
  ];

  return (
    <div className="trade-history">
      <div className="section-header">
        <h3>Recent Trades</h3>
        <span className="trade-count">{trades.length} trades shown</span>
      </div>

      <div className="table-container">
        <table className="trades-table">
          <thead>
            <tr>
              <th>Trade ID</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>P&L</th>
              <th>Duration</th>
              <th>Exit Reason</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => (
              <tr key={trade.id}>
                <td className="trade-id">{trade.id}</td>
                <td className="symbol">{trade.symbol.replace('USDT', '')}</td>
                <td>
                  <span className={`badge ${trade.side.toLowerCase()}`}>
                    {trade.side}
                  </span>
                </td>
                <td className="price">${trade.entry.toLocaleString()}</td>
                <td className="price">${trade.exit.toLocaleString()}</td>
                <td className={`pnl ${trade.pnl >= 0 ? 'positive' : 'negative'}`}>
                  <div className="pnl-content">
                    {trade.pnl >= 0 ? (
                      <TrendingUp size={16} />
                    ) : (
                      <TrendingDown size={16} />
                    )}
                    <span>${Math.abs(trade.pnl).toFixed(2)}</span>
                    <span className="pnl-pct">
                      ({trade.pnl >= 0 ? '+' : ''}{trade.pnlPct.toFixed(2)}%)
                    </span>
                  </div>
                </td>
                <td className="duration">{trade.duration}m</td>
                <td>
                  <span className={`reason-badge ${trade.reason}`}>
                    {trade.reason.replace('_', ' ')}
                  </span>
                </td>
                <td className="timestamp">{trade.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TradeHistory;
