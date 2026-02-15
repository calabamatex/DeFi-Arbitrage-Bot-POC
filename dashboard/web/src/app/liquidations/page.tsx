"use client";

import { useEffect, useState } from "react";
import { api, LiquidationItem } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

export default function LiquidationsPage() {
  const [items, setItems] = useState<LiquidationItem[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    api.liquidations.list().then((d) => {
      setItems(d.liquidations);
      setTotal(d.total);
    }).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Liquidations</h1>
        <span className="text-gray-400 text-sm">{total} total</span>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left">Time</th>
              <th className="px-4 py-3 text-left">User</th>
              <th className="px-4 py-3 text-right">Health Factor</th>
              <th className="px-4 py-3 text-left">Debt Asset</th>
              <th className="px-4 py-3 text-right">Profit</th>
              <th className="px-4 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No liquidation opportunities recorded yet
                </td>
              </tr>
            )}
            {items.map((liq) => (
              <tr key={liq.id} className="hover:bg-gray-750">
                <td className="px-4 py-3 text-gray-300">
                  {liq.detected_at ? new Date(liq.detected_at).toLocaleString() : "-"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {liq.user_address.slice(0, 8)}...{liq.user_address.slice(-6)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-yellow-400">
                  {(Number(liq.health_factor) / 1e18).toFixed(4)}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {liq.debt_asset.slice(0, 8)}...
                </td>
                <td className={`px-4 py-3 text-right font-mono ${
                  liq.net_profit_usd && liq.net_profit_usd > 0 ? "text-green-400" : "text-gray-400"
                }`}>
                  {liq.net_profit_usd != null ? `$${liq.net_profit_usd.toFixed(2)}` : "-"}
                </td>
                <td className="px-4 py-3 text-center">
                  <StatusBadge status={liq.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
