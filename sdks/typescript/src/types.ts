// ─────────────────────────────────────────────────────────────
// Life Graph SDK — Type Definitions
// ─────────────────────────────────────────────────────────────

/** Configuration for the LifeGraph client. */
export interface LifeGraphConfig {
  /** Base URL of the Life Graph API (e.g. "http://localhost:8000"). */
  apiUrl: string
  /** Optional Bearer token for authenticated requests. */
  apiKey?: string
  /** Request timeout in milliseconds. Defaults to 30 000 ms. */
  timeout?: number
}

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
  /** Importance score (0-1). */
  importance: number
  /** Confidence score (0-1). */
  confidence: number
  /** How this memory was ingested (e.g. "text", "voice", "image"). */
  source_type?: string
  /** ISO-8601 timestamp of creation. */
  created_at?: string
  /** Number of times this memory has been retrieved. */
  access_count?: number
}

/** Options for semantic search queries. */
export interface SearchOptions {
  /** Maximum number of results to return. Defaults to 10. */
  limit?: number
  /** Filter results to only include memories with these tags. */
  tags?: string[]
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
  minio_key: string
}

/** A node in the knowledge graph. */
export interface GraphEntity {
  /** Display name / unique identifier of the entity. */
  name: string
  /** Neo4j label (e.g. "Person", "Place", "Concept"). */
  label?: string
  /** Arbitrary properties stored on the entity. */
  properties: Record<string, unknown>
}

/** Full detail view of an entity including its neighborhood. */
export interface EntityDetail {
  /** The entity itself. */
  entity: GraphEntity
  /** Directly connected entities. */
  neighbors: GraphEntity[]
  /** Edges connecting this entity to its neighbors. */
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
  /** Relationship type (e.g. "KNOWS", "VISITED"). */
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

/** API health check response. */
export interface HealthStatus {
  /** Service status string (e.g. "ok"). */
  status: string
  /** Deployed API version. */
  version: string
}

/** All event types emitted by the SDK. */
export type EventType =
  | 'memory:created'
  | 'memory:retrieved'
  | 'memory:updated'
  | 'memory:deleted'
  | 'session:start'
  | 'session:end'
  | 'voice:transcribed'
  | 'image:processed'
  | 'document:imported'

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
