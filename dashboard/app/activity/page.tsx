"use client";
import { Activity, Zap } from "lucide-react";
import { useWatcherEvents, useNotifications } from "@/lib/hooks";

export default function ActivityPage() {
  const events = useWatcherEvents({ limit: "30" });
  const notifications = useNotifications({ limit: "20" });

  const allItems = [
    ...(events.data ?? []).map((e: any) => ({ ...e, kind: "event", ts: e.created_at })),
    ...(notifications.data ?? []).map((n: any) => ({ ...n, kind: "notification", ts: n.created_at })),
  ].sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Activity</h2>
        <p className="text-sm text-zinc-500">System events and notifications</p>
      </div>

      {events.isError ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-600">
          Cannot connect to API — is the backend running?
        </div>
      ) : allItems.length > 0 ? (
        <div className="bg-white border border-zinc-200 rounded-xl divide-y divide-zinc-100">
          {allItems.map((item: any, i: number) => (
            <div key={item.id || i} className="flex items-start gap-4 px-5 py-4 hover:bg-zinc-50/50 transition-colors">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                item.kind === "notification" ? "bg-blue-50" : "bg-zinc-100"
              }`}>
                <Zap className={`w-4 h-4 ${item.kind === "notification" ? "text-blue-500" : "text-zinc-500"}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-700">{item.title || item.summary || item.message || item.content || item.id}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    item.kind === "notification" ? "bg-blue-100 text-blue-700" : "bg-zinc-100 text-zinc-500"
                  }`}>
                    {item.kind === "notification" ? "notification" : item.watcher_name || "event"}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {new Date(item.ts).toLocaleString()}
                  </span>
                  {item.severity && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      item.severity === "critical" ? "bg-red-50 text-red-600" :
                      item.severity === "warning" ? "bg-amber-50 text-amber-600" :
                      "bg-zinc-100 text-zinc-400"
                    }`}>{item.severity}</span>
                  )}
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
