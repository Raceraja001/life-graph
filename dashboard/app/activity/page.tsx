"use client";
import { Activity, Zap } from "lucide-react";
import { useCaptures } from "@/lib/hooks";

const SURFACE_COLORS: Record<string, string> = {
  dashboard: "bg-emerald-100 text-emerald-700",
  orchestrator: "bg-blue-100 text-blue-700",
  mcp: "bg-purple-100 text-purple-700",
  cli: "bg-zinc-100 text-zinc-700",
  voice: "bg-amber-100 text-amber-700",
  watcher: "bg-red-100 text-red-700",
  git: "bg-orange-100 text-orange-700",
};

export default function ActivityPage() {
  const captures = useCaptures({ limit: "30" });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Activity</h2>
        <p className="text-sm text-zinc-500">Live system event feed</p>
      </div>

      {captures.data && captures.data.length > 0 ? (
        <div className="bg-white border border-zinc-200 rounded-xl divide-y divide-zinc-100">
          {captures.data.map((c: any) => (
            <div key={c.id} className="flex items-start gap-4 px-5 py-4 hover:bg-zinc-50/50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center shrink-0 mt-0.5">
                <Zap className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-700">{c.content}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${SURFACE_COLORS[c.surface] || "bg-zinc-100 text-zinc-500"}`}>
                    {c.surface}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {new Date(c.occurred_at).toLocaleString()}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    c.status === "processed" ? "bg-emerald-50 text-emerald-600" :
                    c.status === "duplicate" ? "bg-zinc-100 text-zinc-400" :
                    "bg-blue-50 text-blue-600"
                  }`}>{c.status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
            <Activity className="w-6 h-6 text-emerald-500" />
          </div>
          <p className="text-sm text-zinc-500">No activity yet. Events will appear here as the system processes data.</p>
        </div>
      )}
    </div>
  );
}
