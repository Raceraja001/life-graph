"use client";
// Small surfaces shared by the observability pages (replay, scorecards,
// failures, agents console), in the dashboard's tokens.
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { TONE_CLS, type Tone } from "@/lib/observe";

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`bg-surface border border-line rounded-xl p-4 ${className}`}>{children}</div>;
}

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${TONE_CLS[tone]}`}
    >
      {children}
    </span>
  );
}

export function ErrorBox({ error }: { error?: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="flex items-start gap-2 bg-danger-soft border border-line rounded-xl p-4 text-sm text-danger">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
      <span className="break-words">Cannot reach the API — {message}</span>
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="bg-surface border border-line rounded-xl p-10 text-center space-y-2">
      <div className="w-10 h-10 rounded-xl bg-accent-soft flex items-center justify-center mx-auto text-accent">
        {icon}
      </div>
      <p className="text-sm text-ink-mid">{title}</p>
      {children && <p className="text-xs text-ink-low max-w-md mx-auto">{children}</p>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="bg-surface border border-line rounded-xl p-6 text-sm text-ink-low animate-pulse" role="status">
      {label}
    </div>
  );
}

/** Window picker: 7d · 30d · 90d. */
export function DaysPicker({
  days,
  onChange,
  options = [7, 30, 90],
}: {
  days: number;
  onChange: (d: number) => void;
  options?: number[];
}) {
  return (
    <div className="flex gap-1" role="group" aria-label="Time window">
      {options.map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => onChange(d)}
          aria-pressed={d === days}
          className={`rounded-md px-2 py-1 text-xs ${
            d === days ? "bg-accent text-accent-fg" : "text-ink-mid hover:bg-surface-2"
          }`}
        >
          {d}d
        </button>
      ))}
    </div>
  );
}

/** The Agents section's tabs: console, scorecards, failures. */
export function AgentsTabs() {
  const pathname = usePathname();
  const tabs = [
    { href: "/agents", label: "Console" },
    { href: "/agents/scorecards", label: "Scorecards" },
    { href: "/agents/failures", label: "Failures" },
  ];
  return (
    <nav className="flex gap-1 border-b border-line" aria-label="Agents sections">
      {tabs.map((t) => {
        const active = pathname === t.href;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={`px-3 py-2 text-sm -mb-px border-b-2 ${
              active ? "border-accent text-ink font-medium" : "border-transparent text-ink-mid hover:text-ink"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
