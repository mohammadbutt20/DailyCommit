"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { shouldRetry } from "@/lib/retry";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: shouldRetry } } }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
