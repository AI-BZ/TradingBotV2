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
        {/* Top Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon blue">
              <TrendingUp size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Win Rate</p>
              <p className="stat-value">58.3%</p>
              <p className="stat-change positive">+2.3% vs last week</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon green">
              <DollarSign size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Total P&L</p>
              <p className="stat-value">+$1,520</p>
              <p className="stat-change positive">+15.2%</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon purple">
              <Activity size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Total Trades</p>
              <p className="stat-value">247</p>
              <p className="stat-change neutral">Last 30 days</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon orange">
              <AlertCircle size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-label">Max Drawdown</p>
              <p className="stat-value">-18.4%</p>
              <p className="stat-change neutral">Within limits</p>
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
