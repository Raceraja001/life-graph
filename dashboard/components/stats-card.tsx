import type { LucideIcon } from "lucide-react";

export function StatsCard({ label, value, subtitle, icon: Icon, trend }: {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: { value: number; label: string };
}) {
  return (
    <div className="bg-white border border-zinc-200 rounded-xl p-5 hover:shadow-md hover:border-zinc-300 transition-all group">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-zinc-400 uppercase tracking-wider">{label}</span>
        <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center group-hover:bg-emerald-100 transition-colors">
          <Icon className="w-4 h-4 text-emerald-600" />
        </div>
      </div>
      <div className="text-2xl font-bold text-zinc-900 tracking-tight">{value}</div>
      {subtitle && <p className="text-xs text-zinc-400 mt-1">{subtitle}</p>}
      {trend && (
        <div className={`flex items-center gap-1 mt-2 text-xs ${trend.value >= 0 ? "text-emerald-600" : "text-red-500"}`}>
          <span>{trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}%</span>
          <span className="text-zinc-400">{trend.label}</span>
        </div>
      )}
    </div>
  );
}
