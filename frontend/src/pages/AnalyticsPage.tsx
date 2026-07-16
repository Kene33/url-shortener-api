import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusMessage } from "@/components/ui/status-message";
import { useAnalyticsQuery } from "@/features/analytics/api";
import type { AnalyticsPeriod } from "@/api/types";
import { useState } from "react";

const periods: AnalyticsPeriod[] = ["24h", "7d", "30d", "90d"];

export function AnalyticsPage() {
  const [period, setPeriod] = useState<AnalyticsPeriod>("30d");
  const analytics = useAnalyticsQuery(period);

  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="m-0 text-lg font-semibold">Аналитика</h1>
          <p className="m-0 text-sm text-subtle">Privacy-safe метрики, график и топ коротких ссылок.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {periods.map((value) => (
            <button
              key={value}
              type="button"
              className={`pill ${value === period ? "border-accent text-accent" : ""}`}
              onClick={() => setPeriod(value)}
            >
              {value}
            </button>
          ))}
        </div>
      </Card>
      {analytics.isLoading ? <StatusMessage type="loading" message="Собираем метрики…" /> : null}
      {analytics.error ? <StatusMessage type="error" message={analytics.error.message} /> : null}
      {analytics.data ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {analytics.data.metrics.map((metric) => (
              <Card key={metric.key} className="space-y-2">
                <p className="m-0 text-xs text-subtle">{metric.label}</p>
                <p className="m-0 text-2xl font-semibold">{metric.value}</p>
                <p className="m-0 text-xs text-success">{metric.change ? `${metric.change}%` : "No change"}</p>
              </Card>
            ))}
          </div>
          <Card className="h-[340px]">
            {!analytics.data.chart.length ? (
              <EmptyState title="Нет данных" description="Появятся после первых переходов." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={analytics.data.chart}>
                  <XAxis dataKey="label" stroke="currentColor" tick={{ fill: "currentColor", fontSize: 12 }} />
                  <YAxis stroke="currentColor" tick={{ fill: "currentColor", fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="visits" stroke="rgb(var(--accent))" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
          <Card className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="m-0 font-semibold">Топ ссылок</p>
            </div>
            {analytics.data.top_links.map((link) => (
              <div key={link.shortcode} className="flex items-center justify-between border-t border-border pt-3 first:border-t-0 first:pt-0">
                <div>
                  <p className="m-0 font-medium text-accent">{link.shortcode}</p>
                  <p className="m-0 text-xs text-subtle">{link.label ?? "Без label"}</p>
                </div>
                <p className="m-0 text-sm text-subtle">{link.access_count}</p>
              </div>
            ))}
          </Card>
        </>
      ) : null}
    </div>
  );
}
