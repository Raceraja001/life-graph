// ─────────────────────────────────────────────────────────────
// Life Graph SDK v1.0 — Public API Surface
// ─────────────────────────────────────────────────────────────

// Core client
export { LifeGraph, LifeGraphError } from './client'

// All types
export type {
  LifeGraphConfig,
  ApiResponse,
  ApiErrorBody,
  RateLimitInfo,
  Memory,
  SearchOptions,
  SearchResult,
  AskResult,
  RecallContext,
  IngestResult,
  Session,
  Intention,
  TimelineChapter,
  StaleBelief,
  KnowledgeGap,
  JobRun,
  GraphEntity,
  EntityDetail,
  GraphEdge,
  PathResult,
  GraphSearchResult,
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
  useSessions,
  useIntentions,
} from './react'
