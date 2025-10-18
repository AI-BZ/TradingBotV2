import React from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import StrategyPanel from './StrategyPanel';
import SystemStatus from './SystemStatus';
import { Activity } from 'lucide-react';

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

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-content">
          <div className="logo">
            <Activity size={32} />
            <h1>TradingBot V2 - 3 Strategy Comparison</h1>
          </div>
          <SystemStatus healthData={healthData} />
        </div>
      </header>

      {/* Main Content - 3 Strategy Panels */}
      <div className="dashboard-content">
        <div className="strategies-container">
          <StrategyPanel
            apiUrl={apiUrl}
            strategyId="a"
            strategyName="Strategy A - Conservative"
            strategyDescription="Lower risk, steady gains (Volatility ≥0.04%, Cooldown 300s)"
            colorScheme="blue"
          />

          <StrategyPanel
            apiUrl={apiUrl}
            strategyId="b"
            strategyName="Strategy B - Selective (1-SET)"
            strategyDescription="Main strategy with 1-SET management (Volatility ≥0.08%, Cooldown 300s)"
            colorScheme="green"
          />

          <StrategyPanel
            apiUrl={apiUrl}
            strategyId="c"
            strategyName="Strategy C - Aggressive"
            strategyDescription="Higher frequency, higher risk (Volatility ≥0.02%, Cooldown 180s)"
            colorScheme="orange"
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
