import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type PropsWithChildren, useState } from "react";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@/features/theme/theme-provider";
import { SessionProvider } from "@/features/session/session-provider";

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <SessionProvider>
          <BrowserRouter>{children}</BrowserRouter>
        </SessionProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
