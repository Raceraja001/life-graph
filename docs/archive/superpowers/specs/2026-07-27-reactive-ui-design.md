# Reactive UI — the mobile PWA feels instant

> **Date:** 2026-07-27
> **Status:** Approved design — ready for implementation planning
> **Scope:** `dashboard/lib/hooks.ts` + `lib/mobile-api.ts` (optimistic mutation), `lib/use-websocket.ts`
> (event map), `components/mobile/mobile-capture.tsx` (honest toasts), `components/mobile/parts.tsx`
> (skeletons), `app/(mobile)/m/memories/page.tsx` + `app/(mobile)/m/page.tsx` (skeletons +
> pull-to-refresh), a new `lib/use-pull-to-refresh.ts`. Frontend-only; deployed at `brain.raceraja001.in`.
> **Roadmap:** memory-quality → notifications → reliability → **reactive UI** → distillation.
> **Note:** overlaps a few mobile files with open PRs #15/#16; resolved at batch-merge time.

## Problem

The mobile PWA feels laggy on the moments that matter:
- **Capture:** hitting send clears the textarea but nothing appears until the full extraction-pipeline
  POST resolves (LLM work, hundreds of ms to seconds) AND a second invalidate→refetch round-trip. The
  capture appears to vanish, then reappear. There is **zero optimistic UI anywhere** in the app.
- **Voice/photo:** the success toast fires the instant the upload returns — *before* the memory
  actually exists (it's created later by the ARQ job). The purpose-built completion events
  (`voice:transcribed` / `image:processed` / `document:imported`) are emitted and reach the browser
  but are **silently dropped** by the frontend event map — so voice/photo results don't refresh live
  and the "success" toast is dishonest.
- **Browsing:** the loading state is a single pulsing "Loading…" box (not content-shaped); there is
  **no pull-to-refresh** on any mobile list.

What already works (keep): the memories list DOES live-refresh on capture via the `MEMORY_PENDING`
WebSocket event; repeat navigation is cached (5-min staleTime, no spinner flash).

## Decisions (locked with user)

- **All four improvements ship:** optimistic capture, honest voice/photo + live completion events,
  content-shaped skeletons, pull-to-refresh.
- **Optimistic card = the typed text as a "saving…" card**, cleanly reconciled by the existing
  invalidate→refetch (no "show both versions" morphing). Rollback + error toast on failure.
- **No new npm dependency** — pull-to-refresh is a small custom touch hook.

## Non-goals (v1)

- No manual React-Query cache surgery to *merge* server results into the optimistic card — the temp
  card is simply replaced by the refetched real memory(ies).
- No optimistic UI for voice/photo/document (those are inherently async background jobs — they get
  honest "processing…" copy + live refresh, not a fake instant card).
- No desktop changes (mobile PWA is the target); shared hooks stay backward-compatible for desktop.
- No offline optimistic reconciliation beyond what exists (the offline queue already handles offline).
- No infinite-scroll / virtualization / new list pagination.

## Architecture

```
Text capture ── useCreateMemory.mutate(content)
   onMutate(content):                          ← instant, before the network
     cancelQueries(["memories"])
     snapshot = getQueryData(["memories"])
     setQueryData(["memories"], prepend {id: temp, content, _optimistic:true, status:"pending"})
     return { snapshot }
   POST /memories/  (slow extraction pipeline runs here)
   onError(_e,_v,ctx): setQueryData(["memories"], ctx.snapshot)   ← rollback + error toast
   onSuccess: invalidateQueries(["memories"])  → refetch replaces temp card with real memory(ies)

Voice/photo ── api.ingest.* (upload+transcribe/OCR sync) → "Uploaded — processing…" toast
   ARQ job later → store() → MEMORY_PENDING (live refresh) + voice:transcribed{memories_created}
   WS EVENT_MAP now maps voice/image/document → invalidate(["memories"]) + surfaces count → toast

Browsing ── loading → <MemoryCardSkeleton> ×N (content-shaped)
            list top + swipe-down → usePullToRefresh → refetch
```

## Components

### 1. Optimistic capture (`lib/hooks.ts` `useCreateMemory`, shared with mobile)

- Add `onMutate` / `onError` / `onSuccess` to the existing `useCreateMemory` mutation:
  - `onMutate(content)`: `await qc.cancelQueries({queryKey:["memories"]})`; snapshot current
    `["memories"]` data; `qc.setQueryData(["memories"], prepend an optimistic item)`. The optimistic
    item matches the shape the list renders (id = `"optimistic-" + Date.now()`, content, tags: [],
    `status: "pending"`, a flag `_optimistic: true`, created_at now). Return `{ snapshot }` as context.
  - `onError(_err,_content,ctx)`: restore `qc.setQueryData(["memories"], ctx.snapshot)`.
  - `onSettled`/`onSuccess`: `qc.invalidateQueries({queryKey:["memories"]})` (+ `["tasks"]` as today).
- The mobile list's mapper (`mapMemory` in `mobile-api.ts`) and card renderer must tolerate the
  optimistic item: render `_optimistic` items with a subtle "saving…" spinner/badge and no
  approve/reject actions. The card key uses the item id (stable temp id).
- Because the list query key is `["memories"]` shared by Home and Memories, the optimistic card shows
  on both surfaces at once.

### 2. Honest voice/photo + live completion events

- `lib/use-websocket.ts` `EVENT_MAP`: add `voice → ["memories"]`, `image → ["memories"]`,
  `document → ["memories"]` so completion events refresh the list live.
- Surface the completion payload: extend `useWebSocket`'s message handler to, on a
  `voice:transcribed`/`image:processed`/`document:imported` event, call an optional callback / emit a
  lightweight app event carrying `memories_created`, so the capture surface can show
  "Voice note → N memories". Simplest wiring: a tiny module-level event emitter
  (`lib/capture-events.ts`) that `useWebSocket` publishes to and `mobile-capture.tsx` subscribes to;
  keeps `useWebSocket` otherwise invalidation-only.
- `mobile-capture.tsx`: change the voice/image/document success toast from the immediate
  "captured" copy to **"Uploaded — processing…"**; on the subsequent completion event, show
  **"Voice note → N memories"** (or "Photo → N memories"). Text capture keeps its optimistic-card flow.

### 3. Content-shaped skeletons (`components/mobile/parts.tsx`)

- Add `MemoryCardSkeleton` — a pulsing block shaped like a memory card (a title bar, 2 body lines, a
  couple of tag pills), using the uzhavu tokens. Add a `SkeletonList({count=4})` helper.
- Replace `LoadingCard` usage on `/m/memories` and the Home "Remembered today" / tasks sections with
  the shaped skeletons (keep `LoadingCard`/`EmptyCard`/`ErrorCard` for other uses).

### 4. Pull-to-refresh (`lib/use-pull-to-refresh.ts` + list pages)

- `usePullToRefresh({ onRefresh, threshold=64 })`: touch handlers (touchstart/touchmove/touchend) that
  only engage when the scroll container is at `scrollTop === 0` and the drag is downward; tracks pull
  distance; on release past `threshold` calls `onRefresh()` (the query `refetch`) and shows a spinner;
  resets. Returns handler props + a `pulling`/`refreshing` state + a pull offset for a follow indicator.
  No dependency — pure React + touch events. Guarded for SSR / non-touch.
- Wire it into `/m/memories` and `/m` (Home): `onRefresh = () => useMobileMemories(...).refetch()`
  (and tasks refetch on Home). Render a small pull indicator (arrow/spinner) at the top that follows
  the drag.

## Failure handling

| Case | Behaviour |
|---|---|
| Capture POST fails | onError rolls back the optimistic card; error toast; textarea content already cleared → error copy notes it (or offer the offline queue as today) |
| Optimistic card + real refetch race | invalidate→refetch replaces the whole list with server truth; temp card (only in cache) disappears; no duplicate |
| Voice job never completes | List still shows via MEMORY_PENDING when store() runs; if truly failed, no memory + no completion toast (honest) |
| Pull-to-refresh on non-touch/desktop | Hook no-ops (guards on touch support); desktop unaffected |
| WS disconnected | Optimistic card + mutation-success invalidate still work; live completion events resume on reconnect |
| Offline capture | Existing offline-queue path unchanged (no optimistic card offline — "Saved offline" toast as today) |

## Verification

1. Manual/build: capture text → a "saving…" card appears instantly (before the POST resolves) →
   reconciles to the real memory; on a forced error → card rolls back + error toast.
2. Voice/photo: toast reads "Uploaded — processing…"; when the job completes, list refreshes live and
   a "→ N memories" toast appears (driven by the completion event).
3. Skeletons: first load of `/m/memories` shows content-shaped skeleton rows, not a single box.
4. Pull-to-refresh: swipe down at top of `/m/memories` → spinner → list refetches.
5. `npm run build` passes; lint zero new; desktop unaffected (shared hooks backward-compatible).
6. Live E2E (batched): on the phone, capture feels instant; voice note shows processing→N; pull-to-refresh works.
