import React from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { TrendingUp, DollarSign, Activity, AlertCircle, Target } from 'lucide-react';

interface StrategyPanelProps {
  apiUrl: string;
  strategyId: string; // 'a', 'b', or 'c'
  strategyName: string;
  strategyDescription: string;
  colorScheme: 'blue' | 'green' | 'orange';
}

const StrategyPanel: React.FC<StrategyPanelProps> = ({
  apiUrl,
  strategyId,
  strategyName,
  strategyDescription,
  colorScheme
}) => {
  const { data: performanceData, isLoading } = useQuery({
    queryKey: ['strategy-performance', strategyId],
    queryFn: async () => {
      const response = await axios.get(`${apiUrl}/api/v1/trading/performance/${strategyId}`);
      return response.data;
    },
    refetchInterval: 10000, // Update every 10 seconds
  });

  const colorClasses = {
    blue: {
      bg: 'strategy-panel-blue',
      header: 'strategy-header-blue',
      stat: 'stat-icon-blue'
    },
    green: {
      bg: 'strategy-panel-green',
      header: 'strategy-header-green',
      stat: 'stat-icon-green'
    },
    orange: {
      bg: 'strategy-panel-orange',
      header: 'strategy-header-orange',
      stat: 'stat-icon-orange'
    }
  };

  const colors = colorClasses[colorScheme];

  if (isLoading || performanceData?.status === 'not_started') {
    return (
      <div className={`strategy-panel ${colors.bg}`}>
        <div className={`strategy-panel-header ${colors.header}`}>
          <h2>{strategyName}</h2>
          <p className="strategy-description">{strategyDescription}</p>
        </div>
        <div className="strategy-panel-body">
          <div className="strategy-not-started">
            <AlertCircle size={48} />
            <p>Strategy not started</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`strategy-panel ${colors.bg}`}>
      {/* Header */}
      <div className={`strategy-panel-header ${colors.header}`}>
        <h2>{strategyName}</h2>
        <p className="strategy-description">{strategyDescription}</p>
      </div>

      {/* Stats Grid */}
      <div className="strategy-stats-grid">
        <div className="strategy-stat-card">
          <div className={`stat-icon ${colors.stat}`}>
            <TrendingUp size={20} />
          </div>
          <div className="stat-info">
            <p className="stat-label">Win Rate</p>
            <p className="stat-value">
              {performanceData?.win_rate !== undefined
                ? `${performanceData.win_rate.toFixed(1)}%`
                : 'N/A'}
            </p>
          </div>
        </div>

        <div className="strategy-stat-card">
          <div className={`stat-icon ${colors.stat}`}>
            <DollarSign size={20} />
          </div>
          <div className="stat-info">
            <p className="stat-label">Total P&L</p>
            <p className={`stat-value ${performanceData?.total_pnl >= 0 ? 'positive' : 'negative'}`}>
              {performanceData?.total_pnl !== undefined
                ? `${performanceData.total_pnl > 0 ? '+' : ''}$${performanceData.total_pnl.toFixed(2)}`
                : 'N/A'}
            </p>
          </div>
        </div>

        <div className="strategy-stat-card">
          <div className={`stat-icon ${colors.stat}`}>
            <Activity size={20} />
          </div>
          <div className="stat-info">
            <p className="stat-label">Trades</p>
            <p className="stat-value">
              {performanceData?.total_trades ?? 'N/A'}
            </p>
            <p className="stat-sublabel">
              {performanceData?.trades_per_day
                ? `${performanceData.trades_per_day.toFixed(1)}/day`
                : ''}
            </p>
          </div>
        </div>

        <div className="strategy-stat-card">
          <div className={`stat-icon ${colors.stat}`}>
            <Target size={20} />
          </div>
          <div className="stat-info">
            <p className="stat-label">Active</p>
            <p className="stat-value">
              {performanceData?.active_positions ?? 'N/A'}
            </p>
            <p className="stat-sublabel">positions</p>
          </div>
        </div>
      </div>

      {/* Additional Metrics */}
      <div className="strategy-metrics">
        <div className="metric-row">
          <span className="metric-label">Avg Profit/Trade:</span>
          <span className={`metric-value ${performanceData?.avg_profit_per_trade >= 0 ? 'positive' : 'negative'}`}>
            ${performanceData?.avg_profit_per_trade?.toFixed(2) ?? 'N/A'}
          </span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Max Drawdown:</span>
          <span className="metric-value">
            {performanceData?.max_drawdown?.toFixed(1) ?? 'N/A'}%
          </span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Total Return:</span>
          <span className={`metric-value ${performanceData?.total_return >= 0 ? 'positive' : 'negative'}`}>
            {performanceData?.total_return !== undefined
              ? `${performanceData.total_return > 0 ? '+' : ''}${performanceData.total_return.toFixed(2)}%`
              : 'N/A'}
          </span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Signals Generated:</span>
          <span className="metric-value">
            {performanceData?.signals_generated ?? 'N/A'}
          </span>
        </div>
        <div className="metric-row">
          <span className="metric-label">Cooldown Skipped:</span>
          <span className="metric-value">
            {performanceData?.signals_skipped_cooldown ?? 'N/A'}
          </span>
        </div>
      </div>

      {/* Active Positions */}
      {performanceData?.active_positions_list && performanceData.active_positions_list.length > 0 && (
        <div className="strategy-positions">
          <h4>Active Positions</h4>
          <div className="positions-list">
            {performanceData.active_positions_list.map((pos: any, idx: number) => (
              <div key={idx} className="position-item">
                <div className="position-header">
                  <span className="position-symbol">{pos.symbol}</span>
                  <span className={`position-type ${pos.type.toLowerCase()}`}>{pos.type}</span>
                </div>
                <div className="position-details">
                  <div className="position-detail">
                    <span>Entry:</span>
                    <span>${pos.entry_price?.toFixed(2)}</span>
                  </div>
                  <div className="position-detail">
                    <span>Current:</span>
                    <span>${pos.current_price?.toFixed(2)}</span>
                  </div>
                  <div className="position-detail">
                    <span>P&L:</span>
                    <span className={pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
                      ${pos.unrealized_pnl?.toFixed(2)} ({pos.unrealized_pnl_pct?.toFixed(2)}%)
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StrategyPanel;
