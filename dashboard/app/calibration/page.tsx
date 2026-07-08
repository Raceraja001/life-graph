"use client";
import { BarChart3, TrendingUp, AlertTriangle } from "lucide-react";
import { StatsCard } from "@/components/stats-card";
import { useCalibrationCurve, usePredictions } from "@/lib/hooks";

export default function CalibrationPage() {
  const calibration = useCalibrationCurve();
  const predictions = usePredictions({ limit: "100" });

  const resolved = calibration.data?.resolved_count ?? 0;
  const brier = calibration.data?.brier_score;
  const multiplier = calibration.data?.estimate_multiplier;
  const bias = calibration.data?.bias_findings ?? [];
  const buckets = calibration.data?.buckets ?? [];
  const sufficient = resolved >= 20;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Calibration</h2>
        <p className="text-sm text-zinc-500">How accurate are your predictions?</p>
      </div>

      {sufficient ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatsCard label="Brier Score" value={brier?.toFixed(3) ?? "—"} subtitle="Lower = better (0 perfect)" icon={BarChart3} />
            <StatsCard label="Resolved" value={resolved} subtitle="Predictions resolved" icon={TrendingUp} />
            <StatsCard label="Multiplier" value={multiplier?.toFixed(2) ?? "—"} subtitle=">1 = underconfident" icon={TrendingUp} />
            <StatsCard label="Biases" value={bias.length} subtitle="Detected patterns" icon={AlertTriangle} />
          </div>

          {/* Calibration chart */}
          <div className="bg-white border border-zinc-200 rounded-xl p-6">
            <h3 className="text-sm font-semibold text-zinc-700 mb-6">Predicted vs Actual</h3>
            <div className="space-y-3">
              {buckets.map((b: any) => (
                <div key={b.range_label} className="flex items-center gap-4">
                  <span className="text-xs text-zinc-400 w-24 font-mono text-right">{b.range_label}</span>
                  <div className="flex-1 flex items-center gap-2">
                    <div className="flex-1 h-8 bg-zinc-50 rounded-lg overflow-hidden relative border border-zinc-100">
                      {/* Perfect calibration line */}
                      <div className="absolute inset-y-0 border-r-2 border-dashed border-zinc-300" style={{ left: `${((b.range_low + b.range_high) / 2) * 100}%` }} />
                      {/* Hit rate bar */}
                      <div
                        className={`absolute inset-y-0 left-0 rounded-lg transition-all ${
                          Math.abs(b.gap) < 0.1 ? "bg-emerald-400" : b.gap > 0 ? "bg-blue-400" : "bg-amber-400"
                        }`}
                        style={{ width: `${Math.max((b.hit_rate || 0) * 100, 2)}%`, opacity: 0.7 }}
                      />
                    </div>
                    <span className="text-xs text-zinc-500 w-16 font-mono">
                      {b.count > 0 ? `${(b.hit_rate * 100).toFixed(0)}% (${b.count})` : "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-6 mt-4 pt-4 border-t border-zinc-100 text-xs text-zinc-400">
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-emerald-400 opacity-70" /> Well calibrated</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-blue-400 opacity-70" /> Underconfident</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-amber-400 opacity-70" /> Overconfident</div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-1 border-r-2 border-dashed border-zinc-300" /> Perfect line</div>
            </div>
          </div>

          {/* Bias alerts */}
          {bias.length > 0 && (
            <div className="space-y-2">
              {bias.map((b: any, i: number) => (
                <div key={i} className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
                  b.direction === "overconfident" ? "bg-amber-50 border-amber-200" : "bg-blue-50 border-blue-200"
                }`}>
                  <AlertTriangle className={`w-4 h-4 ${
                    b.direction === "overconfident" ? "text-amber-500" : "text-blue-500"
                  }`} />
                  <span className="text-sm">
                    You are <strong>{b.direction}</strong> in {b.domain} by {(Math.abs(b.gap) * 100).toFixed(0)}% ({b.count} predictions)
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto">
            <BarChart3 className="w-8 h-8 text-emerald-500" />
          </div>
          <h3 className="text-lg font-semibold text-zinc-800">Keep making predictions!</h3>
          <p className="text-sm text-zinc-500 max-w-md mx-auto">
            You need at least 20 resolved predictions to see your calibration curve. Start by making predictions with your decisions.
          </p>
          <div className="w-48 mx-auto">
            <div className="flex justify-between text-xs text-zinc-400 mb-1">
              <span>{resolved} resolved</span>
              <span>20 needed</span>
            </div>
            <div className="w-full bg-zinc-100 rounded-full h-2.5">
              <div className="bg-emerald-500 h-2.5 rounded-full transition-all" style={{ width: `${Math.min((resolved / 20) * 100, 100)}%` }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
