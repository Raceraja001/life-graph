# Reactive UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the mobile PWA feel instant — optimistic capture, honest voice/photo feedback with live completion events, content-shaped skeletons, and pull-to-refresh.

**Architecture:** Frontend-only changes in `dashboard/`. Optimistic capture is a React-Query `onMutate`/`onError`/`onSettled` cycle on the shared `useCreateMemory` mutation that prepends a temp card to every `["memories"]` list, rolled back on error and replaced by the refetch. Voice/photo become honest by wiring the already-emitted `voice:transcribed`/`image:processed`/`document:imported` WebSocket events (currently dropped) into the event map plus a tiny module-level emitter that carries `memories_created` to the capture toast. Skeletons and pull-to-refresh are self-contained presentational additions.

**Tech Stack:** Next.js 16 / React 19, `@tanstack/react-query` v5, plain touch events (no new dependency), inline-style design tokens (uzhavu).

## Global Constraints

- **Frontend-only.** Touch only files under `dashboard/`. No backend, no API-contract, no migration changes.
- **No new npm dependency.** Pull-to-refresh is a hand-written touch hook.
- **No JS test runner exists** in `dashboard/` (no jest/vitest, no `test` script). Each task's verification gate is: `npm run build` passes AND `npm run lint` reports zero **new** warnings/errors, plus the task's explicit manual check. Do **not** scaffold a test framework — that is out of scope.
- **Shared hooks stay backward-compatible with desktop.** `useCreateMemory`, `mapMemory`, and `MemoryVM` are consumed by desktop surfaces too; changes must be additive.
- **Design tokens only.** Use existing CSS variables (`var(--surface)`, `var(--border)`, `var(--text-subtle)`, `var(--radius-lg)`, etc.) — no hardcoded colors except where the codebase already does (e.g. the existing `#fef3c7` pending-badge fallback).
- **Run commands from `dashboard/`.** All `npm` commands run in `dashboard/` (the worktree is at `scratchpad/hotfix-wt`, dashboard at `scratchpad/hotfix-wt/dashboard`).
- **Branch:** `feat/reactive-ui` (already checked out, off master). Commit after every task with trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Query-key facts (verified):** the memories list cache key is `["memories", { limit: "…" }]` (mobile) / `["memories", params]` (desktop). Single-memory is `["memories", id]`; pending-count is `["memories", "pending-count"]`. Search is a **separate** key `["memory-search", …]`. The list `queryFn` returns the **raw** backend rows; `mapMemory` runs in React-Query `select`, so any optimistic cache item must be in **raw** shape (not `MemoryVM`).
- **WebSocket message shape (verified):** `{ type: "voice:transcribed" | "image:processed" | "document:imported" | …, payload: {…, memories_created: number}, timestamp, source }`. `data.type` holds the event string; `data.payload.memories_created` holds the count.

---

## File Structure

**Task 1 — Optimistic capture**
- Modify: `dashboard/lib/hooks.ts` (`useCreateMemory` — add optimistic lifecycle)
- Modify: `dashboard/lib/mobile-api.ts` (`MemoryVM` + `mapMemory` — carry `_optimistic`)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx` (render optimistic card as "saving…", suppress approve/reject + sheet)

**Task 2 — Honest voice/photo + live completion events**
- Create: `dashboard/lib/capture-events.ts` (module-level completion emitter)
- Modify: `dashboard/lib/use-websocket.ts` (`EVENT_MAP` + emit completion detail)
- Modify: `dashboard/components/mobile/mobile-capture.tsx` (processing → "→ N memories" toasts; subscribe; drop redundant list invalidation)

**Task 3 — Content-shaped skeletons**
- Modify: `dashboard/components/mobile/parts.tsx` (`MemoryCardSkeleton`, `SkeletonList`)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx` (replace `LoadingCard`)
- Modify: `dashboard/app/(mobile)/m/page.tsx` (replace `LoadingCard` for memories + tasks)

**Task 4 — Pull-to-refresh**
- Create: `dashboard/lib/use-pull-to-refresh.ts` (touch hook)
- Modify: `dashboard/components/mobile/mobile-shell.tsx` (mark the scroll container)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx` (wire refetch + indicator)
- Modify: `dashboard/app/(mobile)/m/page.tsx` (wire refetch + indicator)

---

### Task 1: Optimistic capture

Add an optimistic-update lifecycle to the shared `useCreateMemory` mutation so a typed capture appears as a "saving…" card instantly, is rolled back on error, and is replaced by the refetch on completion. Teach the memory view-model and the mobile memories list to render that temp card safely (no approve/reject, no detail sheet).

**Files:**
- Modify: `dashboard/lib/hooks.ts:44-46`
- Modify: `dashboard/lib/mobile-api.ts:9-19` (interface) and `:38-52` (mapper)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx:54-161`

**Interfaces:**
- Consumes: `api.memories.create(content) -> Promise<any>`; React-Query `useQueryClient`.
- Produces:
  - `useCreateMemory()` — unchanged call site signature (`const m = useCreateMemory(); m.mutateAsync(content)`), now with optimistic side effects on the `["memories"]` cache.
  - `MemoryVM._optimistic?: boolean` — consumed by Task 3/4 renderers and this task's card.
  - Optimistic raw cache item shape: `{ id: "optimistic-<ts>", content, tags: [], status: "pending", importance: 0.5, source: "capture", created_at: <iso>, _optimistic: true }`.

- [ ] **Step 1: Add the optimistic lifecycle to `useCreateMemory`**

In `dashboard/lib/hooks.ts`, replace the existing three-line `useCreateMemory` (lines 44-46):

```ts
export function useCreateMemory() {
  return useMutation({ mutationFn: (content: string) => api.memories.create(content) });
}
```

with:

```ts
export function useCreateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => api.memories.create(content),
    onMutate: async (content: string) => {
      // Instant optimistic card: prepend to every cached memories list.
      await qc.cancelQueries({ queryKey: ["memories"] });
      const snapshots = qc.getQueriesData<any>({ queryKey: ["memories"] });
      const optimistic = {
        id: "optimistic-" + Date.now(),
        content,
        tags: [],
        status: "pending",
        importance: 0.5,
        source: "capture",
        created_at: new Date().toISOString(),
        _optimistic: true,
      };
      // Only touch list caches (arrays); leave single-memory objects and
      // the pending-count number untouched.
      qc.setQueriesData<any>({ queryKey: ["memories"] }, (old: any) =>
        Array.isArray(old) ? [optimistic, ...old] : old
      );
      return { snapshots };
    },
    onError: (_err, _content, ctx) => {
      // Roll every list back to its pre-mutation snapshot.
      ctx?.snapshots?.forEach(([key, data]: [readonly unknown[], unknown]) =>
        qc.setQueryData(key, data)
      );
    },
    onSettled: () => {
      // Refetch replaces the temp card with server truth (success)
      // or reconciles after a rollback (error).
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
```

`useQueryClient` and `useMutation` are already imported at the top of `hooks.ts` (line 2). No new imports.

- [ ] **Step 2: Carry `_optimistic` through the memory view-model**

In `dashboard/lib/mobile-api.ts`, add the flag to the `MemoryVM` interface. Change the closing lines of the interface (currently ending at line 18-19):

```ts
  properties?: Record<string, unknown>;
  status: string; // "pending" | "active" | ...
}
```

to:

```ts
  properties?: Record<string, unknown>;
  status: string; // "pending" | "active" | ...
  _optimistic?: boolean; // true = local optimistic card, not yet persisted
}
```

Then in `mapMemory` (the `return { … }` block ending around line 51), add the mapping right after the `status` line:

```ts
    properties: raw?.properties,
    status: raw?.status ?? "active",
    _optimistic: raw?._optimistic === true,
  };
```

- [ ] **Step 3: Render the optimistic card safely on the memories list**

In `dashboard/app/(mobile)/m/memories/page.tsx`:

(a) Make the card non-interactive when optimistic — change the `<button onClick={() => setSelected(m)}` (line 59) to:

```tsx
              <button
                onClick={() => { if (!m._optimistic) setSelected(m); }}
```

and in that button's inline `style`, change the `cursor` line (line 68) from `cursor: "pointer",` to:

```tsx
                  cursor: m._optimistic ? "default" : "pointer",
                  opacity: m._optimistic ? 0.7 : 1,
```

(b) Replace the pending badge so optimistic items read "saving…" instead of "pending". Change the badge block (lines 75-88) from `{m.status === "pending" && ( … pending … )}` to:

```tsx
                  {(m._optimistic || m.status === "pending") && (
                    <span
                      style={{
                        background: "var(--warning-soft, #fef3c7)",
                        color: "var(--warning, #b45309)",
                        borderRadius: 999,
                        padding: "1px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      {m._optimistic ? "saving…" : "pending"}
                    </span>
                  )}
```

(c) Suppress the approve/reject actions for optimistic items. Change the actions guard (line 120) from `{m.status === "pending" && (` to:

```tsx
              {m.status === "pending" && !m._optimistic && (
```

- [ ] **Step 4: Build + lint**

Run (from `dashboard/`):
```bash
npm run build
npm run lint
```
Expected: build succeeds; lint reports zero new warnings. If lint flags the `readonly unknown[]` tuple destructure, it is a type-only annotation and must still pass — fix any real type error, do not suppress.

- [ ] **Step 5: Manual verification (dev server)**

Run `npm run dev`, open `/m/memories` in a browser (mobile viewport). In the capture box on `/m`, type "test optimistic" and hit Capture. Confirm:
  - A card with "saving…" appears at the top of the memories list **before** the network settles (throttle to Slow 3G in devtools to see it clearly).
  - It has no Approve/Reject buttons and does not open the detail sheet on tap.
  - When the POST resolves, the temp card is replaced by the real memory (now with normal "pending" badge + approve/reject).
  - Force an error (devtools → offline while online-flag still true is hard; instead temporarily point `NEXT_PUBLIC_API_URL` at a dead port) → the temp card disappears (rollback) and the existing error toast shows.

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/hooks.ts dashboard/lib/mobile-api.ts "dashboard/app/(mobile)/m/memories/page.tsx"
git commit -m "feat(mobile): optimistic capture card with rollback

Typed captures appear instantly as a 'saving…' card via useCreateMemory
onMutate/onError/onSettled; temp card carries _optimistic so the memories
list skips approve/reject and the detail sheet until the refetch reconciles.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Honest voice/photo + live completion events

Wire the already-emitted `voice:transcribed`/`image:processed`/`document:imported` WebSocket events (currently silently dropped by the frontend event map) into (a) cache invalidation so voice/photo results refresh live, and (b) a tiny module-level emitter carrying `memories_created` so the capture surface can replace its dishonest instant "captured" toast with "Uploaded — processing…" → "Voice note → N memories".

**Files:**
- Create: `dashboard/lib/capture-events.ts`
- Modify: `dashboard/lib/use-websocket.ts:8-20` (EVENT_MAP) and `:54-72` (message handler)
- Modify: `dashboard/components/mobile/mobile-capture.tsx`

**Interfaces:**
- Consumes: WS `data.type` (event string) + `data.payload.memories_created` (number).
- Produces:
  - `capture-events.ts`: `type CaptureDetail = { source: "voice" | "image" | "document"; memoriesCreated: number }`; `emitCaptureComplete(detail: CaptureDetail): void`; `onCaptureComplete(cb: (d: CaptureDetail) => void): () => void` (returns an unsubscribe).

- [ ] **Step 1: Create the completion emitter**

Create `dashboard/lib/capture-events.ts`:

```ts
// Tiny module-level pub/sub bridging WebSocket capture-completion events
// (voice:transcribed / image:processed / document:imported) to the capture
// surface, so it can show an honest "→ N memories" toast when the ARQ job
// finishes. Kept separate so useWebSocket stays otherwise invalidation-only.

export type CaptureSource = "voice" | "image" | "document";
export interface CaptureDetail {
  source: CaptureSource;
  memoriesCreated: number;
}

const listeners = new Set<(d: CaptureDetail) => void>();

export function emitCaptureComplete(detail: CaptureDetail): void {
  listeners.forEach((fn) => fn(detail));
}

/** Subscribe to capture-completion events. Returns an unsubscribe function. */
export function onCaptureComplete(cb: (d: CaptureDetail) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
```

- [ ] **Step 2: Map the completion events + emit their detail in `useWebSocket`**

In `dashboard/lib/use-websocket.ts`, extend `EVENT_MAP` (the object at lines 8-20) by adding three entries (place them after the `"memory"` line):

```ts
  "memory":       ["memories"],
  "voice":        ["memories"],
  "image":        ["memories"],
  "document":     ["memories"],
```

Then add the emitter import at the top (after the existing imports, lines 1-3):

```ts
import { emitCaptureComplete, type CaptureSource } from "./capture-events";
```

Finally, in the `ws.onmessage` handler, surface the completion count. Replace the `for (const [prefix, keys] …)` loop body (lines 62-67) so a matched voice/image/document event also emits its detail:

```ts
        const type: string = data.type || "";
        // Capture-completion events additionally carry a memory count.
        const captureSrc: CaptureSource | null =
          type.startsWith("voice") ? "voice" :
          type.startsWith("image") ? "image" :
          type.startsWith("document") ? "document" : null;
        if (captureSrc) {
          const count = Number(data?.payload?.memories_created ?? 0);
          emitCaptureComplete({ source: captureSrc, memoriesCreated: count });
        }
        // Only invalidate if we recognize the event type
        for (const [prefix, keys] of Object.entries(EVENT_MAP)) {
          if (type.startsWith(prefix)) {
            keys.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
            return; // matched, done
          }
        }
```

(The `const type: string = data.type || "";` line already exists at line 60 — replace from that line through the loop so `type` is declared once, before the capture-source check.)

- [ ] **Step 3: Honest toasts + subscription in `mobile-capture.tsx`**

In `dashboard/components/mobile/mobile-capture.tsx`:

(a) Add imports (after line 7 `import { useRecorder }`):

```ts
import { useEffect } from "react";
import { onCaptureComplete, type CaptureSource } from "@/lib/capture-events";
```
(`useEffect` — merge into the existing `react` import on line 2 instead of a second import: change line 2 to `import { useEffect, useRef, useState, type CSSProperties } from "react";`.)

(b) Extend the `Result` union (lines 36-40) to include the async states:

```ts
type Result =
  | { kind: "captured"; routedTo: string }
  | { kind: "queued" }
  | { kind: "processing"; source: CaptureSource }
  | { kind: "done-async"; source: CaptureSource; count: number }
  | { kind: "error"; message?: string }
  | null;

const SOURCE_LABEL: Record<CaptureSource, string> = {
  voice: "Voice note",
  image: "Photo",
  document: "Document",
};
```

(c) Change `afterIngest` (lines 60-64) to set the honest "processing" state and to stop the now-redundant memories/tasks invalidation there is fine to keep for tasks, but the completion event handles memories. Replace it with:

```ts
  const afterIngest = (source: CaptureSource) => {
    setResult({ kind: "processing", source });
    // The memories list refreshes live on the completion WS event; still
    // nudge tasks in case the capture routed to one.
    qc.invalidateQueries({ queryKey: ["tasks"] });
  };
```

Update its three call sites to pass the source enum instead of a prose label:
  - line 77 `afterIngest("voice memory")` → `afterIngest("voice")`
  - line 98 `afterIngest("document")` → `afterIngest("document")`
  - line 101 `afterIngest("photo memory")` → `afterIngest("image")`

(d) Subscribe to completion events. Add, immediately after the `const [result, setResult] = useState<Result>(null);` line (line 52):

```ts
  useEffect(() => {
    return onCaptureComplete(({ source, memoriesCreated }) => {
      setResult({ kind: "done-async", source, count: memoriesCreated });
    });
  }, []);
```

(e) Simplify the text `submit()` path — the optimistic hook (Task 1) now owns memories/tasks invalidation, so drop the manual invalidations there. In `submit` (lines 123-127) change:

```ts
    try {
      const res = await route.mutateAsync(content);
      setResult({ kind: "captured", routedTo: routedTarget(res, fallbackKind) });
      qc.invalidateQueries({ queryKey: ["memories"] });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch {
```

to:

```ts
    try {
      const res = await route.mutateAsync(content);
      setResult({ kind: "captured", routedTo: routedTarget(res, fallbackKind) });
    } catch {
```

(f) Render the two new toast states. After the existing `{result?.kind === "queued" && ( … )}` block (ends line 276), add:

```tsx
      {result?.kind === "processing" && (
        <Toast bg="var(--surface-2)" fg="var(--text-muted)">
          {SOURCE_LABEL[result.source]} uploaded — processing…
        </Toast>
      )}
      {result?.kind === "done-async" && (
        <Toast bg="var(--success-soft)" fg="var(--success)">
          {SOURCE_LABEL[result.source]} → {result.count} {result.count === 1 ? "memory" : "memories"}
        </Toast>
      )}
```

- [ ] **Step 4: Build + lint**

```bash
npm run build
npm run lint
```
Expected: pass, zero new warnings. Confirm no unused-import or unused-var (`qc` is still used by `afterIngest`).

- [ ] **Step 5: Manual verification**

With the full stack running (or on the deployed VM during batch E2E), on `/m`:
  - Record a voice note → toast reads "Voice note uploaded — processing…" immediately (not "captured").
  - When the ARQ ingest job completes, the memories list refreshes live **and** the toast becomes "Voice note → N memories".
  - Repeat with a photo (Camera) → "Photo uploaded — processing…" → "Photo → N memories".
  (If the worker/WS isn't reachable in local dev, verify at least the build + that the immediate toast copy changed; full live check is part of the batched E2E.)

- [ ] **Step 6: Commit**

```bash
git add dashboard/lib/capture-events.ts dashboard/lib/use-websocket.ts dashboard/components/mobile/mobile-capture.tsx
git commit -m "feat(mobile): honest voice/photo feedback + live completion events

Wire the dropped voice:transcribed/image:processed/document:imported events
into the WS event map (live list refresh) and a module-level emitter carrying
memories_created; capture toast now shows 'processing…' then '→ N memories'
instead of a premature 'captured'.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Content-shaped skeletons

Replace the single pulsing "Loading…" box with skeleton rows shaped like real memory cards, on `/m/memories` and the Home memories + tasks sections.

**Files:**
- Modify: `dashboard/components/mobile/parts.tsx` (add after `LoadingCard`, ~line 21)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx:48-49`
- Modify: `dashboard/app/(mobile)/m/page.tsx:81-82` (tasks) and `:100-101` (memories)

**Interfaces:**
- Consumes: nothing new.
- Produces: `MemoryCardSkeleton()` and `SkeletonList({ count?: number })` exported from `parts.tsx`.

- [ ] **Step 1: Add the skeleton components**

In `dashboard/components/mobile/parts.tsx`, add after the `LoadingCard` function (after line 21, before `EmptyCard`):

```tsx
export function MemoryCardSkeleton() {
  const bar = (w: string, h = 12): CSSProperties => ({
    width: w,
    height: h,
    borderRadius: "var(--radius-sm, 6px)",
    background: "var(--surface-3)",
  });
  return (
    <div
      className="animate-pulse"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div style={bar("85%")} />
      <div style={bar("60%")} />
      <div style={{ display: "flex", gap: "6px", marginTop: "2px" }}>
        <div style={bar("52px", 19)} />
        <div style={bar("44px", 19)} />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {Array.from({ length: count }, (_, i) => (
        <MemoryCardSkeleton key={i} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Use skeletons on `/m/memories`**

In `dashboard/app/(mobile)/m/memories/page.tsx`:
  - Add `SkeletonList` to the import from `@/components/mobile/parts` (line 3): `import { LoadingCard, EmptyCard, ErrorCard, SkeletonList } from "@/components/mobile/parts";`
  - Replace the loading branch (lines 48-49) from `<LoadingCard label={searching ? "Searching…" : "Loading memories…"} />` to:

```tsx
      {active.isLoading ? (
        <SkeletonList count={5} />
```

  - `LoadingCard` may now be unused on this page — if lint flags it, drop it from the import.

- [ ] **Step 3: Use skeletons on Home**

In `dashboard/app/(mobile)/m/page.tsx`:
  - Add `SkeletonList` to the parts import (line 5): `import { SectionEyebrow, TaskRow, LoadingCard, EmptyCard, ErrorCard, SkeletonList } from "@/components/mobile/parts";`
  - Tasks section: replace `tasks.isLoading ? ( <LoadingCard label="Loading tasks…" /> )` (lines 81-82) with `tasks.isLoading ? ( <SkeletonList count={2} /> )`.
  - Memories section: replace `memories.isLoading ? ( <LoadingCard label="Loading memories…" /> )` (lines 100-101) with `memories.isLoading ? ( <SkeletonList count={3} /> )`.
  - If `LoadingCard` is now unused on this page, drop it from the import.

- [ ] **Step 4: Build + lint**

```bash
npm run build
npm run lint
```
Expected: pass. Resolve any unused-import warning for `LoadingCard`.

- [ ] **Step 5: Manual verification**

`npm run dev`, hard-reload `/m/memories` (clear React-Query cache by reloading) with network throttled: the first paint shows 5 card-shaped pulsing skeletons (title bar + 2 lines + 2 tag pills), not one centered "Loading…" box. Same on `/m` for the Today and Remembered-today sections.

- [ ] **Step 6: Commit**

```bash
git add dashboard/components/mobile/parts.tsx "dashboard/app/(mobile)/m/memories/page.tsx" "dashboard/app/(mobile)/m/page.tsx"
git commit -m "feat(mobile): content-shaped loading skeletons

Add MemoryCardSkeleton + SkeletonList and use them for the memories list
and Home sections instead of a single 'Loading…' box.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Pull-to-refresh

Add a dependency-free touch hook that, when the mobile scroll container is at the top and the user drags down past a threshold, calls a refetch and shows a follow indicator. Wire it into `/m/memories` and `/m`.

**Files:**
- Create: `dashboard/lib/use-pull-to-refresh.ts`
- Modify: `dashboard/components/mobile/mobile-shell.tsx:205-216` (mark scroll container)
- Modify: `dashboard/app/(mobile)/m/memories/page.tsx`
- Modify: `dashboard/app/(mobile)/m/page.tsx`

**Interfaces:**
- Consumes: a scroll container marked with `data-scroll-root` (the mobile `<main>`).
- Produces: `usePullToRefresh({ onRefresh, threshold? }): { pulling: boolean; refreshing: boolean; distance: number }` — a hook that self-attaches touch listeners to the `[data-scroll-root]` element and drives an indicator the page renders.

- [ ] **Step 1: Mark the scroll container**

In `dashboard/components/mobile/mobile-shell.tsx`, add `data-scroll-root` to the `<main>` element (line 205). Change:

```tsx
      <main
        style={{
```

to:

```tsx
      <main
        data-scroll-root
        style={{
```

- [ ] **Step 2: Write the hook**

Create `dashboard/lib/use-pull-to-refresh.ts`:

```ts
"use client";
import { useEffect, useRef, useState } from "react";

interface Options {
  onRefresh: () => void | Promise<unknown>;
  threshold?: number;
}

/**
 * Pull-to-refresh for the mobile scroll container ([data-scroll-root]).
 * Engages only when that container is scrolled to the top and the drag is
 * downward. No dependency; guards for SSR / non-touch. Returns indicator state.
 */
export function usePullToRefresh({ onRefresh, threshold = 64 }: Options) {
  const [distance, setDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);
  const refreshingRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || !("ontouchstart" in window)) return;
    const el = document.querySelector<HTMLElement>("[data-scroll-root]");
    if (!el) return;

    const onStart = (e: TouchEvent) => {
      if (el.scrollTop <= 0 && !refreshingRef.current) {
        startY.current = e.touches[0].clientY;
      } else {
        startY.current = null;
      }
    };
    const onMove = (e: TouchEvent) => {
      if (startY.current === null) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy <= 0) {
        setDistance(0);
        return;
      }
      // Rubber-band: dampen the pull so it feels physical.
      setDistance(Math.min(dy * 0.5, threshold * 1.5));
    };
    const onEnd = async () => {
      if (startY.current === null) return;
      const pulled = distanceRef.current;
      startY.current = null;
      setDistance(0);
      if (pulled >= threshold && !refreshingRef.current) {
        refreshingRef.current = true;
        setRefreshing(true);
        try {
          await onRefresh();
        } finally {
          refreshingRef.current = false;
          setRefreshing(false);
        }
      }
    };

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: true });
    el.addEventListener("touchend", onEnd);
    el.addEventListener("touchcancel", onEnd);
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
    // onRefresh identity may change each render; threshold is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold]);

  // Keep a ref of the live distance for the touchend closure.
  const distanceRef = useRef(0);
  distanceRef.current = distance;

  return { pulling: distance > 0, refreshing, distance };
}
```

Note: `distanceRef` is declared after the effect but hoisted usage inside `onEnd` reads `distanceRef.current` at call time (after the ref exists), which is safe because the listeners fire well after mount. Keep the `distanceRef` lines exactly where shown.

- [ ] **Step 3: A small pull indicator + wire into `/m/memories`**

In `dashboard/app/(mobile)/m/memories/page.tsx`:
  - Import the hook (after the parts import): `import { usePullToRefresh } from "@/lib/use-pull-to-refresh";`
  - Inside the component, after the `const resolve = useResolveMemory();` line, add:

```tsx
  const { refreshing, distance } = usePullToRefresh({
    onRefresh: () => (searching ? search.refetch() : list.refetch()),
  });
```

  - Render an indicator at the very top of the returned fragment, immediately after the opening `<>` (before the `<input type="search" …>`):

```tsx
      {(distance > 0 || refreshing) && (
        <div
          role="status"
          style={{
            height: refreshing ? 28 : distance,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--text-subtle)",
            fontSize: "var(--text-2xs)",
            overflow: "hidden",
            transition: refreshing ? "height 0.15s" : undefined,
          }}
        >
          {refreshing ? "Refreshing…" : distance >= 64 ? "Release to refresh" : "Pull to refresh"}
        </div>
      )}
```

- [ ] **Step 4: Wire into Home `/m`**

In `dashboard/app/(mobile)/m/page.tsx`:
  - Import the hook: `import { usePullToRefresh } from "@/lib/use-pull-to-refresh";`
  - After the `const memories = useMobileMemories(20);` line, add:

```tsx
  const { refreshing, distance } = usePullToRefresh({
    onRefresh: async () => {
      await Promise.all([tasks.refetch(), memories.refetch()]);
    },
  });
```

  - Render the same indicator block (copy from Task 4 Step 3) immediately after the opening `<>` of the returned fragment, before `<MobileCapture />`.

- [ ] **Step 5: Build + lint**

```bash
npm run build
npm run lint
```
Expected: pass. The `eslint-disable-next-line react-hooks/exhaustive-deps` in the hook is intentional and should silence the deps warning; if a different lint rule fires, fix it properly.

- [ ] **Step 6: Manual verification**

On a touch device or Chrome devtools device-emulation (touch enabled), open `/m/memories`, scroll to the very top, then drag down: the "Pull to refresh" indicator follows the drag, flips to "Release to refresh" past the threshold, and on release shows "Refreshing…" while the list refetches. On desktop (no touch) the hook no-ops and nothing renders. Repeat on `/m`.

- [ ] **Step 7: Commit**

```bash
git add dashboard/lib/use-pull-to-refresh.ts dashboard/components/mobile/mobile-shell.tsx "dashboard/app/(mobile)/m/memories/page.tsx" "dashboard/app/(mobile)/m/page.tsx"
git commit -m "feat(mobile): pull-to-refresh on memories + home

Dependency-free touch hook attached to the mobile scroll container; drag
down at top past threshold refetches the list(s) with a follow indicator.
No-ops on non-touch/desktop.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification (whole branch)

After all four tasks:

1. `npm run build` and `npm run lint` both clean from `dashboard/`.
2. Grep sanity: no remaining `LoadingCard` on pages that were meant to switch (only intentional uses remain); `voice`/`image`/`document` present in `EVENT_MAP`.
3. Desktop unaffected: load the desktop dashboard, confirm memory capture + list still work (shared `useCreateMemory`/`mapMemory` are backward-compatible; optimistic card also appears on desktop lists — acceptable).
4. Batched live E2E (deferred to the user's deploy call): on the phone at `brain.raceraja001.in` — capture feels instant; voice note shows "processing…" → "→ N memories"; skeletons on first load; pull-to-refresh works.

## Notes for the batch merge

This branch overlaps a few mobile files with open PRs #15 (memory-quality) and #16 (notifications): `mobile-capture.tsx`, `app/(mobile)/m/page.tsx`, `lib/mobile-api.ts`, `sw.js` (untouched here). Resolve at batch-merge time — the changes here are additive (new toast states, new event-map entries, new exports) and should merge cleanly, but re-run `npm run build` after each merge.
