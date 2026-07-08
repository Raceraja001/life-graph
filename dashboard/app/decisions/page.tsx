"use client";
import { BookOpen, ChevronRight } from "lucide-react";
import { usePreferences } from "@/lib/hooks";

export default function DecisionsPage() {
  const preferences = usePreferences({ limit: "50" });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Preferences</h2>
        <p className="text-sm text-zinc-500">Learned preferences and decisions</p>
      </div>

      {preferences.isError ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-600">
          Cannot load preferences — check API connection
        </div>
      ) : preferences.data && preferences.data.length > 0 ? (
        <div className="space-y-3">
          {preferences.data.map((p: any) => (
            <div key={p.id} className="bg-white border border-zinc-200 rounded-xl p-5 hover:shadow-md hover:border-zinc-300 transition-all group">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-zinc-800">{p.key || p.domain || p.id}</h3>
                    {p.confidence && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">
                        {(p.confidence * 100).toFixed(0)}% confident
                      </span>
                    )}
                  </div>
                  {p.value && <p className="text-sm text-zinc-500 line-clamp-2 mb-2">{typeof p.value === 'string' ? p.value : JSON.stringify(p.value)}</p>}
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-zinc-400">{new Date(p.created_at).toLocaleDateString()}</span>
                    {p.domain && <span className="text-[10px] px-1.5 py-0.5 bg-zinc-100 text-zinc-500 rounded">{p.domain}</span>}
                    {p.source && <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">{p.source}</span>}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-zinc-300 group-hover:text-zinc-500 shrink-0 mt-1 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
            <BookOpen className="w-6 h-6 text-emerald-500" />
          </div>
          <p className="text-sm text-zinc-500">No preferences learned yet. Interact with the system to build your preference profile.</p>
        </div>
      )}
    </div>
  );
}
