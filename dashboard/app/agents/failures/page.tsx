"use client";
// Failure explorer: every failed dev-agent run, grouped by why it failed,
// each linking to its replay.
import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { SearchCheck } from "lucide-react";
import { useFailures, when } from "@/lib/observe";
import { Card, DaysPicker, Empty, ErrorBox, Loading, Pill } from "@/components/observe-ui";

function FailuresInner() {
  const [days, setDays] = useState(30);
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const cause = params.get("cause");
  const data = useFailures(days);
  const rows = useMemo(
    () => (data.data?.failures ?? []).filter((f) => !cause || f.cause === cause),
    [data.data, cause],
  );
  const pick = (c: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (c) next.set("cause", c);
    else next.delete("cause");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-mid">Failed runs in the window, by primary cause.</p>
        <DaysPicker days={days} onChange={setDays} options={[7, 30, 90, 365]} />
      </div>
      <ErrorBox error={data.error} />
      {data.isLoading && !data.data && <Loading />}

      {data.data && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by cause">
          <button
            type="button"
            onClick={() => pick(null)}
            aria-pressed={!cause}
            className={`rounded-full border px-3 py-1 text-xs ${
              !cause ? "border-accent bg-accent-soft text-accent-soft-fg" : "border-line text-ink-mid"
            }`}
          >
            All · {data.data.total}
          </button>
          {data.data.groups.map((g) => (
            <button
              key={g.cause}
              type="button"
              onClick={() => pick(g.cause === cause ? null : g.cause)}
              aria-pressed={g.cause === cause}
              className={`rounded-full border px-3 py-1 text-xs ${
                g.cause === cause ? "border-danger bg-danger-soft text-danger" : "border-line text-ink-mid"
              }`}
            >
              {g.label} · {g.count}
            </button>
          ))}
        </div>
      )}

      {data.data && rows.length === 0 && (
        <Empty icon={<SearchCheck className="h-5 w-5" />} title="No failed runs in this window" />
      )}
      <ul className="space-y-2">
        {rows.map((f) => (
          <li key={f.id}>
            <Card>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 line-clamp-2 text-sm text-ink break-words">{f.title}</p>
                <Pill tone="danger">{f.label}</Pill>
              </div>
              <p className="mt-1 text-xs text-ink-low">
                {f.driver ?? f.persona} · {f.task_type} · {when(f.created_at)}
                {f.detail && <span className="break-words"> · {f.detail}</span>}
              </p>
              {(f.signals?.length ?? 0) > 1 && (
                <p className="mt-1 text-[11px] text-ink-low">
                  Also: {f.signals!.filter((s) => s !== f.cause).join(", ")}
                </p>
              )}
              <div className="mt-2 text-xs">
                <Link className="text-accent-text hover:underline" href={`/drivers/${f.id}`}>
                  {f.has_steps ? "Replay the run" : "Open (no recorded steps)"}
                </Link>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function FailuresPage() {
  // useSearchParams needs a Suspense boundary for static prerendering.
  return (
    <Suspense fallback={<Loading />}>
      <FailuresInner />
    </Suspense>
  );
}
