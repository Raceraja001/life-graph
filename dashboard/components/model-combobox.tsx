"use client";
// Searchable model picker backed by the live OpenRouter catalog
// (useModelCatalog). Replaces the static <select><optgroup> dropdown.
// Built on cmdk (already used by command-palette.tsx) — no new dependency.
import { useEffect, useRef, useState } from "react";
import { Command } from "cmdk";
import { useModelCatalog, type ModelOption } from "@/lib/mobile-api";
import { MODEL_OPTIONS } from "@/lib/model-options";

const STATIC_FALLBACK: ModelOption[] = [
  ...MODEL_OPTIONS.Free.map((id) => ({ id, name: id, isFree: true })),
  ...MODEL_OPTIONS.Paid.map((id) => ({ id, name: id, isFree: false })),
];

interface ModelComboboxProps {
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
  variant: "mobile" | "desktop";
}

export function ModelCombobox({ value, onChange, disabled, variant }: ModelComboboxProps) {
  const catalog = useModelCatalog();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const options: ModelOption[] = catalog.isError
    ? STATIC_FALLBACK
    : catalog.data ?? [];
  const loading = catalog.isLoading;

  const known = options.some((m) => m.id === value);
  const pinned: ModelOption | null = value && !known ? { id: value, name: value, isFree: false } : null;
  const free = options.filter((m) => m.isFree);
  const paid = options.filter((m) => !m.isFree);

  const isMobile = variant === "mobile";
  const buttonStyle = isMobile
    ? {
        width: "100%",
        textAlign: "left" as const,
        padding: "8px 10px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border)",
        background: "var(--surface)",
        color: "var(--text)",
        fontSize: "var(--text-xs)",
      }
    : undefined;
  const buttonClassName = isMobile
    ? undefined
    : "w-full mt-1 text-left text-sm text-zinc-800 bg-zinc-50 px-3 py-2 rounded-lg border border-zinc-100";

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        disabled={disabled || loading}
        onClick={() => setOpen((o) => !o)}
        style={buttonStyle}
        className={buttonClassName}
      >
        {loading ? "Loading models…" : value || "Select a model"}
      </button>

      {open && !loading && (
        <div
          style={
            isMobile
              ? {
                  position: "absolute",
                  zIndex: 20,
                  top: "100%",
                  left: 0,
                  right: 0,
                  marginTop: "4px",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-md, 0 4px 12px rgba(0,0,0,0.1))",
                }
              : undefined
          }
          className={
            isMobile
              ? undefined
              : "absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-zinc-200 rounded-lg shadow-lg"
          }
        >
          <Command>
            <Command.Input
              autoFocus
              placeholder="Search models…"
              style={
                isMobile
                  ? {
                      width: "100%",
                      padding: "8px 10px",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: "transparent",
                      color: "var(--text)",
                      fontSize: "var(--text-xs)",
                      outline: "none",
                    }
                  : undefined
              }
              className={
                isMobile
                  ? undefined
                  : "w-full px-3 py-2 text-sm border-b border-zinc-100 outline-none"
              }
            />
            <Command.List style={{ maxHeight: "220px", overflowY: "auto", padding: "4px" }}>
              <Command.Empty
                style={isMobile ? { padding: "10px", fontSize: "var(--text-xs)", color: "var(--text-muted)" } : undefined}
                className={isMobile ? undefined : "px-3 py-4 text-sm text-zinc-400 text-center"}
              >
                No models found.
              </Command.Empty>

              {pinned && (
                <Command.Group heading="Current">
                  <ModelItem model={pinned} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                </Command.Group>
              )}
              <Command.Group heading="Free">
                {free.map((m) => (
                  <ModelItem key={m.id} model={m} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                ))}
              </Command.Group>
              <Command.Group heading="Paid">
                {paid.map((m) => (
                  <ModelItem key={m.id} model={m} isMobile={isMobile} onSelect={onChange} setOpen={setOpen} />
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </div>
      )}
    </div>
  );
}

function ModelItem({
  model,
  isMobile,
  onSelect,
  setOpen,
}: {
  model: ModelOption;
  isMobile: boolean;
  onSelect: (id: string) => void;
  setOpen: (open: boolean) => void;
}) {
  return (
    <Command.Item
      value={`${model.id} ${model.name}`}
      onSelect={() => {
        onSelect(model.id);
        setOpen(false);
      }}
      style={
        isMobile
          ? {
              padding: "6px 8px",
              borderRadius: "var(--radius-sm, 4px)",
              fontSize: "var(--text-xs)",
              color: "var(--text)",
              cursor: "pointer",
            }
          : undefined
      }
      className={
        isMobile
          ? undefined
          : "px-3 py-1.5 rounded text-sm text-zinc-700 cursor-pointer data-[selected=true]:bg-emerald-50 data-[selected=true]:text-emerald-700"
      }
    >
      {model.name}
    </Command.Item>
  );
}
