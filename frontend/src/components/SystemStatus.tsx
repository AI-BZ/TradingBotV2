import React from 'react';
import { CheckCircle, AlertCircle, XCircle } from 'lucide-react';

interface HealthData {
  status: string;
  components: {
    api: string;
    websocket: string;
  };
  timestamp: string;
}

interface SystemStatusProps {
  healthData?: HealthData;
}

const SystemStatus: React.FC<SystemStatusProps> = ({ healthData }) => {
  if (!healthData) {
    return (
      <div className="system-status">
        <AlertCircle size={20} className="status-icon warning" />
        <span>Connecting...</span>
      </div>
    );
  }

  const isHealthy = healthData.status === 'healthy';
  const StatusIcon = isHealthy ? CheckCircle : XCircle;

  return (
    <div className="system-status">
      <StatusIcon
        size={20}
        className={`status-icon ${isHealthy ? 'healthy' : 'error'}`}
      />
      <div className="status-info">
        <span className="status-label">System Status</span>
        <span className={`status-value ${isHealthy ? 'healthy' : 'error'}`}>
          {healthData.status.toUpperCase()}
        </span>
      </div>
      <div className="status-details">
        <span>API: {healthData.components.api}</span>
        <span>WS: {healthData.components.websocket}</span>
      </div>
    </div>
  );
};

export default SystemStatus;
