"use client";
import { BookOpen, ChevronRight } from "lucide-react";
import { usePreferences } from "@/lib/hooks";

export default function DecisionsPage() {
  const preferences = usePreferences({ limit: "50" });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Preferences</h2>
        <p className="text-sm text-ink-mid">Learned preferences and decisions</p>
      </div>

      {preferences.isError ? (
        <div className="bg-danger-soft border border-danger/30 rounded-xl p-5 text-sm text-danger">
          Cannot load preferences — check API connection
        </div>
      ) : preferences.data && preferences.data.length > 0 ? (
        <div className="space-y-3">
          {preferences.data.map((p: any) => (
            <div key={p.id} className="bg-surface border border-line rounded-xl p-5 hover:shadow-md hover:border-line-strong transition-all group">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-ink">{p.key || p.domain || p.id}</h3>
                    {p.confidence && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-soft text-accent-text font-medium">
                        {(p.confidence * 100).toFixed(0)}% confident
                      </span>
                    )}
                  </div>
                  {p.value && <p className="text-sm text-ink-mid line-clamp-2 mb-2">{typeof p.value === 'string' ? p.value : JSON.stringify(p.value)}</p>}
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-ink-low">{new Date(p.created_at).toLocaleDateString()}</span>
                    {p.domain && <span className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-mid rounded">{p.domain}</span>}
                    {p.source && <span className="text-[10px] px-1.5 py-0.5 bg-info-soft text-info rounded">{p.source}</span>}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-ink-low group-hover:text-ink-mid shrink-0 mt-1 transition-colors" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-surface border border-line rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
            <BookOpen className="w-6 h-6 text-accent" />
          </div>
          <p className="text-sm text-ink-mid">No preferences learned yet. Interact with the system to build your preference profile.</p>
        </div>
      )}
    </div>
  );
}
