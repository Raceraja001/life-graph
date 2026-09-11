"use client";
import { useEffect } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import {
  Brain, Scale, BarChart3, ClipboardList, Bot, Activity,
  Settings, Zap, Search, MessageSquare, Plus, ArrowRight,
} from "lucide-react";

const NAVIGATION = [
  { label: "Overview", href: "/", icon: Zap, keywords: "home dashboard" },
  { label: "Memories", href: "/memories", icon: Brain, keywords: "knowledge search" },
  { label: "Decisions", href: "/decisions", icon: Scale, keywords: "choices options" },
  { label: "Calibration", href: "/calibration", icon: BarChart3, keywords: "predictions accuracy brier" },
  { label: "Tasks", href: "/tasks", icon: ClipboardList, keywords: "agents jobs kanban" },
  { label: "Drivers", href: "/drivers", icon: Bot, keywords: "agents performance cost" },
  { label: "Activity", href: "/activity", icon: Activity, keywords: "events feed log" },
  { label: "Settings", href: "/settings", icon: Settings, keywords: "config api" },
];

const ACTIONS = [
  { label: "Capture a thought", action: "capture", icon: MessageSquare, keywords: "note capture write" },
  { label: "Make a decision", action: "decision", icon: Plus, keywords: "decide choose" },
  { label: "Challenge an idea", action: "challenge", icon: Scale, keywords: "adversarial review" },
  { label: "Search memories", action: "search", icon: Search, keywords: "find lookup" },
];

export function CommandPalette({ open, onOpenChange, onAction }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAction?: (action: string) => void;
}) {
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-scrim backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      {/* Dialog */}
      <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg">
        <Command
          className="bg-surface rounded-2xl border border-line shadow-2xl shadow-ink/10 overflow-hidden"
          onKeyDown={(e) => { if (e.key === "Escape") onOpenChange(false); }}
        >
          <div className="flex items-center gap-2 px-4 border-b border-line">
            <Search className="w-4 h-4 text-ink-low shrink-0" />
            <Command.Input
              placeholder="Type a command or search..."
              className="w-full py-3.5 text-sm text-ink placeholder-ink-low bg-transparent outline-none"
              autoFocus
            />
            <kbd className="px-1.5 py-0.5 rounded bg-surface-3 border border-line text-[10px] font-mono text-ink-low shrink-0">ESC</kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-8 text-center text-sm text-ink-low">
              No results found.
            </Command.Empty>

            <Command.Group heading="Navigate" className="mb-1">
              {NAVIGATION.map(({ label, href, icon: Icon, keywords }) => (
                <Command.Item
                  key={href}
                  value={`${label} ${keywords}`}
                  onSelect={() => { router.push(href); onOpenChange(false); }}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-ink cursor-pointer data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent-text transition-colors"
                >
                  <Icon className="w-4 h-4 text-ink-low data-[selected=true]:text-accent" />
                  <span>{label}</span>
                  <ArrowRight className="w-3 h-3 text-ink-low ml-auto" />
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Separator className="h-px bg-surface-3 my-1" />

            <Command.Group heading="Actions" className="mb-1">
              {ACTIONS.map(({ label, action, icon: Icon, keywords }) => (
                <Command.Item
                  key={action}
                  value={`${label} ${keywords}`}
                  onSelect={() => { onAction?.(action); onOpenChange(false); }}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-ink cursor-pointer data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent-text transition-colors"
                >
                  <Icon className="w-4 h-4 text-ink-low" />
                  <span>{label}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>

          <div className="flex items-center gap-4 px-4 py-2.5 border-t border-line text-[10px] text-ink-low">
            <span><kbd className="px-1 py-0.5 rounded bg-surface-3 font-mono">↑↓</kbd> navigate</span>
            <span><kbd className="px-1 py-0.5 rounded bg-surface-3 font-mono">↵</kbd> select</span>
            <span><kbd className="px-1 py-0.5 rounded bg-surface-3 font-mono">esc</kbd> close</span>
          </div>
        </Command>
      </div>
    </div>
  );
}
