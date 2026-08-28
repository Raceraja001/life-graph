"use client";
import { ClipboardList, CheckCircle, Clock, Loader2 } from "lucide-react";
import { useTasks } from "@/lib/hooks";

const COLUMNS = [
  { key: "queued", label: "Queued", icon: Clock, color: "text-ink-low" },
  { key: "running", label: "Running", icon: Loader2, color: "text-info" },
  { key: "verifying", label: "Verifying", icon: ClipboardList, color: "text-warning" },
  { key: "landed", label: "Landed", icon: CheckCircle, color: "text-accent" },
];

export default function TasksPage() {
  const tasks = useTasks({ limit: "100" });
  const grouped = COLUMNS.map(col => ({
    ...col,
    tasks: (tasks.data ?? []).filter((t: any) => t.status === col.key || (col.key === "landed" && ["completed", "done"].includes(t.status))),
  }));

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Tasks</h2>
        <p className="text-sm text-ink-mid">Agent task board — monitor dispatch and verification</p>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {grouped.map(col => (
          <div key={col.key} className="bg-surface border border-line rounded-xl p-4 min-h-[350px]">
            <div className="flex items-center gap-2 mb-4">
              <col.icon className={`w-4 h-4 ${col.color}`} />
              <h3 className="text-xs font-semibold text-ink-mid uppercase tracking-wider">{col.label}</h3>
              <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-low rounded-full ml-auto">{col.tasks.length}</span>
            </div>
            {col.tasks.length > 0 ? (
              <div className="space-y-2">
                {col.tasks.map((t: any) => (
                  <div key={t.id} className="p-3 bg-surface-2 rounded-lg border border-line hover:border-line transition-colors">
                    <p className="text-sm text-ink font-medium line-clamp-2">{t.description || t.intent || t.task_name || t.id}</p>
                    <p className="text-xs text-ink-low mt-1">{t.persona || t.agent_name || "system"}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-ink-low text-center mt-8">No tasks</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
