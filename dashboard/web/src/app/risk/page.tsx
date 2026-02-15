"use client";

import { useEffect, useState } from "react";
import MetricCard from "@/components/MetricCard";
import StatusBadge from "@/components/StatusBadge";
import { api, RiskStatus } from "@/lib/api";

export default function RiskPage() {
  const [risk, setRisk] = useState<RiskStatus | null>(null);

  useEffect(() => {
    const load = () => api.risk.status().then(setRisk).catch(() => {});
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!risk) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Risk Manager</h1>
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  if (risk.error) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Risk Manager</h1>
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300">
          {risk.error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Risk Manager</h1>
        <StatusBadge
          status={risk.circuit_breaker_active ? "active" : "healthy"}
          size="md"
        />
      </div>

      {risk.circuit_breaker_active && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300">
          Circuit breaker is ACTIVE. Trading is paused due to consecutive losses.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Circuit Breaker"
          value={risk.circuit_breaker_active ? "ACTIVE" : "OK"}
          color={risk.circuit_breaker_active ? "red" : "green"}
        />
        <MetricCard
          label="Consecutive Losses"
          value={risk.consecutive_losses}
          color={risk.consecutive_losses >= 3 ? "red" : "green"}
        />
        <MetricCard
          label="Daily P&L"
          value={`$${risk.daily_pnl_usd.toFixed(2)}`}
          color={risk.daily_pnl_usd >= 0 ? "green" : "red"}
        />
        <MetricCard
          label="Success Rate"
          value={`${risk.success_rate.toFixed(1)}%`}
          color={risk.success_rate >= 50 ? "green" : "yellow"}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <MetricCard label="Total Trades" value={risk.total_trades} color="blue" />
        <MetricCard label="Wins" value={risk.successful_trades} color="green" />
        <MetricCard label="Losses" value={risk.failed_trades} color="red" />
      </div>
    </div>
  );
}
