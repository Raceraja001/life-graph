"use client";
import { ClipboardList, CheckCircle, XCircle, Clock, Loader2 } from "lucide-react";
import { useTasks } from "@/lib/hooks";

const COLUMNS = [
  { key: "queued", label: "Queued", icon: Clock, color: "text-zinc-400" },
  { key: "running", label: "Running", icon: Loader2, color: "text-blue-500" },
  { key: "verifying", label: "Verifying", icon: ClipboardList, color: "text-amber-500" },
  { key: "landed", label: "Landed", icon: CheckCircle, color: "text-emerald-500" },
];

export default function TasksPage() {
  const tasks = useTasks({ limit: "100" });
  const grouped = COLUMNS.map(col => ({
    ...col,
    tasks: (tasks.data ?? []).filter((t: any) => t.status === col.key),
  }));

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Tasks</h2>
        <p className="text-sm text-zinc-500">Agent task board — monitor dispatch and verification</p>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {grouped.map(col => (
          <div key={col.key} className="bg-white border border-zinc-200 rounded-xl p-4 min-h-[350px]">
            <div className="flex items-center gap-2 mb-4">
              <col.icon className={`w-4 h-4 ${col.color}`} />
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">{col.label}</h3>
              <span className="text-[10px] px-1.5 py-0.5 bg-zinc-100 text-zinc-400 rounded-full ml-auto">{col.tasks.length}</span>
            </div>
            {col.tasks.length > 0 ? (
              <div className="space-y-2">
                {col.tasks.map((t: any) => (
                  <div key={t.id} className="p-3 bg-zinc-50 rounded-lg border border-zinc-100 hover:border-zinc-200 transition-colors">
                    <p className="text-sm text-zinc-700 font-medium line-clamp-2">{t.description || t.intent || t.id}</p>
                    <p className="text-xs text-zinc-400 mt-1">{t.persona || "system"}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-400 text-center mt-8">No tasks</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
