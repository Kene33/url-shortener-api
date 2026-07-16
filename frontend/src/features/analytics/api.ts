import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { AnalyticsPeriod, AnalyticsResponse } from "@/api/types";

export const analyticsKeys = {
  all: ["analytics"] as const,
  period: (period: AnalyticsPeriod) => ["analytics", period] as const,
};

export function useAnalyticsQuery(period: AnalyticsPeriod) {
  return useQuery<AnalyticsResponse>({
    queryKey: analyticsKeys.period(period),
    queryFn: () => api.getAnalytics(period) as Promise<AnalyticsResponse>,
  });
}
