"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Cake, CalendarDays, GitPullRequest, Mail, Receipt } from "lucide-react";
import {
  api,
  type BillItem,
  type BirthdayContact,
  type CodeItem,
  type TodayEvent,
  type WaitingMail,
} from "@/lib/api";

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

/** Today's events, birthdays and mail waiting on the user, from connected accounts. */
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
  const birthdays = data.birthdays?.items ?? [];
  const code = data.code ?? { items: [], withheld: {} };
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
        {birthdays.length > 0 && (
          <div className="pt-3 border-t border-line space-y-1.5">
            <h4 className="text-xs font-semibold text-ink-mid uppercase tracking-wider flex items-center gap-1.5">
              <Cake className="w-3.5 h-3.5" /> Birthdays
            </h4>
            {birthdays.map((c) => (
              <p key={c.id} className="text-sm text-ink">
                {c.name}
                <span className="text-ink-low"> · {birthdayLabel(c, tz)}</span>
              </p>
            ))}
          </div>
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
        {(data.bills?.items.length ?? 0) > 0 && (
          <div className="pt-3 border-t border-line space-y-2">
            <h4 className="text-xs font-semibold text-ink-mid uppercase tracking-wider flex items-center gap-1.5">
              <Receipt className="w-3.5 h-3.5" /> Bills &amp; renewals
            </h4>
            {data.bills!.items.map((b) => (
              <BillRow key={b.id} b={b} timeZone={tz} />
            ))}
          </div>
        )}
        {(code.items.length > 0 || Object.keys(code.withheld).length > 0) && <CodeBlock code={code} />}
      </section>
    </div>
  );
}

/** Same order and wording as the brief: most urgent first. */
function prState(c: CodeItem): [number, string] {
  if (c.review === "CHANGES_REQUESTED") return [0, "changes requested"];
  if (c.ci === "FAILURE" || c.ci === "ERROR") return [1, "CI failing"];
  if (c.mergeable === "CONFLICTING") return [2, "merge conflict"];
  if (c.review === "APPROVED" && (!c.ci || c.ci === "SUCCESS")) return [3, "approved, ready to merge"];
  return [9, "waiting on reviewers"];
}

function CodeRow({ c, note }: { c: CodeItem; note?: string }) {
  const ref = `${c.repo.split("/").pop()}#${c.number}`;
  const label = (
    <>
      <span className="text-ink-mid tabular-nums mr-1.5">{ref}</span>
      {c.title}
    </>
  );
  return (
    <p className="text-sm text-ink">
      {c.url ? (
        <a href={c.url} target="_blank" rel="noreferrer" className="hover:underline">
          {label}
        </a>
      ) : (
        label
      )}
      {c.dev_agent && <span className="text-ink-low"> · dev agent</span>}
      {note && <span className={`text-xs ${note === "CI failing" || note === "changes requested" ? "text-danger" : "text-ink-low"}`}> · {note}</span>}
    </p>
  );
}

/** Pull requests and issues waiting on the user, from connected GitHub accounts. */
function CodeBlock({ code }: { code: { items: CodeItem[]; withheld: Record<string, number> } }) {
  const reviews = code.items.filter((c) => c.sub === "pr_review" && !c.draft);
  const mine = code.items
    .filter((c) => c.sub === "pr_mine" && !c.draft)
    .sort((a, b) => prState(a)[0] - prState(b)[0]);
  const issues = code.items.filter((c) => c.sub === "issue");
  return (
    <div className="pt-3 border-t border-line space-y-2">
      <h4 className="text-xs font-semibold text-ink-mid uppercase tracking-wider flex items-center gap-1.5">
        <GitPullRequest className="w-3.5 h-3.5" /> Code
      </h4>
      {reviews.slice(0, 5).map((c) => (
        <CodeRow key={c.id} c={c} note={`review requested${c.author ? ` by ${c.author}` : ""}`} />
      ))}
      {mine.slice(0, 5).map((c) => (
        <CodeRow key={c.id} c={c} note={prState(c)[1]} />
      ))}
      {issues.slice(0, 5).map((c) => (
        <CodeRow key={c.id} c={c} note="assigned" />
      ))}
      {Object.entries(code.withheld).map(([account, n]) => (
        <p key={account} className="text-xs text-ink-low">
          +{n} in {account}
        </p>
      ))}
    </div>
  );
}

/** "today", "tomorrow" or "Sat 21 Sep", counted in the user's zone. */
function birthdayLabel(c: BirthdayContact, timeZone?: string): string {
  let today: string;
  try {
    today = new Date().toLocaleDateString("en-CA", { timeZone });
  } catch {
    today = new Date().toLocaleDateString("en-CA");
  }
  const tomorrow = new Date(`${today}T12:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  if (c.on === today) return "today";
  if (c.on === tomorrow.toISOString().slice(0, 10)) return "tomorrow";
  return new Date(`${c.on}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

function dueLabel(due: string | null | undefined): string {
  if (!due) return "";
  const today = new Date().toISOString().slice(0, 10);
  if (due < today) return " · overdue";
  if (due === today) return " · due today";
  return ` · due ${new Date(`${due}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}`;
}

const MONEY: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

/** One bill from mail: payee, due date, amount, and what to do about it. */
function BillRow({ b, timeZone }: { b: BillItem; timeZone?: string }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const act = async (action: "paid" | "dismiss" | "remind") => {
    setBusy(true);
    try {
      await api.connectors.billAction(b.id, action);
      await qc.invalidateQueries({ queryKey: ["connectors-today"] });
    } finally {
      setBusy(false);
    }
  };
  let today: string;
  try {
    today = new Date().toLocaleDateString("en-CA", { timeZone });
  } catch {
    today = new Date().toLocaleDateString("en-CA");
  }
  const day = new Date(`${b.due}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
  const overdue = b.kind === "bill" && b.due < today;
  const when = b.kind === "renewal" ? `renews ${day}` : b.due === today ? "due today" : `due ${day}`;
  const amount =
    b.amount != null
      ? `${MONEY[b.currency ?? ""] ?? `${b.currency ?? ""} `}${b.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
      : "";
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <p className="flex-1 min-w-[12rem] text-ink">
        {b.payee}
        {amount && <span className="text-ink"> · {amount}</span>}
        <span className={overdue ? "text-danger" : "text-ink-low"}>
          {" "}
          · {overdue ? `overdue (${when})` : when}
          {b.autopay ? " · autopay" : ""}
          {b.state === "reminded" ? " · reminder set" : ""}
        </span>
      </p>
      {b.state !== "reminded" && (
        <button
          disabled={busy}
          onClick={() => act("remind")}
          className="text-xs px-2.5 py-1 rounded-md bg-accent text-accent-fg disabled:opacity-50"
        >
          Remind me
        </button>
      )}
      <button
        disabled={busy}
        onClick={() => act("paid")}
        className="text-xs px-2 py-1 rounded-md border border-line text-ink-mid hover:bg-surface-3 disabled:opacity-50"
      >
        Paid
      </button>
      <button
        disabled={busy}
        onClick={() => act("dismiss")}
        className="text-xs px-2 py-1 rounded-md text-ink-mid hover:bg-surface-3 disabled:opacity-50"
      >
        Dismiss
      </button>
    </div>
  );
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
