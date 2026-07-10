// ─────────────────────────────────────────────────────────────
// Life Graph SDK v1.0 — React Hooks
// ─────────────────────────────────────────────────────────────
//
// Optional React integration. Import from '@life-graph/sdk/react'
// or directly: import { useBrain, useSearch } from '@life-graph/sdk'
//
// These hooks assume React 18+ is available in the consumer's
// project. The SDK itself has zero runtime dependencies — React
// is a peer dependency only.
// ─────────────────────────────────────────────────────────────

// NOTE: We reference React types via global namespace so the SDK
// itself doesn't need React as a dependency. Consumers must have
// React installed.

/* eslint-disable @typescript-eslint/no-explicit-any */

import { LifeGraph } from './client'
import type {
  Memory,
  SearchResult,
  Stats,
  Session,
  Intention,
  LifeGraphConfig,
} from './types'

// ── Tiny React import shim ─────────────────────────────────────
// We dynamically import React so this module doesn't hard-fail
// when React isn't installed (the hooks simply won't work).

let React: any

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  React = require('react')
} catch {
  // React not available — hooks will throw at call-time
}

function ensureReact(): void {
  if (!React) {
    throw new Error(
      '@life-graph/sdk React hooks require React 18+ as a peer dependency. ' +
        'Install it with: npm install react',
    )
  }
}

// ── Singleton client ───────────────────────────────────────────

let _client: LifeGraph | null = null

/**
 * Initialize the shared LifeGraph client used by all hooks.
 *
 * Call this once at the top of your app (e.g. in a provider or layout).
 * The `tenantId` field is **required** in the configuration.
 *
 * @param config - LifeGraph connection configuration.
 * @returns The initialized client instance.
 *
 * @example
 * ```tsx
 * import { initLifeGraph } from '@life-graph/sdk'
 *
 * initLifeGraph({
 *   apiUrl: 'https://api.lifegraph.app',
 *   apiKey: 'lg_live_abc123',
 *   tenantId: 'tenant-42',
 * })
 * ```
 */
export function initLifeGraph(config: LifeGraphConfig): LifeGraph {
  _client = new LifeGraph(config)
  return _client
}

// ── Hooks ──────────────────────────────────────────────────────

/**
 * Returns the shared LifeGraph client instance.
 *
 * @throws If `initLifeGraph()` has not been called.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const brain = useBrain()
 *   // Use brain.remember(), brain.search(), etc.
 * }
 * ```
 */
export function useBrain(): LifeGraph {
  ensureReact()
  if (!_client) {
    throw new Error(
      'LifeGraph client not initialized. Call initLifeGraph({ apiUrl, tenantId }) first.',
    )
  }
  return _client
}

/**
 * Reactive semantic search hook.
 *
 * Automatically re-runs the search when `query` changes.
 * Returns `{ results, loading, error }`.
 *
 * The SDK automatically unwraps the `{ data }` response envelope,
 * so the hook receives the unwrapped search result directly.
 *
 * @param query - The search query string. Pass empty string to skip.
 * @param limit - Maximum results. Defaults to 10.
 *
 * @example
 * ```tsx
 * function SearchBox() {
 *   const [q, setQ] = useState('')
 *   const { results, loading } = useSearch(q)
 *
 *   return (
 *     <div>
 *       <input value={q} onChange={e => setQ(e.target.value)} />
 *       {loading && <p>Searching…</p>}
 *       <pre>{JSON.stringify(results, null, 2)}</pre>
 *     </div>
 *   )
 * }
 * ```
 */
export function useSearch(
  query: string,
  limit = 10,
): { results: SearchResult | null; loading: boolean; error: Error | null } {
  ensureReact()

  const { useState, useEffect } = React

  const [results, setResults] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (!query.trim() || !_client) {
      setResults(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    _client
      .search(query, { limit })
      .then((res: SearchResult) => {
        if (!cancelled) setResults(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [query, limit])

  return { results, loading, error }
}

/**
 * Reactive memory list hook.
 *
 * Fetches all memories on mount and provides a `refresh` function.
 * The SDK automatically unwraps the `{ data }` response envelope.
 *
 * @example
 * ```tsx
 * function MemoryList() {
 *   const { memories, loading, refresh } = useMemories()
 *   return (
 *     <div>
 *       <button onClick={refresh}>Refresh</button>
 *       {memories.map(m => <p key={m.id}>{m.content}</p>)}
 *     </div>
 *   )
 * }
 * ```
 */
export function useMemories(): {
  memories: Memory[]
  loading: boolean
  error: Error | null
  refresh: () => void
} {
  ensureReact()

  const { useState, useEffect, useCallback } = React

  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(() => setTick((t: number) => t + 1), [])

  useEffect(() => {
    if (!_client) return

    let cancelled = false
    setLoading(true)
    setError(null)

    _client
      .memories()
      .then((res: Memory[]) => {
        if (!cancelled) setMemories(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { memories, loading, error, refresh }
}

/**
 * Reactive system stats hook.
 *
 * Fetches stats on mount and provides a `refresh` function.
 * The SDK automatically unwraps the `{ data }` response envelope.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { stats, loading } = useStats()
 *   if (loading || !stats) return <p>Loading…</p>
 *   return <p>{stats.memory_count} memories</p>
 * }
 * ```
 */
export function useStats(): {
  stats: Stats | null
  loading: boolean
  error: Error | null
  refresh: () => void
} {
  ensureReact()

  const { useState, useEffect, useCallback } = React

  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(() => setTick((t: number) => t + 1), [])

  useEffect(() => {
    if (!_client) return

    let cancelled = false
    setLoading(true)
    setError(null)

    _client
      .stats()
      .then((res: Stats) => {
        if (!cancelled) setStats(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { stats, loading, error, refresh }
}

/**
 * Reactive sessions hook.
 *
 * Fetches recent sessions on mount and provides a `refresh` function.
 * The SDK automatically unwraps the `{ data }` response envelope.
 *
 * @param limit - Maximum number of sessions to fetch. Defaults to 20.
 *
 * @example
 * ```tsx
 * function SessionList() {
 *   const { sessions, loading, refresh } = useSessions(10)
 *   return (
 *     <div>
 *       <button onClick={refresh}>Refresh</button>
 *       {sessions.map(s => (
 *         <div key={s.id}>
 *           <p>{s.id} — {s.summary ?? 'No summary'}</p>
 *           <small>{s.started_at}</small>
 *         </div>
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useSessions(limit = 20): {
  sessions: Session[]
  loading: boolean
  error: Error | null
  refresh: () => void
} {
  ensureReact()

  const { useState, useEffect, useCallback } = React

  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(() => setTick((t: number) => t + 1), [])

  useEffect(() => {
    if (!_client) return

    let cancelled = false
    setLoading(true)
    setError(null)

    _client
      .sessions(limit)
      .then((res: Session[]) => {
        if (!cancelled) setSessions(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tick, limit])

  return { sessions, loading, error, refresh }
}

/**
 * Reactive intentions hook.
 *
 * Fetches all active intentions on mount and provides a `refresh` function.
 * The SDK automatically unwraps the `{ data }` response envelope.
 *
 * @example
 * ```tsx
 * function IntentionList() {
 *   const { intentions, loading, refresh } = useIntentions()
 *   return (
 *     <div>
 *       <button onClick={refresh}>Refresh</button>
 *       {intentions.map(i => (
 *         <div key={i.id}>
 *           <p>{i.content} — {i.status}</p>
 *           <small>Priority: {i.priority}</small>
 *         </div>
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useIntentions(): {
  intentions: Intention[]
  loading: boolean
  error: Error | null
  refresh: () => void
} {
  ensureReact()

  const { useState, useEffect, useCallback } = React

  const [intentions, setIntentions] = useState<Intention[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(() => setTick((t: number) => t + 1), [])

  useEffect(() => {
    if (!_client) return

    let cancelled = false
    setLoading(true)
    setError(null)

    _client
      .intentions()
      .then((res: Intention[]) => {
        if (!cancelled) setIntentions(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { intentions, loading, error, refresh }
}
