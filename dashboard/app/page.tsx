"use client";
import { Brain, Bell, ClipboardList, BookOpen } from "lucide-react";
import { StatsCard } from "@/components/stats-card";
import { useMemories, useTasks, usePreferences, useWatcherEvents } from "@/lib/hooks";

export default function OverviewPage() {
  const memories = useMemories({ limit: "50" });
  const tasks = useTasks({ limit: "50" });
  const preferences = usePreferences({ limit: "50" });
  const events = useWatcherEvents({ limit: "5" });

  const memCount = memories.isLoading ? "—" : (memories.data?.length ?? 0);
  const taskCount = tasks.isLoading ? "—" : (tasks.data?.length ?? 0);
  const prefCount = preferences.isLoading ? "—" : (preferences.data?.length ?? 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatsCard label="Memories" value={memCount} subtitle="Total stored" icon={Brain} />
        <StatsCard label="Tasks" value={taskCount} subtitle="Kernel tasks" icon={ClipboardList} />
        <StatsCard label="Preferences" value={prefCount} subtitle="Learned preferences" icon={BookOpen} />
        <StatsCard label="Events" value={events.isLoading ? "—" : (events.data?.length ?? 0)} subtitle="Recent watcher events" icon={Bell} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent memories */}
        <div className="bg-surface border border-line rounded-xl p-5 min-h-[240px]">
          <h3 className="text-sm font-semibold text-ink mb-4">Recent Memories</h3>
          {memories.isError ? (
            <div className="flex items-center justify-center h-36 text-danger text-sm">
              Cannot connect to API — is the backend running?
            </div>
          ) : memories.data && memories.data.length > 0 ? (
            <div className="space-y-2.5">
              {memories.data.slice(0, 5).map((m: any) => (
                <div key={m.id} className="flex items-start gap-3 py-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent mt-2 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-ink truncate">{m.content}</p>
                    <p className="text-xs text-ink-low mt-0.5">
                      {new Date(m.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-ink-low text-sm">
              No memories yet — type something in the chat bar
            </div>
          )}
        </div>

        {/* Recent watcher events */}
        <div className="bg-surface border border-line rounded-xl p-5 min-h-[240px]">
          <h3 className="text-sm font-semibold text-ink mb-4">Recent Events</h3>
          {events.data && events.data.length > 0 ? (
            <div className="space-y-2.5">
              {events.data.slice(0, 5).map((e: any) => (
                <div key={e.id} className="flex items-start gap-3 py-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-info mt-2 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-ink truncate">{e.title || e.summary || e.id}</p>
                    <p className="text-xs text-ink-low mt-0.5">
                      {e.watcher_name || "system"} · {new Date(e.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-ink-low text-sm">
              No events yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
