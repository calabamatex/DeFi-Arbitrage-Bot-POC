"use client";

import { useEffect, useState } from "react";
import { api, BotConfig } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

export default function ConfigPage() {
  const [config, setConfig] = useState<BotConfig | null>(null);

  useEffect(() => {
    api.config.get().then(setConfig).catch(() => {});
  }, []);

  if (!config) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Configuration</h1>
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  const entries = [
    ["Execution Mode", config.execution_mode],
    ["Dry Run", config.dry_run ? "Yes" : "No"],
    ["Min Profit (USD)", `$${config.min_profit_usd}`],
    ["Max Gas Price (Gwei)", config.max_gas_price_gwei],
    ["Scan Interval (s)", config.scan_interval_seconds],
    ["Max Flash Loan (USD)", `$${config.max_flash_loan_amount_usd}`],
    ["Slippage Tolerance (bps)", config.slippage_tolerance_bps],
    ["Daily Loss Limit (USD)", `$${config.daily_loss_limit_usd}`],
    ["Max Consecutive Losses", config.max_consecutive_losses],
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Configuration</h1>
        <span className="text-gray-500 text-sm">Read-only</span>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left">Parameter</th>
              <th className="px-4 py-3 text-left">Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {entries.map(([key, val]) => (
              <tr key={key as string}>
                <td className="px-4 py-3 text-gray-300">{key as string}</td>
                <td className="px-4 py-3 font-mono">{String(val)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-lg font-semibold mt-6">Active Chains</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(config.chains).map(([name, chain]) => (
          <div
            key={name}
            className="bg-gray-800 rounded-xl border border-gray-700 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium">{name}</h3>
              <StatusBadge
                status={config.active_chains.includes(name) ? "active" : "inactive"}
              />
            </div>
            <div className="text-sm text-gray-400 space-y-1">
              <p>Chain ID: {chain.chain_id}</p>
              <p>Native Token: {chain.native_token}</p>
              <p>RPC: {chain.rpc_url}</p>
              <p>Testnet: {chain.is_testnet ? "Yes" : "No"}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
