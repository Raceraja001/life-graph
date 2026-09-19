"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Mail } from "lucide-react";
import { api, type TodayEvent, type WaitingMail } from "@/lib/api";

/** HH:MM in the user's configured zone (the same day the brief uses), not the browser's. */
function hm(iso: string | null, timeZone?: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone });
  } catch {
    return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
}

function daysAgo(iso: string | null): string {
  if (!iso) return "";
  const h = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  return h >= 24 ? `${Math.floor(h / 24)}d` : `${Math.max(1, Math.floor(h))}h`;
}

function overlaps(events: TodayEvent[]): Set<string> {
  const timed = events.filter((e) => !e.all_day && e.starts_at && e.ends_at);
  const clash = new Set<string>();
  timed.forEach((a, i) =>
    timed.slice(i + 1).forEach((b) => {
      if (a.starts_at! < b.ends_at! && b.starts_at! < a.ends_at!) {
        clash.add(a.id);
        clash.add(b.id);
      }
    })
  );
  return clash;
}

/** Today's events and mail waiting on the user, from connected accounts. */
export function TodayCard() {
  const today = useQuery({ queryKey: ["connectors-today"], queryFn: api.connectors.today, refetchInterval: 60000 });
  const data = today.data;
  if (today.isLoading || today.isError) return null;
  if (!data) {
    return (
      <div className="bg-surface border border-line rounded-xl p-5 text-sm text-ink-mid">
        Connect a calendar or mailbox in{" "}
        <Link href="/settings" className="text-accent-text underline">Settings</Link> to see your day here.
      </div>
    );
  }
  const tz = data.timezone;
  const events = data.today.items;
  const clash = overlaps(events);
  const waiting = data.waiting.items;
  const promises = data.promises?.items ?? [];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <section className="bg-surface border border-line rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-accent" /> Today
        </h3>
        {events.length === 0 ? (
          <p className="text-sm text-ink-low">Nothing on the calendar.</p>
        ) : (
          <ul className="space-y-2">
            {events.map((e) => (
              <li key={e.id} className="flex gap-3 text-sm">
                <span className="w-24 shrink-0 text-ink-mid tabular-nums whitespace-nowrap">
                  {e.all_day ? "All day" : `${hm(e.starts_at, tz)}–${hm(e.ends_at, tz)}`}
                </span>
                <span className="min-w-0">
                  <span className="text-ink">{e.title}</span>
                  {e.location && <span className="text-ink-low"> · {e.location}</span>}
                  <span className="text-ink-low"> · {e.account}</span>
                  {clash.has(e.id) && <span className="ml-1 text-[11px] text-danger">overlaps</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
        {data.tomorrow_early.items[0] && (
          <p className="text-xs text-ink-mid">
            Tomorrow starts early: {hm(data.tomorrow_early.items[0].starts_at, tz)} {data.tomorrow_early.items[0].title}
          </p>
        )}
      </section>
      <section className="bg-surface border border-line rounded-xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <Mail className="w-4 h-4 text-accent" /> Waiting on you ({waiting.length})
        </h3>
        {waiting.length === 0 ? (
          <p className="text-sm text-ink-low">No email waiting on a reply.</p>
        ) : (
          <ul className="space-y-2.5">
            {waiting.slice(0, 6).map((m) => (
              <li key={m.id} className="text-sm">
                <p className="text-ink">
                  <span className="text-ink-low tabular-nums mr-2">{daysAgo(m.date)}</span>
                  {m.sender_name || m.sender_addr}: {m.subject}
                </p>
                {m.summary && <p className="text-xs text-ink-mid line-clamp-2">{m.summary}</p>}
              </li>
            ))}
          </ul>
        )}
        {promises.length > 0 && (
          <div className="pt-3 border-t border-line space-y-2">
            <h4 className="text-xs font-semibold text-ink-mid uppercase tracking-wider">
              You promised ({promises.length})
            </h4>
            {promises.slice(0, 5).map((p) => (
              <PromiseRow key={p.id} p={p} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function dueLabel(due: string | null | undefined): string {
  if (!due) return "";
  const today = new Date().toISOString().slice(0, 10);
  if (due < today) return " · overdue";
  if (due === today) return " · due today";
  return ` · due ${new Date(`${due}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}`;
}

function PromiseRow({ p }: { p: WaitingMail }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["connectors-today"] });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <p className="flex-1 min-w-[12rem] text-ink">
        {p.commitment}
        <span className="text-ink-low">{dueLabel(p.commitment_due)} · re: {p.subject}</span>
      </p>
      <button
        disabled={busy}
        onClick={() => act(() => api.connectors.remind(p.id))}
        className="text-xs px-2.5 py-1 rounded-md bg-accent text-accent-fg disabled:opacity-50"
      >
        Remind me
      </button>
      <button
        disabled={busy}
        onClick={() => act(() => api.connectors.dismissPromise(p.id))}
        className="text-xs px-2 py-1 rounded-md text-ink-mid hover:bg-surface-3 disabled:opacity-50"
      >
        Dismiss
      </button>
    </div>
  );
}
