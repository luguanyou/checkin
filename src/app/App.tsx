import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AppRoutes } from './router';
import { AuthProvider } from './auth';
import { queryClient } from './query-client';
import { ToastProvider } from '../components/ToastProvider';

export function App() {
  return <QueryClientProvider client={queryClient}><BrowserRouter><ToastProvider><AuthProvider><AppRoutes /></AuthProvider></ToastProvider></BrowserRouter></QueryClientProvider>;
}
