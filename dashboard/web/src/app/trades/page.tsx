"use client";

import { useEffect, useState } from "react";
import { api, TradeItem } from "@/lib/api";

export default function TradesPage() {
  const [trades, setTrades] = useState<TradeItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    api.trades.list(page).then((data) => {
      setTrades(data.trades);
      setTotalPages(data.pages);
      setTotal(data.total);
    }).catch(() => {});
  }, [page]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <span className="text-gray-400 text-sm">{total} total trades</span>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left">Time</th>
              <th className="px-4 py-3 text-left">Pair</th>
              <th className="px-4 py-3 text-left">DEX Path</th>
              <th className="px-4 py-3 text-right">Profit</th>
              <th className="px-4 py-3 text-right">Gas</th>
              <th className="px-4 py-3 text-center">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {trades.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No trades recorded yet
                </td>
              </tr>
            )}
            {trades.map((t) => (
              <tr key={t.id} className="hover:bg-gray-750">
                <td className="px-4 py-3 text-gray-300">
                  {t.executed_at ? new Date(t.executed_at).toLocaleString() : "-"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {t.token_in?.slice(0, 6)}.../{t.token_out?.slice(0, 6)}...
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">
                  {t.dex_path?.join(" -> ") || "-"}
                </td>
                <td className={`px-4 py-3 text-right font-mono ${
                  t.net_profit_usd && t.net_profit_usd > 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {t.net_profit_usd != null ? `$${t.net_profit_usd.toFixed(2)}` : "-"}
                </td>
                <td className="px-4 py-3 text-right font-mono text-gray-400">
                  {t.gas_cost_usd != null ? `$${t.gas_cost_usd.toFixed(2)}` : "-"}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`inline-block w-2 h-2 rounded-full ${
                    t.success ? "bg-green-400" : "bg-red-400"
                  }`} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 bg-gray-800 rounded disabled:opacity-50"
          >
            Prev
          </button>
          <span className="text-gray-400 text-sm">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 bg-gray-800 rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
