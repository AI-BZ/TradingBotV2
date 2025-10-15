import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface PriceChartProps {
  apiUrl: string;
}

const PriceChart: React.FC<PriceChartProps> = ({ apiUrl }) => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1h');

  const { data: chartData, isLoading } = useQuery({
    queryKey: ['chart', symbol, interval],
    queryFn: async () => {
      const response = await axios.get(
        `${apiUrl}/api/v1/market/klines/${symbol}?interval=${interval}&limit=100`
      );

      // Transform data for recharts
      return response.data.klines.map((kline: any) => ({
        time: new Date(kline.timestamp).toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        price: parseFloat(kline.close),
        volume: parseFloat(kline.volume),
      }));
    },
  });

  const symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'];
  const intervals = ['1m', '5m', '15m', '1h', '4h', '1d'];

  return (
    <div className="price-chart-container">
      <div className="chart-header">
        <h3>Price Chart</h3>
        <div className="chart-controls">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="chart-select"
          >
            {symbols.map((s) => (
              <option key={s} value={s}>
                {s.replace('USDT', '/USDT')}
              </option>
            ))}
          </select>
          <select
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            className="chart-select"
          >
            {intervals.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="chart-loading">Loading chart data...</div>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="time"
              stroke="#888"
              tick={{ fill: '#888' }}
            />
            <YAxis
              stroke="#888"
              tick={{ fill: '#888' }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1a1a',
                border: '1px solid #333',
                borderRadius: '8px'
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Price (USDT)"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default PriceChart;
