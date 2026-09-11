"use client";
import { useState } from "react";
import { Search, Brain, Check, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useMemories, useMemorySearch } from "@/lib/hooks";
import { api } from "@/lib/api";
import { MemoryDetail } from "@/components/memory-detail";

export default function MemoriesPage() {
  const [query, setQuery] = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const memories = useMemories({ limit: "50" });
  const search = useMemorySearch(searchActive ? query : "");
  const queryClient = useQueryClient();

  const resolveMemory = async (id: string, action: "approve" | "reject") => {
    setResolvingId(id);
    try {
      await (action === "approve" ? api.memories.approve(id) : api.memories.reject(id));
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      queryClient.invalidateQueries({ queryKey: ["memory-search"] });
    } finally {
      setResolvingId(null);
    }
  };

  const data = searchActive && query.length > 2 ? search.data : memories.data;
  const isLoading = searchActive ? search.isLoading : memories.isLoading;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.length > 2) setSearchActive(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink">Memories</h2>
          <p className="text-sm text-ink-mid">Search and browse your stored knowledge</p>
        </div>
        <form onSubmit={handleSearch} className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-low" />
          <input
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); if (e.target.value.length < 3) setSearchActive(false); }}
            placeholder="Semantic search..."
            className="bg-surface border border-line rounded-xl pl-10 pr-4 py-2 text-sm text-ink placeholder-ink-low focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft w-72"
          />
        </form>
      </div>

      {isLoading ? (
        <div className="bg-surface border border-line rounded-xl p-12 text-center">
          <div className="animate-pulse text-ink-low text-sm">Loading memories...</div>
        </div>
      ) : data && data.length > 0 ? (
        <div className="bg-surface border border-line rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line">
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider">Content</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-24">Importance</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-32">Tags</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-36">Created</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-24">Status</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-ink-low uppercase tracking-wider w-24">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m: any) => (
                <tr
                  key={m.id}
                  onClick={() => setSelected(m)}
                  className="border-b border-line hover:bg-accent-soft/30 transition-colors cursor-pointer group"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-sm text-ink line-clamp-2">{m.content}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${(m.importance || 0.5) * 100}%` }} />
                      </div>
                      <span className="text-xs text-ink-low">{((m.importance || 0.5) * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex flex-wrap gap-1">
                      {(m.tags || []).slice(0, 2).map((t: string) => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 bg-surface-3 text-ink-mid rounded">{t}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-ink-low">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-5 py-3.5">
                    {m.status === "pending" ? (
                      <span className="text-warning bg-warning-soft rounded-full px-2 text-xs">pending</span>
                    ) : null}
                  </td>
                  <td className="px-5 py-3.5">
                    {m.status === "pending" && (
                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => resolveMemory(m.id, "approve")}
                          disabled={resolvingId === m.id}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-accent-soft text-accent hover:bg-accent-soft disabled:opacity-50"
                          aria-label="Approve"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => resolveMemory(m.id, "reject")}
                          disabled={resolvingId === m.id}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-danger-soft text-danger hover:bg-danger-soft disabled:opacity-50"
                          aria-label="Reject"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-surface border border-line rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-accent-soft flex items-center justify-center mx-auto">
            <Brain className="w-6 h-6 text-accent" />
          </div>
          <p className="text-sm text-ink-mid">No memories yet. Start by typing something in the chat bar below.</p>
        </div>
      )}

      {selected && <MemoryDetail key={selected.id} memory={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
