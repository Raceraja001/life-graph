// ─────────────────────────────────────────────────────────────
// Life Graph SDK — Public API Surface
// ─────────────────────────────────────────────────────────────

// Core client
export { LifeGraph, LifeGraphError } from './client'

// All types
export type {
  LifeGraphConfig,
  Memory,
  SearchOptions,
  SearchResult,
  IngestResult,
  GraphEntity,
  EntityDetail,
  GraphEdge,
  PathResult,
  Stats,
  HealthStatus,
  EventType,
  EventHandler,
  LifeGraphEvent,
} from './types'

// React hooks (optional — only works when React is installed)
export {
  initLifeGraph,
  useBrain,
  useSearch,
  useMemories,
  useStats,
} from './react'
