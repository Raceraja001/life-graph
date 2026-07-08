"use client";
import { Bot, DollarSign, CheckCircle, XCircle } from "lucide-react";
import { useDrivers, useDriverStats } from "@/lib/hooks";
import { StatsCard } from "@/components/stats-card";

export default function DriversPage() {
  const drivers = useDrivers();
  const stats = useDriverStats();

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Drivers</h2>
        <p className="text-sm text-zinc-500">Agent driver performance — verified tasks per ₹</p>
      </div>

      {stats.data && Object.keys(stats.data).length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(stats.data).map(([name, s]: [string, any]) => (
            <div key={name} className="bg-white border border-zinc-200 rounded-xl p-5 hover:shadow-md transition-all">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-emerald-600" />
                </div>
                <h3 className="text-sm font-semibold text-zinc-800">{name}</h3>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><span className="text-xs text-zinc-400">Dispatched</span><p className="text-lg font-bold text-zinc-900">{s.dispatched ?? 0}</p></div>
                <div><span className="text-xs text-zinc-400">Landed</span><p className="text-lg font-bold text-emerald-600">{s.landed ?? 0}</p></div>
                <div><span className="text-xs text-zinc-400">Failed</span><p className="text-lg font-bold text-red-500">{s.failed ?? 0}</p></div>
                <div><span className="text-xs text-zinc-400">₹/task</span><p className="text-lg font-bold text-zinc-900">{s.cost_per_task?.toFixed(2) ?? "—"}</p></div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
            <Bot className="w-6 h-6 text-emerald-500" />
          </div>
          <p className="text-sm text-zinc-500">No driver stats yet. Dispatch agent tasks to see performance data.</p>
        </div>
      )}
    </div>
  );
}
