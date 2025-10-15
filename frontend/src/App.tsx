import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './components/Dashboard';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5000, // Refetch every 5 seconds
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const [apiUrl] = useState('http://167.179.108.246');

  return (
    <QueryClientProvider client={queryClient}>
      <div className="App">
        <Dashboard apiUrl={apiUrl} />
      </div>
    </QueryClientProvider>
  );
}

export default App;
