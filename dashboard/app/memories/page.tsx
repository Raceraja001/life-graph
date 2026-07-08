"use client";
import { useState } from "react";
import { Search, Brain } from "lucide-react";
import { useMemories, useMemorySearch } from "@/lib/hooks";
import { MemoryDetail } from "@/components/memory-detail";

export default function MemoriesPage() {
  const [query, setQuery] = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const memories = useMemories({ limit: "50" });
  const search = useMemorySearch(searchActive ? query : "");

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
          <h2 className="text-lg font-semibold text-zinc-900">Memories</h2>
          <p className="text-sm text-zinc-500">Search and browse your stored knowledge</p>
        </div>
        <form onSubmit={handleSearch} className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); if (e.target.value.length < 3) setSearchActive(false); }}
            placeholder="Semantic search..."
            className="bg-white border border-zinc-200 rounded-xl pl-10 pr-4 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100 w-72"
          />
        </form>
      </div>

      {isLoading ? (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center">
          <div className="animate-pulse text-zinc-400 text-sm">Loading memories...</div>
        </div>
      ) : data && data.length > 0 ? (
        <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-100">
                <th className="text-left px-5 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Content</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider w-24">Importance</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider w-32">Tags</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider w-36">Created</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m: any) => (
                <tr
                  key={m.id}
                  onClick={() => setSelected(m)}
                  className="border-b border-zinc-50 hover:bg-emerald-50/30 transition-colors cursor-pointer group"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-sm text-zinc-700 line-clamp-2">{m.content}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${(m.importance || 0.5) * 100}%` }} />
                      </div>
                      <span className="text-xs text-zinc-400">{((m.importance || 0.5) * 100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex flex-wrap gap-1">
                      {(m.tags || []).slice(0, 2).map((t: string) => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 bg-zinc-100 text-zinc-500 rounded">{t}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-zinc-400">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center mx-auto">
            <Brain className="w-6 h-6 text-emerald-500" />
          </div>
          <p className="text-sm text-zinc-500">No memories yet. Start by typing something in the chat bar below.</p>
        </div>
      )}

      {selected && <MemoryDetail memory={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
