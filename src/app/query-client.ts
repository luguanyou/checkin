import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => {
        const status = (error as { status?: number }).status;
        return count < 1 && status !== 401 && status !== 403 && status !== 404;
      },
      staleTime: 30_000,
    },
    mutations: { retry: false },
  },
});
