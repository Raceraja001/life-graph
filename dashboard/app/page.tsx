"use client";
import { Brain, Scale, BarChart3, Activity } from "lucide-react";
import { StatsCard } from "@/components/stats-card";
import { useMemories, useDecisions, useCalibrationCurve, useCaptures } from "@/lib/hooks";

export default function OverviewPage() {
  const memories = useMemories({ limit: "1" });
  const decisions = useDecisions({ limit: "5" });
  const calibration = useCalibrationCurve();
  const captures = useCaptures({ limit: "5" });

  const memCount = memories.data?.length !== undefined ? (memories.data?.length > 0 ? "1+" : "0") : "—";
  const decCount = decisions.data?.length ?? "—";
  const brier = calibration.data?.brier_score != null ? calibration.data.brier_score.toFixed(3) : "—";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatsCard label="Memories" value={memCount} subtitle="Total stored" icon={Brain} />
        <StatsCard label="Decisions" value={decCount} subtitle="Active decisions" icon={Scale} />
        <StatsCard label="Brier Score" value={brier} subtitle="Lower is better (0 = perfect)" icon={BarChart3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Calibration preview */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 min-h-[240px]">
          <h3 className="text-sm font-semibold text-zinc-700 mb-4">Calibration Preview</h3>
          {calibration.data?.buckets && calibration.data.buckets.length > 0 ? (
            <div className="space-y-2">
              {calibration.data.buckets.map((b: any) => (
                <div key={b.range_label} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400 w-20 font-mono">{b.range_label}</span>
                  <div className="flex-1 h-6 bg-zinc-100 rounded-md overflow-hidden relative">
                    <div className="absolute inset-y-0 left-0 bg-emerald-200 rounded-md" style={{ width: `${(b.avg_confidence || 0) * 100}%` }} />
                    <div className="absolute inset-y-0 left-0 bg-emerald-500 rounded-md opacity-60" style={{ width: `${(b.hit_rate || 0) * 100}%` }} />
                  </div>
                  <span className="text-xs text-zinc-500 w-8 text-right">{b.count}</span>
                </div>
              ))}
              <div className="flex items-center gap-4 mt-3 text-xs text-zinc-400">
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-emerald-200" /> Predicted</div>
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-emerald-500 opacity-60" /> Actual</div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-zinc-400 text-sm">
              Make predictions to see your calibration curve
            </div>
          )}
        </div>

        {/* Recent captures */}
        <div className="bg-white border border-zinc-200 rounded-xl p-5 min-h-[240px]">
          <h3 className="text-sm font-semibold text-zinc-700 mb-4">Recent Activity</h3>
          {captures.data && captures.data.length > 0 ? (
            <div className="space-y-2.5">
              {captures.data.slice(0, 5).map((c: any) => (
                <div key={c.id} className="flex items-start gap-3 py-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-2 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm text-zinc-700 truncate">{c.content}</p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      {c.surface} · {new Date(c.occurred_at).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-zinc-400 text-sm">
              Start capturing to see activity
            </div>
          )}
        </div>
      </div>

      {/* Recent decisions */}
      {decisions.data && decisions.data.length > 0 && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-700 mb-4">Recent Decisions</h3>
          <div className="space-y-3">
            {decisions.data.map((d: any) => (
              <div key={d.id} className="flex items-center justify-between py-2 border-b border-zinc-100 last:border-0">
                <div>
                  <p className="text-sm font-medium text-zinc-800">{d.title}</p>
                  <p className="text-xs text-zinc-400 mt-0.5">{new Date(d.created_at).toLocaleDateString()}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                  d.status === "decided" ? "bg-emerald-50 text-emerald-700" :
                  d.status === "candidate" ? "bg-amber-50 text-amber-700" :
                  d.status === "reviewed" ? "bg-blue-50 text-blue-700" :
                  "bg-zinc-100 text-zinc-500"
                }`}>{d.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
