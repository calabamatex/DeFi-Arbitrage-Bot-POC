"use client";

import { useEffect, useState } from "react";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { api, MetricsData } from "@/lib/api";

export default function OverviewPage() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.metrics.current();
        setMetrics(data);
        setError(null);
      } catch (e) {
        setError("Failed to connect to bot API");
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300">
          {error}. Make sure the bot and dashboard API are running.
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  const uptimeHrs = (metrics.uptime_seconds / 3600).toFixed(1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="flex items-center gap-3">
          <StatusBadge status={metrics.running ? "running" : "stopped"} size="md" />
          {metrics.dry_run && <StatusBadge status="dry-run" size="md" />}
          {metrics.circuit_breaker_active && <StatusBadge status="active" size="md" />}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Net Profit"
          value={`$${metrics.net_profit_usd.toFixed(2)}`}
          color={metrics.net_profit_usd >= 0 ? "green" : "red"}
          subtitle="All time"
        />
        <MetricCard
          label="Daily P&L"
          value={`$${metrics.daily_pnl_usd.toFixed(2)}`}
          color={metrics.daily_pnl_usd >= 0 ? "green" : "red"}
          subtitle="Today"
        />
        <MetricCard
          label="Win Rate"
          value={`${metrics.success_rate.toFixed(1)}%`}
          color={metrics.success_rate >= 50 ? "green" : "yellow"}
          subtitle={`${metrics.successful_trades}W / ${metrics.failed_trades}L`}
        />
        <MetricCard
          label="Trades"
          value={metrics.total_trades}
          color="blue"
          subtitle={`from ${metrics.opportunities} opps`}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Scans" value={metrics.scans} color="gray" />
        <MetricCard label="Opportunities" value={metrics.opportunities} color="blue" />
        <MetricCard label="Uptime" value={`${uptimeHrs}h`} color="gray" />
        <MetricCard
          label="Memory"
          value={`${metrics.memory_mb?.toFixed(0) || "?"}MB`}
          color={metrics.memory_mb > 500 ? "red" : "gray"}
        />
      </div>
    </div>
  );
}
