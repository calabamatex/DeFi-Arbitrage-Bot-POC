"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, Legend,
} from "recharts";
import MetricCard from "@/components/MetricCard";
import { api, PnLDataPoint, PnLSummary } from "@/lib/api";

export default function AnalyticsPage() {
  const [daily, setDaily] = useState<PnLDataPoint[]>([]);
  const [summary, setSummary] = useState<PnLSummary | null>(null);
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");

  useEffect(() => {
    api.pnl.summary().then(setSummary).catch(() => {});
  }, []);

  useEffect(() => {
    const fetcher =
      period === "daily" ? api.pnl.daily(30) :
      period === "weekly" ? api.pnl.weekly(12) :
      api.pnl.monthly(12);

    fetcher.then((d) => setDaily(d.data)).catch(() => {});
  }, [period]);

  // Compute cumulative P&L
  let cumulative = 0;
  const chartData = daily.map((d) => {
    cumulative += d.net_profit_usd;
    return { ...d, cumulative };
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">P&L Analytics</h1>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard
            label="Total Net Profit"
            value={`$${summary.total_net_profit_usd.toFixed(2)}`}
            color={summary.total_net_profit_usd >= 0 ? "green" : "red"}
          />
          <MetricCard
            label="Total Gas Cost"
            value={`$${summary.total_gas_cost_usd.toFixed(2)}`}
            color="yellow"
          />
          <MetricCard label="Win Rate" value={`${summary.win_rate}%`} color="blue" />
          <MetricCard
            label="Best Trade"
            value={`$${summary.best_trade_usd.toFixed(2)}`}
            color="green"
          />
          <MetricCard
            label="Worst Trade"
            value={`$${summary.worst_trade_usd.toFixed(2)}`}
            color="red"
          />
        </div>
      )}

      <div className="flex gap-2">
        {(["daily", "weekly", "monthly"] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1 rounded text-sm ${
              period === p ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-300"
            }`}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
        <h3 className="text-sm text-gray-400 mb-4">Cumulative P&L</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="period" stroke="#9CA3AF" tick={{ fontSize: 11 }} />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151" }}
              labelStyle={{ color: "#9CA3AF" }}
            />
            <Line type="monotone" dataKey="cumulative" stroke="#3B82F6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
        <h3 className="text-sm text-gray-400 mb-4">Profit vs Gas Cost per Period</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="period" stroke="#9CA3AF" tick={{ fontSize: 11 }} />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#1F2937", border: "1px solid #374151" }}
              labelStyle={{ color: "#9CA3AF" }}
            />
            <Legend />
            <Bar dataKey="net_profit_usd" fill="#10B981" name="Net Profit" />
            <Bar dataKey="gas_cost_usd" fill="#F59E0B" name="Gas Cost" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
