"use client";
import { useState } from "react";
import { Scale, ChevronRight, ChevronDown, Target, Clock } from "lucide-react";
import { useDecisions, usePredictions } from "@/lib/hooks";

function DecisionCard({ decision }: { decision: any }) {
  const [expanded, setExpanded] = useState(false);
  const predictions = usePredictions({ limit: "50" });
  const linkedPreds = (predictions.data ?? []).filter((p: any) => p.decision_id === decision.id);

  return (
    <div className="bg-white border border-zinc-200 rounded-xl hover:shadow-md hover:border-zinc-300 transition-all">
      <div className="p-5 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-sm font-semibold text-zinc-800">{decision.title}</h3>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                decision.status === "decided" ? "bg-emerald-50 text-emerald-700" :
                decision.status === "candidate" ? "bg-amber-50 text-amber-700" :
                decision.status === "reviewed" ? "bg-blue-50 text-blue-700" :
                decision.status === "superseded" ? "bg-zinc-100 text-zinc-500 line-through" :
                "bg-zinc-100 text-zinc-500"
              }`}>{decision.status}</span>
              {linkedPreds.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded-full">
                  {linkedPreds.length} prediction{linkedPreds.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
            {decision.reasoning && <p className="text-sm text-zinc-500 line-clamp-2 mb-2">{decision.reasoning}</p>}
            {decision.chosen_option && (
              <p className="text-xs text-emerald-600 font-medium">Chose: {decision.chosen_option}</p>
            )}
            <div className="flex items-center gap-3 mt-2">
              <span className="text-xs text-zinc-400">{new Date(decision.created_at).toLocaleDateString()}</span>
              {decision.domain_tags?.map((t: string) => (
                <span key={t} className="text-[10px] px-1.5 py-0.5 bg-zinc-100 text-zinc-500 rounded">{t}</span>
              ))}
            </div>
          </div>
          {expanded
            ? <ChevronDown className="w-4 h-4 text-zinc-400 shrink-0 mt-1" />
            : <ChevronRight className="w-4 h-4 text-zinc-300 shrink-0 mt-1" />
          }
        </div>
      </div>

      {expanded && (
        <div className="border-t border-zinc-100 px-5 py-4 space-y-3 bg-zinc-50/50">
          {/* Options */}
          {decision.options && decision.options.length > 0 && (
            <div>
              <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Options Considered</span>
              <div className="mt-2 space-y-2">
                {decision.options.map((opt: any, i: number) => (
                  <div key={i} className={`px-3 py-2 rounded-lg border text-sm ${
                    opt.label === decision.chosen_option
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-zinc-100 bg-white text-zinc-600"
                  }`}>
                    <span className="font-medium">{opt.label}</span>
                    {opt.pros && <span className="text-xs ml-2 text-emerald-600">+ {opt.pros}</span>}
                    {opt.cons && <span className="text-xs ml-2 text-red-500">- {opt.cons}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Linked predictions */}
          {linkedPreds.length > 0 && (
            <div>
              <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Predictions</span>
              <div className="mt-2 space-y-2">
                {linkedPreds.map((p: any) => (
                  <div key={p.id} className="flex items-center gap-3 px-3 py-2 bg-white rounded-lg border border-zinc-100">
                    <Target className={`w-3.5 h-3.5 shrink-0 ${
                      p.outcome === "correct" ? "text-emerald-500" :
                      p.outcome === "incorrect" ? "text-red-500" :
                      "text-zinc-400"
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-zinc-700">{p.statement}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="w-16 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${p.confidence * 100}%` }} />
                      </div>
                      <span className="text-[10px] font-mono text-zinc-500">{(p.confidence * 100).toFixed(0)}%</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        p.outcome === "correct" ? "bg-emerald-50 text-emerald-600" :
                        p.outcome === "incorrect" ? "bg-red-50 text-red-600" :
                        p.outcome === "pending" ? "bg-blue-50 text-blue-600" :
                        "bg-zinc-100 text-zinc-400"
                      }`}>{p.outcome}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Review date */}
          {decision.review_at && (
            <div className="flex items-center gap-2 text-xs text-zinc-400 pt-2">
              <Clock className="w-3 h-3" />
              <span>Review: {new Date(decision.review_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DecisionsPage() {
  const decisions = useDecisions({ limit: "50" });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">Decisions</h2>
          <p className="text-sm text-zinc-500">Track decisions, predictions, and outcomes</p>
        </div>
      </div>

      {decisions.data && decisions.data.length > 0 ? (
        <div className="space-y-3">
          {decisions.data.map((d: any) => (
            <DecisionCard key={d.id} decision={d} />
          ))}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
            <Scale className="w-6 h-6 text-emerald-500" />
          </div>
          <p className="text-sm text-zinc-500">No decisions tracked yet. Type &quot;I decided to...&quot; in the chat bar.</p>
        </div>
      )}
    </div>
  );
}
