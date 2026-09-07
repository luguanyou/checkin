import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AppRoutes } from './router';
import { AuthProvider } from './auth';
import { queryClient } from './query-client';
import { ToastProvider } from '../components/ToastProvider';

// 子路径部署：路由 basename 跟随 Vite base（BASE_URL 以 / 结尾，去掉尾斜杠）。
const routerBasename = import.meta.env.BASE_URL.replace(/\/+$/, '') || '/';

export function App() {
  return <QueryClientProvider client={queryClient}><BrowserRouter basename={routerBasename}><ToastProvider><AuthProvider><AppRoutes /></AuthProvider></ToastProvider></BrowserRouter></QueryClientProvider>;
}
