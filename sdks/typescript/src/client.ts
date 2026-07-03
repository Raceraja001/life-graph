// ─────────────────────────────────────────────────────────────
// Life Graph SDK — Main Client
// ─────────────────────────────────────────────────────────────

import type {
  LifeGraphConfig,
  Memory,
  SearchOptions,
  SearchResult,
  IngestResult,
  GraphEntity,
  EntityDetail,
  PathResult,
  Stats,
  HealthStatus,
  EventType,
  EventHandler,
} from './types'

/**
 * Error thrown when the Life Graph API returns a non-2xx response.
 *
 * @example
 * ```ts
 * try {
 *   await lg.memory('nonexistent')
 * } catch (err) {
 *   if (err instanceof LifeGraphError && err.statusCode === 404) {
 *     console.log('Memory not found')
 *   }
 * }
 * ```
 */
export class LifeGraphError extends Error {
  /** HTTP status code from the failed response. */
  public readonly statusCode: number

  constructor(message: string, statusCode: number) {
    super(message)
    this.name = 'LifeGraphError'
    this.statusCode = statusCode
  }
}

/**
 * The main Life Graph SDK client.
 *
 * Provides typed access to every Life Graph API endpoint — memories,
 * ingestion, search, knowledge graph, multi-modal upload, and admin stats.
 *
 * @example
 * ```ts
 * import { LifeGraph } from '@life-graph/sdk'
 *
 * const lg = new LifeGraph({ apiUrl: 'http://localhost:8000' })
 *
 * // Remember something
 * await lg.remember('I love building with TypeScript')
 *
 * // Search memories
 * const results = await lg.search('typescript')
 * ```
 */
export class LifeGraph {
  private readonly baseUrl: string
  private readonly apiKey?: string
  private readonly timeout: number
  private readonly eventHandlers: Map<string, Set<EventHandler>>

  constructor(config: LifeGraphConfig) {
    this.baseUrl = config.apiUrl.replace(/\/$/, '')
    this.apiKey = config.apiKey
    this.timeout = config.timeout ?? 30_000
    this.eventHandlers = new Map()
  }

  // ── Private helpers ──────────────────────────────────────────

  /**
   * Internal fetch wrapper that handles auth, timeout, and error mapping.
   */
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    }
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeout)

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      })

      if (!response.ok) {
        const body = await response.text().catch(() => '')
        throw new LifeGraphError(
          `${response.status} ${response.statusText}: ${body}`,
          response.status,
        )
      }

      // 204 No Content — nothing to parse
      if (response.status === 204) return undefined as T

      return (await response.json()) as T
    } finally {
      clearTimeout(timeoutId)
    }
  }

  /**
   * Internal multipart upload helper for voice / image / document ingestion.
   * Does NOT set Content-Type so the browser/runtime can set the correct
   * multipart boundary automatically.
   */
  private async upload<T>(path: string, file: File | Blob, fieldName = 'file'): Promise<T> {
    const formData = new FormData()
    formData.append(fieldName, file)

    const headers: Record<string, string> = {}
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeout)

    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers,
        body: formData,
        signal: controller.signal,
      })

      if (!response.ok) {
        const body = await response.text().catch(() => '')
        throw new LifeGraphError(`${response.status}: ${body}`, response.status)
      }

      return (await response.json()) as T
    } finally {
      clearTimeout(timeoutId)
    }
  }

  // ── Health ───────────────────────────────────────────────────

  /**
   * Check the API health status.
   *
   * @returns The current health status and version.
   *
   * @example
   * ```ts
   * const h = await lg.health()
   * console.log(h.version) // "0.4.0"
   * ```
   */
  async health(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health')
  }

  /**
   * Quick connectivity check.
   *
   * @returns `true` if the API is reachable and healthy, `false` otherwise.
   *
   * @example
   * ```ts
   * if (await lg.ping()) {
   *   console.log('Life Graph is online')
   * }
   * ```
   */
  async ping(): Promise<boolean> {
    try {
      await this.health()
      return true
    } catch {
      return false
    }
  }

  // ── Memory CRUD ──────────────────────────────────────────────

  /**
   * List all memories.
   *
   * @returns An array of every memory in the system.
   *
   * @example
   * ```ts
   * const all = await lg.memories()
   * console.log(`You have ${all.length} memories`)
   * ```
   */
  async memories(): Promise<Memory[]> {
    const result = await this.request<Memory[]>('/memories/')
    this.emit('memory:retrieved', { count: result.length })
    return result
  }

  /**
   * Get a single memory by ID.
   *
   * @param id - The unique memory identifier.
   * @returns The requested memory.
   * @throws {LifeGraphError} 404 if the memory does not exist.
   *
   * @example
   * ```ts
   * const mem = await lg.memory('abc-123')
   * console.log(mem.content)
   * ```
   */
  async memory(id: string): Promise<Memory> {
    const result = await this.request<Memory>(`/memories/${encodeURIComponent(id)}`)
    this.emit('memory:retrieved', { id })
    return result
  }

  /**
   * Delete a memory by ID.
   *
   * @param id - The unique memory identifier.
   * @throws {LifeGraphError} 404 if the memory does not exist.
   *
   * @example
   * ```ts
   * await lg.deleteMemory('abc-123')
   * ```
   */
  async deleteMemory(id: string): Promise<void> {
    await this.request<void>(`/memories/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
    this.emit('memory:deleted', { id })
  }

  // ── Ingestion ────────────────────────────────────────────────

  /**
   * Ingest free-form text and create memories from it.
   *
   * The API will extract entities, relationships, and semantic meaning
   * from the text and persist them as memories in the graph.
   *
   * @param text - The text to ingest.
   * @returns An array of newly created memories.
   *
   * @example
   * ```ts
   * const memories = await lg.remember('I had coffee with Alice at Blue Bottle today')
   * console.log(`Created ${memories.length} memories`)
   * ```
   */
  async remember(text: string): Promise<Memory[]> {
    const result = await this.request<Memory[]>('/admin/ingest', {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
    this.emit('memory:created', { count: result.length, source: 'text' })
    return result
  }

  /**
   * Upload and transcribe a voice recording, creating memories from the transcript.
   *
   * @param file - An audio file (Blob or File).
   * @returns Transcription result with memory creation stats.
   *
   * @example
   * ```ts
   * const audioBlob = new Blob([audioBuffer], { type: 'audio/webm' })
   * const result = await lg.ingestVoice(audioBlob)
   * console.log(result.transcript)
   * ```
   */
  async ingestVoice(file: File | Blob): Promise<IngestResult> {
    const result = await this.upload<IngestResult>('/ingest/voice', file)
    this.emit('voice:transcribed', { memories_created: result.memories_created })
    return result
  }

  /**
   * Upload an image for OCR processing, creating memories from extracted text.
   *
   * @param file - An image file (Blob or File).
   * @returns OCR result with memory creation stats.
   *
   * @example
   * ```ts
   * const result = await lg.ingestImage(imageFile)
   * console.log(result.ocr_text)
   * ```
   */
  async ingestImage(file: File | Blob): Promise<IngestResult> {
    const result = await this.upload<IngestResult>('/ingest/image', file)
    this.emit('image:processed', { memories_created: result.memories_created })
    return result
  }

  /**
   * Upload a document (PDF, DOCX, etc.) for text extraction and memory creation.
   *
   * @param file - A document file (Blob or File).
   * @returns Extraction result with chunk count and memory creation stats.
   *
   * @example
   * ```ts
   * const result = await lg.ingestDocument(pdfFile)
   * console.log(`Processed ${result.chunks} chunks → ${result.memories_created} memories`)
   * ```
   */
  async ingestDocument(file: File | Blob): Promise<IngestResult> {
    const result = await this.upload<IngestResult>('/ingest/document', file)
    this.emit('document:imported', {
      memories_created: result.memories_created,
      chunks: result.chunks,
    })
    return result
  }

  // ── Search ───────────────────────────────────────────────────

  /**
   * Perform a semantic search across all memories.
   *
   * @param query - Natural language search query.
   * @param options - Optional search parameters (limit, tag filters).
   * @returns Ranked list of matching memories.
   *
   * @example
   * ```ts
   * const results = await lg.search('meetings with Alice', { limit: 5 })
   * results.forEach(r => console.log(r.content, r.score))
   * ```
   */
  async search(query: string, options?: SearchOptions): Promise<SearchResult[]> {
    const body: Record<string, unknown> = {
      query,
      limit: options?.limit ?? 10,
    }
    if (options?.tags?.length) {
      body['tags'] = options.tags
    }

    const result = await this.request<SearchResult[] | { results: SearchResult[] }>('/search/', {
      method: 'POST',
      body: JSON.stringify(body),
    })

    // The API may return { results: [...] } or a bare array
    return Array.isArray(result) ? result : result.results
  }

  // ── Graph ────────────────────────────────────────────────────

  /**
   * List entities in the knowledge graph, optionally filtered by label.
   *
   * @param label - Optional Neo4j label to filter by (e.g. "Person").
   * @returns Array of matching entities.
   *
   * @example
   * ```ts
   * const people = await lg.entities('Person')
   * ```
   */
  async entities(label?: string): Promise<GraphEntity[]> {
    const query = label ? `?label=${encodeURIComponent(label)}` : ''
    return this.request<GraphEntity[]>(`/graph/entities${query}`)
  }

  /**
   * Get full details for a named entity, including its neighbors and edges.
   *
   * @param name - The entity name.
   * @returns Entity detail with neighborhood and associated memories.
   * @throws {LifeGraphError} 404 if the entity does not exist.
   *
   * @example
   * ```ts
   * const detail = await lg.entity('Alice')
   * console.log(detail.neighbors.map(n => n.name))
   * ```
   */
  async entity(name: string): Promise<EntityDetail> {
    return this.request<EntityDetail>(`/graph/entity/${encodeURIComponent(name)}`)
  }

  /**
   * Execute a raw Cypher query against the knowledge graph.
   *
   * @param cypher - A valid Cypher query string.
   * @param columns - Optional list of column names to return.
   * @returns Array of result rows.
   *
   * @example
   * ```ts
   * const rows = await lg.graphQuery(
   *   'MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name',
   *   ['a.name', 'b.name']
   * )
   * ```
   */
  async graphQuery(cypher: string, columns?: string[]): Promise<unknown[]> {
    const body: Record<string, unknown> = { cypher }
    if (columns?.length) {
      body['columns'] = columns
    }
    return this.request<unknown[]>('/graph/query', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  /**
   * Find the shortest path between two entities in the graph.
   *
   * @param from - Source entity name.
   * @param to - Target entity name.
   * @returns The path with ordered edges and hop count.
   *
   * @example
   * ```ts
   * const path = await lg.graphPath('Alice', 'Bob')
   * console.log(`${path.length} hops`)
   * ```
   */
  async graphPath(from: string, to: string): Promise<PathResult> {
    const params = new URLSearchParams({
      from_name: from,
      to_name: to,
    })
    return this.request<PathResult>(`/graph/path?${params.toString()}`)
  }

  /**
   * Hybrid search combining semantic similarity with graph structure.
   *
   * @param query - Natural language search query.
   * @param graphFilter - Optional graph-level filter object.
   * @param limit - Maximum number of results. Defaults to 10.
   * @returns Ranked search results enriched with graph context.
   *
   * @example
   * ```ts
   * const results = await lg.graphSearch('coffee shops', { label: 'Place' }, 5)
   * ```
   */
  async graphSearch(
    query: string,
    graphFilter?: Record<string, unknown>,
    limit?: number,
  ): Promise<SearchResult[]> {
    const body: Record<string, unknown> = {
      query,
      limit: limit ?? 10,
    }
    if (graphFilter) {
      body['graph_filter'] = graphFilter
    }

    const result = await this.request<SearchResult[] | { results: SearchResult[] }>(
      '/graph/search',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    )

    return Array.isArray(result) ? result : result.results
  }

  // ── Stats ────────────────────────────────────────────────────

  /**
   * Retrieve high-level system statistics.
   *
   * @returns Memory, intention, gap, and session counts.
   *
   * @example
   * ```ts
   * const s = await lg.stats()
   * console.log(`${s.memory_count} memories across ${s.session_count} sessions`)
   * ```
   */
  async stats(): Promise<Stats> {
    return this.request<Stats>('/admin/stats')
  }

  // ── Events (client-side) ─────────────────────────────────────

  /**
   * Register an event handler.
   *
   * Use `'*'` to listen to all events.
   *
   * @param event - The event type to listen for, or `'*'` for all.
   * @param handler - Callback invoked when the event fires.
   * @returns An unsubscribe function — call it to remove this handler.
   *
   * @example
   * ```ts
   * const unsub = lg.on('memory:created', (e) => {
   *   console.log('New memory!', e.payload)
   * })
   *
   * // Later…
   * unsub()
   * ```
   */
  on(event: EventType | '*', handler: EventHandler): () => void {
    const key = event as string
    if (!this.eventHandlers.has(key)) {
      this.eventHandlers.set(key, new Set())
    }
    this.eventHandlers.get(key)!.add(handler)

    // Return unsubscribe function
    return () => this.off(event, handler)
  }

  /**
   * Remove a previously registered event handler.
   *
   * @param event - The event type the handler was registered for.
   * @param handler - The exact handler function reference to remove.
   */
  off(event: EventType | '*', handler: EventHandler): void {
    const key = event as string
    this.eventHandlers.get(key)?.delete(handler)
  }

  /**
   * Emit an event to all registered handlers.
   *
   * @internal
   */
  protected emit(event: EventType, payload: Record<string, unknown>): void {
    const envelope = {
      type: event,
      payload,
      timestamp: new Date().toISOString(),
    }

    // Fire specific handlers
    const specific = this.eventHandlers.get(event)
    if (specific) {
      for (const handler of specific) {
        try {
          handler(envelope)
        } catch {
          // Swallow handler errors to avoid breaking the SDK flow
        }
      }
    }

    // Fire wildcard handlers
    const wildcard = this.eventHandlers.get('*')
    if (wildcard) {
      for (const handler of wildcard) {
        try {
          handler(envelope)
        } catch {
          // Swallow handler errors
        }
      }
    }
  }
}
