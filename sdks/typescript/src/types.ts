// ─────────────────────────────────────────────────────────────
// Life Graph SDK v1.0 — Type Definitions
// ─────────────────────────────────────────────────────────────

// ── Configuration ──────────────────────────────────────────────

/**
 * Configuration for the {@link LifeGraph} client.
 *
 * @example
 * ```ts
 * const config: LifeGraphConfig = {
 *   apiUrl: 'https://api.lifegraph.app',
 *   apiKey: 'lg_live_abc123',
 *   tenantId: 'tenant-42',
 *   timeout: 15_000,
 * }
 * ```
 */
export interface LifeGraphConfig {
  /** Base URL of the Life Graph API (e.g. `"https://api.lifegraph.app"`). */
  apiUrl: string
  /** API key sent via the `X-API-Key` header. Optional for local development. */
  apiKey?: string
  /** Tenant identifier sent via the `X-Tenant-ID` header on every request. **Required.** */
  tenantId: string
  /** Request timeout in milliseconds. Defaults to 30 000 ms. */
  timeout?: number
}

// ── Response / Error Envelopes ─────────────────────────────────

/**
 * Standard API response envelope.
 *
 * Every successful Life Graph response wraps the payload in `{ data, meta? }`.
 * The SDK unwraps `.data` automatically so callers never see this directly.
 */
export interface ApiResponse<T> {
  /** The actual response payload. */
  data: T
  /** Optional pagination / timing metadata returned by the API. */
  meta?: Record<string, unknown>
}

/**
 * Structured error body returned by the Life Graph API.
 *
 * @example
 * ```json
 * {
 *   "error": {
 *     "code": "MEMORY_NOT_FOUND",
 *     "message": "No memory with ID abc-123",
 *     "request_id": "req_xyz"
 *   }
 * }
 * ```
 */
export interface ApiErrorBody {
  error: {
    /** Machine-readable error code (e.g. `"MEMORY_NOT_FOUND"`). */
    code: string
    /** Human-readable error description. */
    message: string
    /** Unique request identifier for support / debugging. */
    request_id: string
  }
}

/**
 * Parsed rate-limit information from response headers.
 *
 * Updated after every successful API call and available via
 * `LifeGraph.rateLimitInfo`.
 */
export interface RateLimitInfo {
  /** Maximum requests allowed in the current window. */
  limit: number
  /** Remaining requests in the current window. */
  remaining: number
  /** Unix epoch (seconds) when the window resets. */
  resetAt: number
}

// ── Core Domain Types ──────────────────────────────────────────

/** A single memory stored in the Life Graph. */
export interface Memory {
  /** Unique identifier for this memory. */
  id: string
  /** The textual content of the memory. */
  content: string
  /** LLM-generated reasoning about why this memory matters. */
  reasoning?: string
  /** Classification tags attached to this memory. */
  tags: string[]
  /** Arbitrary key-value properties. */
  properties: Record<string, unknown>
  /** Importance score (0–1). */
  importance: number
  /** Confidence score (0–1). */
  confidence: number
  /** Memory lifecycle status (e.g. `"active"`, `"superseded"`). */
  status?: string
  /** How this memory was ingested (e.g. `"text"`, `"voice"`, `"image"`). */
  source_type?: string
  /** The originating source description. */
  source?: string
  /** ISO-8601 timestamp of creation. */
  created_at?: string
  /** ISO-8601 timestamp of the last update. */
  updated_at?: string
  /** Number of times this memory has been retrieved. */
  access_count?: number
  /** Domain this memory belongs to (e.g. `"work"`, `"personal"`). */
  domain?: string
}

// ── Search ─────────────────────────────────────────────────────

/** Options for semantic search queries. */
export interface SearchOptions {
  /** Maximum number of results to return. Defaults to 10. */
  limit?: number
  /** Filter results to only include memories with these tags. */
  tags?: string[]
  /** Minimum importance threshold (0–1). */
  min_importance?: number
}

/** A single search result with relevance metadata. */
export interface SearchResult {
  /** The textual content of the matched memory. */
  content: string
  /** Tags on the matched memory. */
  tags: string[]
  /** Semantic similarity score. */
  score?: number
  /** Importance score of the matched memory. */
  importance?: number
  /** Arbitrary properties on the matched memory. */
  properties?: Record<string, unknown>
}

/**
 * Result from the `/ask` endpoint — a synthesised answer grounded in memories.
 */
export interface AskResult {
  /** The generated natural-language answer. */
  answer: string
  /** Number of source memories used to formulate the answer. */
  source_count: number
  /** The LLM model used for generation, if available. */
  model: string | null
  /** Source memories that contributed to the answer. */
  memories: Memory[]
  /** Server-side query processing time in milliseconds. */
  query_time_ms: number
}

/**
 * Contextual recall result containing relevant memories,
 * active decisions, intentions, and warnings.
 */
export interface RecallContext {
  /** Memories relevant to the provided context. */
  relevant_memories: Memory[]
  /** Active decisions applicable to the context. */
  decisions: Record<string, unknown>[]
  /** Active intentions applicable to the context. */
  intentions: Record<string, unknown>[]
  /** Warnings or conflicts detected against the context. */
  warnings: Record<string, unknown>[]
}

// ── Sessions ───────────────────────────────────────────────────

/**
 * A conversation / interaction session tracked by Life Graph.
 */
export interface Session {
  /** Unique session identifier. */
  id: string
  /** ISO-8601 timestamp when the session was started. */
  started_at: string
  /** ISO-8601 timestamp when the session ended, or `null` if still active. */
  ended_at: string | null
  /** Arbitrary context metadata attached to the session. */
  context: Record<string, unknown>
  /** AI-generated summary of the session, or `null` if not yet summarised. */
  summary: string | null
  /** Number of memories created during this session. */
  memories_created: number
  /** Number of memories accessed / retrieved during this session. */
  memories_accessed: number
}

// ── Intentions ─────────────────────────────────────────────────

/**
 * An intention (goal / to-do / reminder) tracked by Life Graph.
 */
export interface Intention {
  /** Unique intention identifier. */
  id: string
  /** Human-readable description of the intention. */
  content: string
  /** How this intention is triggered (e.g. `"context"`, `"time"`, `"manual"`). */
  trigger_type: string
  /** Condition expression that activates this intention, or `null`. */
  trigger_condition: string | null
  /** Lifecycle status (e.g. `"active"`, `"completed"`, `"dismissed"`). */
  status: string
  /** Priority level (e.g. `"low"`, `"medium"`, `"high"`). */
  priority: string
  /** ISO-8601 timestamp of creation. */
  created_at: string
}

// ── Identity / Timeline ────────────────────────────────────────

/**
 * A chapter in the identity timeline, grouping memories by time period.
 */
export interface TimelineChapter {
  /** Human-readable period label (e.g. `"2026-Q1"`, `"Last 30 days"`). */
  period: string
  /** Memories that are still actively relevant in this period. */
  active: Memory[]
  /** Memories that have been superseded during this period. */
  superseded: Memory[]
}

/**
 * A belief that may be stale and should be re-evaluated.
 */
export interface StaleBelief {
  /** The memory representing the belief. */
  memory: Memory
  /** Suggested prompt/question to re-evaluate the belief. */
  prompt: string
  /** Number of days since the belief was last confirmed. */
  days_stale: number
}

// ── Knowledge Gaps ─────────────────────────────────────────────

/**
 * A detected knowledge gap — a topic the user has asked about
 * but the system lacks sufficient information on.
 */
export interface KnowledgeGap {
  /** Unique gap identifier. */
  id: string
  /** The topic or subject of the gap. */
  topic: string
  /** Number of queries that triggered this gap. */
  query_count: number
  /** ISO-8601 timestamp of the first related query. */
  first_asked: string
  /** ISO-8601 timestamp of the most recent related query. */
  last_asked: string
  /** Whether this gap has been resolved. */
  resolved: boolean
}

// ── Ingestion ──────────────────────────────────────────────────

/** Result returned from multi-modal ingestion endpoints. */
export interface IngestResult {
  /** Transcript text (voice ingestion). */
  transcript?: string
  /** OCR-extracted text (image ingestion). */
  ocr_text?: string
  /** Total character length of extracted text (document ingestion). */
  text_length?: number
  /** Number of chunks the document was split into. */
  chunks?: number
  /** Number of memories created from the ingested content. */
  memories_created: number
  /** Object storage key for the uploaded file. */
  minio_key?: string
}

// ── Knowledge Graph ────────────────────────────────────────────

/** A node in the knowledge graph. */
export interface GraphEntity {
  /** Display name / unique identifier of the entity. */
  name: string
  /** Neo4j label (e.g. `"Person"`, `"Place"`, `"Concept"`). */
  label?: string
  /** Arbitrary properties stored on the entity. */
  properties: Record<string, unknown>
}

/** Full detail view of an entity including its neighbourhood. */
export interface EntityDetail {
  /** The entity itself. */
  entity: GraphEntity
  /** Directly connected entities. */
  neighbors: GraphEntity[]
  /** Edges connecting this entity to its neighbours. */
  edges: GraphEdge[]
  /** Memories associated with this entity. */
  memories: Memory[]
}

/** A directed edge in the knowledge graph. */
export interface GraphEdge {
  /** Source entity name. */
  from_name: string
  /** Target entity name. */
  to_name: string
  /** Relationship type (e.g. `"KNOWS"`, `"VISITED"`). */
  label: string
  /** Arbitrary properties stored on the edge. */
  properties: Record<string, unknown>
}

/** Result of a shortest-path query between two entities. */
export interface PathResult {
  /** Source entity name. */
  from_name: string
  /** Target entity name. */
  to_name: string
  /** Ordered list of edges forming the path. */
  path: GraphEdge[]
  /** Number of hops in the path. */
  length: number
}

/**
 * Result from the hybrid graph search endpoint.
 *
 * Combines semantic similarity with graph-structural relevance.
 */
export interface GraphSearchResult {
  /** Ranked search results enriched with graph context. */
  results: SearchResult[]
  /** Total number of results available (may exceed returned count). */
  total?: number
  /** Graph entities related to the query. */
  entities?: GraphEntity[]
}

// ── Admin / Jobs ───────────────────────────────────────────────

/** High-level system statistics. */
export interface Stats {
  /** Total number of memories. */
  memory_count: number
  /** Total number of detected intentions. */
  intention_count: number
  /** Total number of knowledge gaps. */
  gap_count: number
  /** Total number of sessions. */
  session_count: number
}

/**
 * A background job run record (e.g. consolidation, embedding).
 */
export interface JobRun {
  /** Unique job run identifier. */
  id: string
  /** Tenant this job belongs to. */
  tenant_id: string
  /** Job type name (e.g. `"consolidation"`, `"embedding"`). */
  job_name: string
  /** Execution status (e.g. `"pending"`, `"running"`, `"completed"`, `"failed"`). */
  status: string
  /** ISO-8601 timestamp of when the job started. */
  started_at: string
  /** ISO-8601 timestamp of completion, or `null` if still running. */
  completed_at: string | null
  /** Error message if the job failed, or `null`. */
  error: string | null
  /** Arbitrary result payload from a completed job, or `null`. */
  result: Record<string, unknown> | null
}

// ── Health ──────────────────────────────────────────────────────

/** API health check response. */
export interface HealthStatus {
  /** Service status string (e.g. `"ok"`). */
  status: string
  /** Deployed API version. */
  version: string
}

// ── Events ─────────────────────────────────────────────────────

/** All event types emitted by the SDK. */
export type EventType =
  | 'memory:created'
  | 'memory:retrieved'
  | 'memory:updated'
  | 'memory:deleted'
  | 'session:start'
  | 'session:end'
  | 'session:heartbeat'
  | 'intention:created'
  | 'intention:completed'
  | 'intention:dismissed'
  | 'voice:transcribed'
  | 'image:processed'
  | 'document:imported'
  | 'search:completed'
  | 'ask:completed'

/** Shape of an event delivered to handlers. */
export interface LifeGraphEvent {
  /** The event type. */
  type: EventType
  /** Event-specific data. */
  payload: Record<string, unknown>
  /** ISO-8601 timestamp of when the event was emitted. */
  timestamp: string
}

/** Callback for SDK events. */
export type EventHandler = (event: LifeGraphEvent) => void
