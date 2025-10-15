import React from 'react';
import { TrendingUp, Target, BarChart3, AlertTriangle } from 'lucide-react';

interface PerformanceMetricsProps {
  apiUrl: string;
}

const PerformanceMetrics: React.FC<PerformanceMetricsProps> = () => {
  // Mock data - will be replaced with real API calls
  const metrics = {
    winRate: 58.3,
    profitFactor: 1.82,
    sharpeRatio: 1.23,
    maxDrawdown: 18.4,
    totalTrades: 247,
    winningTrades: 144,
    losingTrades: 103,
    avgWin: 87.50,
    avgLoss: 45.20,
    avgDuration: 145,
  };

  return (
    <div className="performance-metrics">
      <h3>Performance Metrics</h3>

      <div className="metrics-list">
        <div className="metric-item">
          <div className="metric-icon green">
            <Target size={20} />
          </div>
          <div className="metric-content">
            <span className="metric-label">Win Rate</span>
            <span className="metric-value">{metrics.winRate}%</span>
            <div className="metric-bar">
              <div
                className="metric-bar-fill green"
                style={{ width: `${metrics.winRate}%` }}
              />
            </div>
          </div>
        </div>

        <div className="metric-item">
          <div className="metric-icon blue">
            <TrendingUp size={20} />
          </div>
          <div className="metric-content">
            <span className="metric-label">Profit Factor</span>
            <span className="metric-value">{metrics.profitFactor.toFixed(2)}</span>
            <span className="metric-subtext">
              Target: &gt; 1.5
            </span>
          </div>
        </div>

        <div className="metric-item">
          <div className="metric-icon purple">
            <BarChart3 size={20} />
          </div>
          <div className="metric-content">
            <span className="metric-label">Sharpe Ratio</span>
            <span className="metric-value">{metrics.sharpeRatio.toFixed(2)}</span>
            <span className="metric-subtext">
              Risk-adjusted return
            </span>
          </div>
        </div>

        <div className="metric-item">
          <div className="metric-icon orange">
            <AlertTriangle size={20} />
          </div>
          <div className="metric-content">
            <span className="metric-label">Max Drawdown</span>
            <span className="metric-value negative">-{metrics.maxDrawdown}%</span>
            <div className="metric-bar">
              <div
                className="metric-bar-fill orange"
                style={{ width: `${(metrics.maxDrawdown / 25) * 100}%` }}
              />
            </div>
          </div>
        </div>

        <div className="metric-divider" />

        <div className="metric-row">
          <div className="metric-stat">
            <span className="stat-label">Total Trades</span>
            <span className="stat-value">{metrics.totalTrades}</span>
          </div>
          <div className="metric-stat">
            <span className="stat-label">Winning</span>
            <span className="stat-value green">{metrics.winningTrades}</span>
          </div>
          <div className="metric-stat">
            <span className="stat-label">Losing</span>
            <span className="stat-value red">{metrics.losingTrades}</span>
          </div>
        </div>

        <div className="metric-row">
          <div className="metric-stat">
            <span className="stat-label">Avg Win</span>
            <span className="stat-value green">${metrics.avgWin}</span>
          </div>
          <div className="metric-stat">
            <span className="stat-label">Avg Loss</span>
            <span className="stat-value red">${metrics.avgLoss}</span>
          </div>
          <div className="metric-stat">
            <span className="stat-label">Avg Duration</span>
            <span className="stat-value">{metrics.avgDuration}m</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PerformanceMetrics;
