"use client";
import Link from "next/link";
import { ChevronRight, Octagon } from "lucide-react";
import { EmptyCard, ErrorCard, LoadingCard, Meta, Row, Section, Stack } from "@/components/mobile/parts";
import {
  useModelHealth,
  type ModelHealthVM,
  type ModelHealthState,
  useAutonomyKillSwitch,
  useToggleAutonomyKillSwitch,
} from "@/lib/mobile-api";

const DOT_COLOR: Record<ModelHealthState, string> = {
  up: "var(--success)",
  cooling: "var(--warning)",
  down: "var(--danger)",
  unknown: "var(--text-subtle)",
};

function relativeTime(epochSeconds: number | null): string | null {
  if (epochSeconds == null) return null;
  const deltaMs = Date.now() - epochSeconds * 1000;
  if (deltaMs < 0) return "just now";
  const seconds = Math.floor(deltaMs / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Title + supporting line, the shape every row on this screen shares. */
function RowText({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <span style={{ minWidth: 0, flex: 1 }}>
      <span style={{ display: "block", fontSize: "var(--size-body)", fontWeight: 600, letterSpacing: "var(--tracking-snug)" }}>
        {title}
      </span>
      <Meta style={{ display: "block", marginTop: "1px" }}>{children}</Meta>
    </span>
  );
}

/** A row that navigates. Three of these were written out longhand before. */
function NavRow({ href, title, detail }: { href: string; title: string; detail: string }) {
  return (
    <Link href={href} style={{ textDecoration: "none", color: "var(--text)" }}>
      <Row>
        <RowText title={title}>{detail}</RowText>
        <ChevronRight width={16} height={16} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
      </Row>
    </Link>
  );
}

function ModelHealthRow({ item }: { item: ModelHealthVM }) {
  const lastSeen = relativeTime(item.lastSuccessAt);
  return (
    <Row style={{ alignItems: "flex-start" }}>
      <span
        aria-hidden
        style={{
          width: "9px",
          height: "9px",
          borderRadius: "50%",
          background: DOT_COLOR[item.state],
          flexShrink: 0,
          marginTop: "5px",
        }}
      />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "var(--size-body)", fontWeight: 600 }}>{item.shortName}</span>
          {lastSeen && <Meta>{lastSeen}</Meta>}
        </span>
        {item.lastError && (
          <span
            style={{
              display: "block",
              fontSize: "var(--size-meta)",
              color: "var(--danger)",
              marginTop: "3px",
              lineHeight: 1.4,
            }}
          >
            {item.lastError}
          </span>
        )}
      </span>
    </Row>
  );
}

function KillSwitchCard() {
  const killSwitch = useAutonomyKillSwitch();
  const toggle = useToggleAutonomyKillSwitch();
  const paused = killSwitch.data?.paused ?? false;
  const pausedAgo =
    paused && killSwitch.data?.pausedAt
      ? relativeTime(Math.floor(new Date(killSwitch.data.pausedAt).getTime() / 1000))
      : null;
  const busy = killSwitch.isLoading || toggle.isPending;

  return (
    <Row
      style={{
        background: paused ? "var(--danger-soft)" : "var(--surface)",
        borderColor: paused ? "var(--danger)" : "var(--border)",
      }}
    >
      <Octagon
        width={18}
        height={18}
        style={{ color: paused ? "var(--danger)" : "var(--text-subtle)", flexShrink: 0 }}
      />
      <RowText title="Autonomous actions">
        {killSwitch.isLoading
          ? "Checking…"
          : paused
            ? `Paused${pausedAgo ? ` ${pausedAgo}` : ""} — nothing will auto-execute`
            : "Running normally — ops/cody can act within their trust level"}
      </RowText>
      <button
        onClick={() => toggle.mutate(!paused)}
        disabled={busy}
        style={{
          flexShrink: 0,
          border: `1px solid ${paused ? "var(--danger)" : "var(--border-strong)"}`,
          borderRadius: "var(--radius-control)",
          background: paused ? "var(--danger)" : "var(--surface-2)",
          color: paused ? "var(--danger-fg)" : "var(--text)",
          fontSize: "var(--size-meta)",
          fontFamily: "inherit",
          fontWeight: 600,
          padding: "7px 12px",
          cursor: busy ? "not-allowed" : "pointer",
          opacity: busy ? 0.6 : 1,
        }}
      >
        {paused ? "Resume" : "Pause"}
      </button>
    </Row>
  );
}

export default function MobileSettings() {
  const modelHealth = useModelHealth();
  const items = modelHealth.data ?? [];

  return (
    <>
      <KillSwitchCard />

      <Stack>
        <NavRow href="/m/schedules" title="Ambient roles" detail="Scout, admin & tutor — schedules and watch-list" />
        <NavRow href="/m/personas" title="Personas" detail="Model, temperature & max tokens per persona" />
        <NavRow
          href="/m/shadow"
          title="Shadow log"
          detail="What autonomous actions would have run — grade good/bad"
        />
      </Stack>

      <Section title="Model health">
        {modelHealth.isLoading ? (
          <LoadingCard label="Loading model health…" />
        ) : modelHealth.isError ? (
          <ErrorCard>Can’t reach model health — is the backend running?</ErrorCard>
        ) : items.length === 0 ? (
          <EmptyCard hint="It fills in the first time a persona calls a model.">
            No model activity recorded yet.
          </EmptyCard>
        ) : (
          <Stack>
            {items.map((item) => (
              <ModelHealthRow key={item.model} item={item} />
            ))}
          </Stack>
        )}
      </Section>
    </>
  );
}
