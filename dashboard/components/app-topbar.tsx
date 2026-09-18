"use client";
import { Search, Bell, LogOut } from "lucide-react";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/auth";

const TITLES: Record<string, string> = {
  "/": "Overview",
  "/memories": "Memories",
  "/decisions": "Decisions",
  "/calibration": "Calibration",
  "/tasks": "Tasks",
  "/drivers": "Dev tasks",
  "/activity": "Activity",
  "/settings": "Settings",
};

export function AppTopbar({ onOpenCommand }: { onOpenCommand?: () => void }) {
  const pathname = usePathname();
  const title = TITLES[pathname] || "Life Graph";
  return (
    <header className="h-14 bg-surface/80 backdrop-blur-sm border-b border-line flex items-center justify-between pl-14 pr-6 lg:px-6 shrink-0">
      <h1 className="text-sm font-semibold text-ink">{title}</h1>
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenCommand}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-3 border border-line text-ink-mid text-xs hover:text-ink hover:border-line-strong hover:shadow-sm transition-all"
        >
          <Search className="w-3.5 h-3.5" />
          <span>Search</span>
          <kbd className="ml-2 px-1.5 py-0.5 rounded bg-surface border border-line text-[10px] font-mono text-ink-low">⌘K</kbd>
        </button>
        <button className="relative p-2 rounded-lg text-ink-low hover:text-ink hover:bg-surface-3 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
        <button
          onClick={logout}
          className="p-2 rounded-lg text-ink-low hover:text-danger hover:bg-danger-soft transition-colors"
          title="Logout"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
