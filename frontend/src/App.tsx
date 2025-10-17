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
  // Use the same protocol and domain as the current page
  const apiUrl = `${window.location.protocol}//${window.location.host}`;

  return (
    <QueryClientProvider client={queryClient}>
      <div className="App">
        <Dashboard apiUrl={apiUrl} />
      </div>
    </QueryClientProvider>
  );
}

export default App;
