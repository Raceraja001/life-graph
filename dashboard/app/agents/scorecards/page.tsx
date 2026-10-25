"use client";
// How each agent driver performs: success, bounces, merges, cost; and the
// per-project auto-merge trust the dispatcher reads.
import { useState } from "react";
import Link from "next/link";
import { Gauge } from "lucide-react";
import { autoMergeState, pct, usd, useScorecards, type Scorecard } from "@/lib/observe";
import { Card, DaysPicker, Empty, ErrorBox, Loading, Pill } from "@/components/observe-ui";

function Metric({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div>
      <p className="text-[11px] text-ink-low">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-ink">{value}</p>
      {hint && <p className="text-[11px] text-ink-low">{hint}</p>}
    </div>
  );
}

function ScoreCard({ c }: { c: Scorecard }) {
  const rate = Math.round(c.success_rate * 100);
  const bar = c.success_rate >= 0.8 ? "bg-success" : c.success_rate >= 0.5 ? "bg-warning" : "bg-danger";
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-mono text-sm font-semibold text-ink">{c.driver}</h3>
        <span className="text-xs text-ink-low">{c.personas.join(", ")}</span>
      </div>
      {c.models.length > 0 && (
        <p className="mt-0.5 break-all font-mono text-[11px] text-ink-low">{c.models.join(" · ")}</p>
      )}
      <div className="mt-3">
        <div className="mb-1 flex justify-between text-xs text-ink-mid">
          <span>Success</span>
          <span className="tabular-nums">
            {c.succeeded} of {c.runs} · {pct(c.success_rate)}
          </span>
        </div>
        <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
          <div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, rate)}%` }} />
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Merged" value={c.merged} />
        <Metric label="Bounced" value={pct(c.bounce_rate)} hint={`${c.bounced} runs`} />
        <Metric label="Spent" value={usd(c.cost_usd)} />
        <Metric label="Per merged PR" value={c.cost_per_merged == null ? "—" : usd(c.cost_per_merged)} />
      </div>
      {c.top_causes.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] text-ink-low">Top failure causes</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {c.top_causes.map((x) => (
              <Link key={x.cause} href={`/agents/failures?cause=${x.cause}`}>
                <Pill tone="danger">
                  {x.label} · {x.count}
                </Pill>
              </Link>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function ScorecardsPage() {
  const [days, setDays] = useState(30);
  const data = useScorecards(days);
  const cards = data.data?.cards ?? [];
  const autoMerge = data.data?.auto_merge ?? [];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-ink-mid">Finished runs in the window, per driver.</p>
        <DaysPicker days={days} onChange={setDays} />
      </div>
      <ErrorBox error={data.error} />
      {data.isLoading && !data.data && <Loading />}
      {data.data && cards.length === 0 && (
        <Empty icon={<Gauge className="h-5 w-5" />} title="No finished runs in this window" />
      )}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {cards.map((c) => (
          <ScoreCard key={c.driver} c={c} />
        ))}
      </div>

      {autoMerge.length > 0 && (
        <Card>
          <h3 className="text-sm font-semibold text-ink">Auto-merge trust</h3>
          <p className="mt-0.5 text-xs text-ink-mid">
            A PR merges without review only when its project has opted in and the driver&rsquo;s merge rate clears the
            bar on enough PRs.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-ink-low">
                <tr>
                  <th className="py-1 pr-3 font-normal">Persona</th>
                  <th className="py-1 pr-3 font-normal">Project</th>
                  <th className="py-1 pr-3 font-normal">Merge rate</th>
                  <th className="py-1 pr-3 font-normal">Bar</th>
                  <th className="py-1 font-normal">Auto-merge</th>
                </tr>
              </thead>
              <tbody>
                {autoMerge.map((a) => {
                  const s = autoMergeState(a);
                  return (
                    <tr key={`${a.persona}-${a.project_name}`} className="border-t border-line text-ink-mid">
                      <td className="py-1.5 pr-3 font-mono">{a.persona}</td>
                      <td className="py-1.5 pr-3">{a.project_name}</td>
                      <td className="py-1.5 pr-3 tabular-nums">
                        {pct(a.merge_rate)} ({a.merged}/{a.total})
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums">{pct(a.threshold)}</td>
                      <td className="py-1.5">
                        <Pill tone={s.tone}>{s.label}</Pill>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
