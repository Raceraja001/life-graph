"use client";
import { BarChart3 } from "lucide-react";

export default function CalibrationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Calibration</h2>
        <p className="text-sm text-zinc-500">How accurate are your predictions?</p>
      </div>

      <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 flex items-center justify-center mx-auto">
          <BarChart3 className="w-8 h-8 text-emerald-500" />
        </div>
        <h3 className="text-lg font-semibold text-zinc-800">Coming Soon</h3>
        <p className="text-sm text-zinc-500 max-w-md mx-auto">
          The Judgment Engine (decisions, predictions, calibration) is the next spec to be built.
          Once active, your calibration curve will appear here.
        </p>
        <div className="flex items-center justify-center gap-4 text-xs text-zinc-400 pt-2">
          <span>📊 Brier Score</span>
          <span>📈 Calibration Curve</span>
          <span>⚠️ Bias Detection</span>
        </div>
      </div>
    </div>
  );
}
