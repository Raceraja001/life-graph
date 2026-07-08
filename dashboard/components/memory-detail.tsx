"use client";
import { X, Clock, Tag, BarChart2, Link2 } from "lucide-react";

export function MemoryDetail({ memory, onClose }: {
  memory: any;
  onClose: () => void;
}) {
  if (!memory) return null;
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/10" onClick={onClose} />
      <div className="absolute right-0 top-0 bottom-0 w-[480px] bg-white border-l border-zinc-200 shadow-2xl shadow-zinc-300/30 overflow-y-auto">
        <div className="sticky top-0 bg-white/90 backdrop-blur-sm border-b border-zinc-100 px-6 py-4 flex items-center justify-between z-10">
          <h3 className="text-sm font-semibold text-zinc-800">Memory Detail</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100 text-zinc-400 hover:text-zinc-600 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-6">
          {/* Content */}
          <div>
            <label className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Content</label>
            <p className="text-sm text-zinc-700 mt-2 leading-relaxed whitespace-pre-wrap">{memory.content}</p>
          </div>

          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-zinc-50 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <BarChart2 className="w-3 h-3 text-zinc-400" />
                <span className="text-[10px] font-medium text-zinc-400 uppercase">Importance</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-zinc-200 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${(memory.importance || 0.5) * 100}%` }} />
                </div>
                <span className="text-sm font-semibold text-zinc-700">{((memory.importance || 0.5) * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="bg-zinc-50 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Clock className="w-3 h-3 text-zinc-400" />
                <span className="text-[10px] font-medium text-zinc-400 uppercase">Created</span>
              </div>
              <span className="text-sm font-semibold text-zinc-700">
                {new Date(memory.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>

          {/* Tags */}
          {memory.tags && memory.tags.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Tag className="w-3 h-3 text-zinc-400" />
                <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Tags</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {memory.tags.map((t: string) => (
                  <span key={t} className="text-xs px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Source */}
          {memory.source && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Link2 className="w-3 h-3 text-zinc-400" />
                <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Source</span>
              </div>
              <span className="text-xs px-2 py-1 bg-zinc-100 text-zinc-600 rounded-lg">{memory.source}</span>
            </div>
          )}

          {/* Properties */}
          {memory.properties && Object.keys(memory.properties).length > 0 && (
            <div>
              <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">Properties</span>
              <pre className="mt-2 text-xs text-zinc-600 bg-zinc-50 p-3 rounded-lg overflow-x-auto border border-zinc-100">
                {JSON.stringify(memory.properties, null, 2)}
              </pre>
            </div>
          )}

          {/* ID */}
          <div className="pt-4 border-t border-zinc-100">
            <span className="text-[10px] font-mono text-zinc-300">{memory.id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
