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
        <h2 className="text-lg font-semibold text-ink">Activity</h2>
        <p className="text-sm text-ink-mid">System events and notifications</p>
      </div>

      {events.isError ? (
        <div className="bg-danger-soft border border-danger/30 rounded-xl p-5 text-sm text-danger">
          Cannot connect to API — is the backend running?
        </div>
      ) : allItems.length > 0 ? (
        <div className="bg-surface border border-line rounded-xl divide-y divide-line">
          {allItems.map((item: any, i: number) => (
            <div key={item.id || i} className="flex items-start gap-4 px-5 py-4 hover:bg-surface-2/50 transition-colors">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                item.kind === "notification" ? "bg-info-soft" : "bg-surface-3"
              }`}>
                <Zap className={`w-4 h-4 ${item.kind === "notification" ? "text-info" : "text-ink-mid"}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-ink">{item.title || item.summary || item.message || item.content || item.id}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    item.kind === "notification" ? "bg-info-soft text-info" : "bg-surface-3 text-ink-mid"
                  }`}>
                    {item.kind === "notification" ? "notification" : item.watcher_name || "event"}
                  </span>
                  <span className="text-xs text-ink-low">
                    {new Date(item.ts).toLocaleString()}
                  </span>
                  {item.severity && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      item.severity === "critical" ? "bg-danger-soft text-danger" :
                      item.severity === "warning" ? "bg-warning-soft text-warning" :
                      "bg-surface-3 text-ink-low"
                    }`}>{item.severity}</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-surface border border-line rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
            <Activity className="w-6 h-6 text-accent" />
          </div>
          <p className="text-sm text-ink-mid">No activity yet. Events will appear here as the system processes data.</p>
        </div>
      )}
    </div>
  );
}
