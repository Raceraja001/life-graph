"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BookText, ClipboardCheck, Inbox, MessageCircle, type LucideIcon } from "lucide-react";
import { useApprovals, usePendingMemoryCount } from "@/lib/mobile-api";

interface Tab {
  href: string;
  label: string;
  icon: LucideIcon;
}

const TABS: Tab[] = [
  { href: "/m", label: "Home", icon: Home },
  { href: "/m/memories", label: "Memories", icon: BookText },
  { href: "/m/chat", label: "Ask", icon: MessageCircle },
  { href: "/m/tasks", label: "Tasks", icon: ClipboardCheck },
  { href: "/m/approvals", label: "Approvals", icon: Inbox },
];

export function MobileTabBar() {
  const pathname = usePathname();
  const approvals = useApprovals();
  const openApprovalsCount = approvals.data?.length ?? 0;
  const pendingMemories = usePendingMemoryCount();
  const isActive = (href: string) => (href === "/m" ? pathname === "/m" : pathname.startsWith(href));

  return (
    <nav
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(5, 1fr)",
        borderTop: "1px solid var(--border)",
        background: "var(--surface)",
        padding: "6px 8px calc(6px + env(safe-area-inset-bottom))",
      }}
    >
      {TABS.map(({ href, label, icon: Icon }) => {
        const active = isActive(href);
        const badge =
          href === "/m/approvals" && openApprovalsCount > 0
            ? openApprovalsCount
            : href === "/m/memories" && (pendingMemories.data ?? 0) > 0
              ? pendingMemories.data
              : 0;
        const badgeColor = href === "/m/memories" ? "var(--warning, #b45309)" : "var(--danger)";
        return (
          <Link
            key={href}
            href={href}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "3px",
              padding: "7px 4px",
              minHeight: "48px",
              borderRadius: "var(--radius-md)",
              color: active ? "var(--accent-text)" : "var(--text-subtle)",
              textDecoration: "none",
            }}
          >
            <span style={{ position: "relative", display: "flex" }}>
              <Icon width={18} height={18} strokeWidth={active ? 2.4 : 2} />
              {badge ? (
                <span
                  style={{
                    position: "absolute",
                    top: "-3px",
                    right: "-7px",
                    minWidth: "15px",
                    height: "15px",
                    borderRadius: "var(--radius-pill)",
                    background: badgeColor,
                    color: "#fff",
                    fontSize: "9px",
                    fontWeight: 800,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    paddingInline: "3px",
                  }}
                >
                  {badge}
                </span>
              ) : null}
            </span>
            <span style={{ fontSize: "10px", fontWeight: "var(--fw-bold)" }}>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
