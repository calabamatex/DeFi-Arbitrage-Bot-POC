"use client";

import { useEffect, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { api, SystemHealth } from "@/lib/api";

export default function HealthPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api.system
        .health()
        .then((d) => { setHealth(d); setError(null); })
        .catch(() => setError("Dashboard API unreachable"));
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">System Health</h1>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300">
          {error}
        </div>
      )}

      {health && (
        <>
          <div className="flex items-center gap-3">
            <span className="text-gray-400">Overall:</span>
            <StatusBadge status={health.status} size="md" />
          </div>

          <div className="space-y-4">
            {Object.entries(health.checks).map(([name, check]) => (
              <div
                key={name}
                className="bg-gray-800 rounded-xl border border-gray-700 p-4 flex items-center justify-between"
              >
                <div>
                  <h3 className="font-medium capitalize">{name}</h3>
                  {check.error && (
                    <p className="text-red-400 text-sm mt-1">{check.error}</p>
                  )}
                </div>
                <StatusBadge status={check.status} />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
