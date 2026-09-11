"use client";
import { useState } from "react";
import { X, Clock, Tag, BarChart2, Link2, Pencil } from "lucide-react";
import { useUpdateMemory } from "@/lib/mobile-api";

export function MemoryDetail({ memory, onClose }: {
  memory: any;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(memory?.content ?? "");
  const [tagsText, setTagsText] = useState(Array.isArray(memory?.tags) ? memory.tags.join(", ") : "");
  const currentTags = tagsText.split(",").map((t: string) => t.trim()).filter(Boolean);
  const update = useUpdateMemory();

  if (!memory) return null;

  const startEdit = () => {
    setContent(memory.content ?? "");
    setTagsText(Array.isArray(memory.tags) ? memory.tags.join(", ") : "");
    setEditing(true);
  };
  const cancelEdit = () => {
    setContent(memory.content ?? "");
    setTagsText(Array.isArray(memory.tags) ? memory.tags.join(", ") : "");
    setEditing(false);
  };
  const saveEdit = () => {
    update.mutate(
      { id: memory.id, content, tags: currentTags },
      { onSuccess: () => setEditing(false) }
    );
  };

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div className="absolute right-0 top-0 bottom-0 w-[480px] bg-surface border-l border-line shadow-2xl shadow-ink/10 overflow-y-auto">
        <div className="sticky top-0 bg-surface/90 backdrop-blur-sm border-b border-line px-6 py-4 flex items-center justify-between z-10">
          <h3 className="text-sm font-semibold text-ink">Memory Detail</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-3 text-ink-low hover:text-ink-mid transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-6">
          {/* Content */}
          <div>
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-medium text-ink-low uppercase tracking-wider">Content</label>
              {!editing && (
                <button
                  onClick={startEdit}
                  className="flex items-center gap-1 text-[11px] font-medium text-accent hover:text-accent-text"
                >
                  <Pencil className="w-3 h-3" /> Edit
                </button>
              )}
            </div>
            {editing ? (
              <div className="mt-2 space-y-2">
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={5}
                  autoFocus
                  className="w-full text-sm text-ink leading-relaxed rounded-lg border border-line bg-surface-2 p-3 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y"
                />
                <input
                  value={tagsText}
                  onChange={(e) => setTagsText(e.target.value)}
                  placeholder="tags, comma, separated"
                  className="w-full text-xs text-ink rounded-lg border border-line bg-surface-2 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent"
                />
                {update.isError && (
                  <p className="text-xs text-danger">Couldn&apos;t save — try again.</p>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={saveEdit}
                    disabled={update.isPending || !content.trim()}
                    className="flex-1 text-xs font-semibold rounded-lg bg-accent text-accent-fg py-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-accent-hover transition-colors"
                  >
                    {update.isPending ? "Saving…" : "Save"}
                  </button>
                  <button
                    onClick={cancelEdit}
                    disabled={update.isPending}
                    className="flex-1 text-xs font-semibold rounded-lg border border-line text-ink-mid py-2 disabled:opacity-50 hover:bg-surface-2 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink mt-2 leading-relaxed whitespace-pre-wrap">{content}</p>
            )}
          </div>

          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-surface-2 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <BarChart2 className="w-3 h-3 text-ink-low" />
                <span className="text-[10px] font-medium text-ink-low uppercase">Importance</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full" style={{ width: `${(memory.importance || 0.5) * 100}%` }} />
                </div>
                <span className="text-sm font-semibold text-ink">{((memory.importance || 0.5) * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="bg-surface-2 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-1">
                <Clock className="w-3 h-3 text-ink-low" />
                <span className="text-[10px] font-medium text-ink-low uppercase">Created</span>
              </div>
              <span className="text-sm font-semibold text-ink">
                {new Date(memory.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>

          {/* Tags */}
          {currentTags.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Tag className="w-3 h-3 text-ink-low" />
                <span className="text-[10px] font-medium text-ink-low uppercase tracking-wider">Tags</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {currentTags.map((t: string) => (
                  <span key={t} className="text-xs px-2 py-1 bg-accent-soft text-accent-text rounded-lg">{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Source */}
          {memory.source && (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Link2 className="w-3 h-3 text-ink-low" />
                <span className="text-[10px] font-medium text-ink-low uppercase tracking-wider">Source</span>
              </div>
              <span className="text-xs px-2 py-1 bg-surface-3 text-ink-mid rounded-lg">{memory.source}</span>
            </div>
          )}

          {/* Properties */}
          {memory.properties && Object.keys(memory.properties).length > 0 && (
            <div>
              <span className="text-[10px] font-medium text-ink-low uppercase tracking-wider">Properties</span>
              <pre className="mt-2 text-xs text-ink-mid bg-surface-2 p-3 rounded-lg overflow-x-auto border border-line">
                {JSON.stringify(memory.properties, null, 2)}
              </pre>
            </div>
          )}

          {/* ID */}
          <div className="pt-4 border-t border-line">
            <span className="text-[10px] font-mono text-ink-low">{memory.id}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
