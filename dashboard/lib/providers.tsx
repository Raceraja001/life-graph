"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000,       // 5 min — data is "fresh" for 5 min, no refetch
            gcTime: 10 * 60_000,         // 10 min — keep cache alive
            retry: false,                // no retries on failure
            refetchOnMount: false,       // don't refetch when component re-mounts
            refetchOnWindowFocus: false,  // don't refetch on tab focus
            refetchOnReconnect: false,    // don't refetch on network reconnect
          },
        },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
