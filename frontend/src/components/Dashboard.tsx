import React from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import PriceCards from './PriceCards';
import PerformanceMetrics from './PerformanceMetrics';
import PriceChart from './PriceChart';
import TradeHistory from './TradeHistory';
import SystemStatus from './SystemStatus';
import { Activity, TrendingUp, DollarSign, AlertCircle } from 'lucide-react';

interface DashboardProps {
  apiUrl: string;
}

const Dashboard: React.FC<DashboardProps> = ({ apiUrl }) => {
  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await axios.get(`${apiUrl}/health`);
      return response.data;
    },
  });

  const { data: pricesData } = useQuery({
    queryKey: ['prices'],
    queryFn: async () => {
      const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'];
      const response = await axios.get(
        `${apiUrl}/api/v1/market/prices?symbols=${symbols.join(',')}`
      );
      return response.data;
    },
  });

  // Fetch real-time performance metrics
  const { data: performanceData } = useQuery({
    queryKey: ['performance'],
    queryFn: async () => {
      const response = await axios.get(`${apiUrl}/api/v1/trading/performance`);
      return response.data;
    },
    refetchInterval: 10000, // Update every 10 seconds
  });

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-content">
          <div className="logo">
            <Activity size={32} />
            <h1>TradingBot V2</h1>
          </div>
          <SystemStatus healthData={healthData} />
        </div>
      </header>

      {/* Main Content */}
      <div className="dashboard-content">
        {/* Top Stats - Real-time data */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon blue">
              <TrendingUp size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Win Rate</p>
              <p className="stat-value">
                {performanceData?.win_rate
                  ? `${performanceData.win_rate.toFixed(1)}%`
                  : 'Loading...'}
              </p>
              <p className="stat-change positive">
                {performanceData?.win_rate_change
                  ? `${performanceData.win_rate_change > 0 ? '+' : ''}${performanceData.win_rate_change.toFixed(1)}% vs baseline`
                  : 'Calculating...'}
              </p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon green">
              <DollarSign size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Total P&L</p>
              <p className="stat-value">
                {performanceData?.total_pnl !== undefined
                  ? `${performanceData.total_pnl > 0 ? '+' : ''}$${performanceData.total_pnl.toFixed(2)}`
                  : 'Loading...'}
              </p>
              <p className={`stat-change ${performanceData?.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                {performanceData?.total_return
                  ? `${performanceData.total_return > 0 ? '+' : ''}${performanceData.total_return.toFixed(2)}%`
                  : 'Calculating...'}
              </p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon purple">
              <Activity size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Total Trades</p>
              <p className="stat-value">
                {performanceData?.total_trades ?? 'Loading...'}
              </p>
              <p className="stat-change neutral">
                {performanceData?.active_positions
                  ? `${performanceData.active_positions} active positions`
                  : 'Real-time trading'}
              </p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon orange">
              <AlertCircle size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Max Drawdown</p>
              <p className="stat-value">
                {performanceData?.max_drawdown
                  ? `${performanceData.max_drawdown.toFixed(1)}%`
                  : 'Loading...'}
              </p>
              <p className="stat-change neutral">
                {performanceData?.risk_status ?? 'Monitoring...'}
              </p>
            </div>
          </div>
        </div>

        {/* Price Cards */}
        <PriceCards pricesData={pricesData} />

        {/* Charts and Metrics */}
        <div className="charts-grid">
          <div className="chart-section">
            <PriceChart apiUrl={apiUrl} />
          </div>
          <div className="metrics-section">
            <PerformanceMetrics apiUrl={apiUrl} />
          </div>
        </div>

        {/* Trade History */}
        <TradeHistory apiUrl={apiUrl} />
      </div>
    </div>
  );
};

export default Dashboard;
