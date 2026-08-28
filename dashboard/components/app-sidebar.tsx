"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Scale, BarChart3, ClipboardList, Bot, Activity, Settings, Zap, Menu, X } from "lucide-react";
import { useState } from "react";

const NAV = [
  { label: "Overview", href: "/", icon: Zap },
  { label: "Memories", href: "/memories", icon: Brain },
  { label: "Decisions", href: "/decisions", icon: Scale },
  { label: "Calibration", href: "/calibration", icon: BarChart3 },
  { label: "Tasks", href: "/tasks", icon: ClipboardList },
  { label: "Drivers", href: "/drivers", icon: Bot },
  { label: "Activity", href: "/activity", icon: Activity },
];

const BOTTOM = [
  { label: "Settings", href: "/settings", icon: Settings },
];

export function AppSidebar({ wsStatus = "disconnected" }: { wsStatus?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close the drawer on route change (mobile). Adjusting state during render
  // when a value changes is React's documented alternative to a setState
  // effect — it re-renders before the browser paints instead of causing a
  // second, cascading render pass.
  const [lastPathname, setLastPathname] = useState(pathname);
  if (pathname !== lastPathname) {
    setLastPathname(pathname);
    setOpen(false);
  }

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setOpen(true)}
        className="fixed top-3.5 left-4 z-50 p-2 rounded-lg bg-surface border border-line shadow-sm lg:hidden"
      >
        <Menu className="w-4 h-4 text-ink-mid" />
      </button>

      {/* Backdrop (mobile) */}
      {open && (
        <div className="fixed inset-0 bg-scrim backdrop-blur-sm z-40 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed lg:relative inset-y-0 left-0 z-50 w-56 h-screen bg-surface border-r border-line flex flex-col py-4 shrink-0 transition-transform duration-200 ${
        open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      }`}>
        <div className="px-5 mb-8 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent-soft flex items-center justify-center relative">
              <Brain className="w-4.5 h-4.5 text-accent" />
              <div className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-surface ${
                wsStatus === "connected" ? "bg-accent" :
                wsStatus === "connecting" ? "bg-warning animate-pulse" :
                "bg-ink-low"
              }`} title={`WebSocket: ${wsStatus}`} />
            </div>
            <span className="text-sm font-semibold text-ink tracking-tight">Life Graph</span>
          </Link>
          <button onClick={() => setOpen(false)} className="p-1 rounded-md hover:bg-surface-3 lg:hidden">
            <X className="w-4 h-4 text-ink-low" />
          </button>
        </div>
        <nav className="flex-1 px-3 space-y-0.5">
          {NAV.map(({ label, href, icon: Icon }) => {
            const active = pathname === href || (href !== "/" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-accent-soft text-accent-text font-medium"
                    : "text-ink-mid hover:text-ink hover:bg-surface-2"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="px-3 pt-2 border-t border-line mt-2">
          {BOTTOM.map(({ label, href, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors ${
                  active ? "bg-accent-soft text-accent-text" : "text-ink-mid hover:text-ink hover:bg-surface-2"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </div>
      </aside>
    </>
  );
}
