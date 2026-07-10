// ─────────────────────────────────────────────────────────────
// Life Graph SDK v1.0 — Main Client
// ─────────────────────────────────────────────────────────────

import type {
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
  PathResult,
  GraphSearchResult,
  Stats,
  HealthStatus,
  EventType,
  EventHandler,
} from './types'

// ── Error Class ────────────────────────────────────────────────

/**
 * Error thrown when the Life Graph API returns a non-2xx response.
 *
 * Includes structured fields parsed from the API's error envelope:
 * ```json
 * { "error": { "code": "...", "message": "...", "request_id": "..." } }
 * ```
 *
 * @example
 * ```ts
 * try {
 *   await lg.memory('nonexistent')
 * } catch (err) {
 *   if (err instanceof LifeGraphError) {
 *     console.log(err.code)       // "MEMORY_NOT_FOUND"
 *     console.log(err.requestId)  // "req_abc123"
 *     console.log(err.statusCode) // 404
 *   }
 * }
 * ```
 */
export class LifeGraphError extends Error {
  /** HTTP status code from the failed response. */
  public readonly statusCode: number

  /** Machine-readable error code from the API error envelope (e.g. `"MEMORY_NOT_FOUND"`). */
  public readonly code: string

  /** Unique request identifier for debugging / support tickets. */
  public readonly requestId: string

  constructor(message: string, statusCode: number, code = 'UNKNOWN', requestId = '') {
    super(message)
    this.name = 'LifeGraphError'
    this.statusCode = statusCode
    this.code = code
    this.requestId = requestId
  }
}

// ── Main Client ────────────────────────────────────────────────

/**
 * The main Life Graph SDK client.
 *
 * Provides typed access to every Life Graph v1.0 API endpoint — memories,
 * search, sessions, intentions, identity, knowledge graph, multi-modal
 * ingestion, agent helpers, and admin operations.
 *
 * All API calls automatically:
 * - Prepend `/api/v1` (except health/live/ready which stay at root)
 * - Send `X-API-Key` and `X-Tenant-ID` headers
 * - Unwrap the `{ data, meta }` response envelope
 * - Parse rate-limit headers into {@link RateLimitInfo}
 * - Map error responses to {@link LifeGraphError}
 *
 * @example
 * ```ts
 * import { LifeGraph } from '@anthropic/life-graph-sdk'
 *
 * const lg = new LifeGraph({
 *   apiUrl: 'https://api.lifegraph.app',
 *   apiKey: 'lg_live_abc123',
 *   tenantId: 'tenant-42',
 * })
 *
 * // Remember something
 * await lg.remember('I love building with TypeScript')
 *
 * // Semantic search
 * const results = await lg.search('typescript')
 * ```
 */
export class LifeGraph {
  private readonly baseUrl: string
  private readonly apiKey?: string
  private readonly tenantId: string
  private readonly timeout: number
  private readonly eventHandlers: Map<string, Set<EventHandler>>
  private _rateLimitInfo: RateLimitInfo | null = null

  constructor(config: LifeGraphConfig) {
    if (!config.tenantId) {
      throw new Error('LifeGraphConfig.tenantId is required')
    }
    this.baseUrl = config.apiUrl.replace(/\/$/, '')
    this.apiKey = config.apiKey
    this.tenantId = config.tenantId
    this.timeout = config.timeout ?? 30_000
    this.eventHandlers = new Map()
  }

  // ── Rate Limit Info ─────────────────────────────────────────

  /**
   * The most recently observed rate-limit state, parsed from response headers.
   *
   * Returns `null` until at least one successful API call has been made.
   *
   * @example
   * ```ts
   * await lg.health()
   * console.log(lg.rateLimitInfo)
   * // { limit: 1000, remaining: 997, resetAt: 1719180000 }
   * ```
   */
  get rateLimitInfo(): RateLimitInfo | null {
    return this._rateLimitInfo
  }

  // ── Private Helpers ─────────────────────────────────────────

  /**
   * Build the full versioned API path by prepending `/api/v1`.
   *
   * @param path - The resource path (e.g. `"/memories"`).
   * @returns The fully qualified path (e.g. `"/api/v1/memories"`).
   */
  private api(path: string): string {
    return `/api/v1${path}`
  }

  /**
   * Parse rate-limit headers from the response and cache them.
   *
   * @param response - The raw fetch `Response` object.
   */
  private parseRateLimitHeaders(response: Response): void {
    const limit = response.headers.get('X-RateLimit-Limit')
    const remaining = response.headers.get('X-RateLimit-Remaining')
    const reset = response.headers.get('X-RateLimit-Reset')

    if (limit !== null && remaining !== null && reset !== null) {
      this._rateLimitInfo = {
        limit: parseInt(limit, 10),
        remaining: parseInt(remaining, 10),
        resetAt: parseInt(reset, 10),
      }
    }
  }

  /**
   * Internal fetch wrapper that handles auth headers, timeout,
   * response envelope unwrapping, rate-limit parsing, and error mapping.
   *
   * @typeParam T - The expected shape of the unwrapped `data` field.
   * @param path - Full request path (already includes `/api/v1` if needed).
   * @param options - Standard `RequestInit` overrides.
   * @returns The unwrapped `data` payload from the response envelope.
   * @throws {LifeGraphError} On any non-2xx response.
   */
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Tenant-ID': this.tenantId,
      ...(options.headers as Record<string, string>),
    }
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey
    }

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeout)

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      })

      this.parseRateLimitHeaders(response)

      if (!response.ok) {
        const body = await response.text().catch(() => '')
        let code = 'UNKNOWN'
        let message = `${response.status} ${response.statusText}: ${body}`
        let requestId = ''

        try {
          const parsed = JSON.parse(body) as ApiErrorBody
          if (parsed?.error) {
            code = parsed.error.code ?? code
            message = parsed.error.message ?? message
            requestId = parsed.error.request_id ?? requestId
          }
        } catch {
          // Body was not valid JSON — use the raw text
        }

        throw new LifeGraphError(message, response.status, code, requestId)
      }

      // 204 No Content — nothing to parse
      if (response.status === 204) return undefined as T

      const json = await response.json()

      // Unwrap the standard { data, meta? } envelope.
      // If the response has a `data` key, return its value.
      // Otherwise return the raw body (for root-level endpoints like /health).
      if (json !== null && typeof json === 'object' && 'data' in json) {
        return (json as ApiResponse<T>).data
      }

      return json as T
    } finally {
      clearTimeout(timeoutId)
    }
  }

  /**
   * Internal multipart upload helper for voice / image / document ingestion.
   *
   * Does **not** set `Content-Type` so the browser/runtime can set the
   * correct multipart boundary automatically. Unwraps the response envelope.
   *
   * @typeParam T - The expected shape of the unwrapped `data` field.
   * @param path - Full request path (already includes `/api/v1` if needed).
   * @param file - The file to upload.
   * @param fieldName - Form field name. Defaults to `"file"`.
   * @returns The unwrapped `data` payload from the response envelope.
   * @throws {LifeGraphError} On any non-2xx response.
   */
  private async upload<T>(path: string, file: File | Blob, fieldName = 'file'): Promise<T> {
    const formData = new FormData()
    formData.append(fieldName, file)

    const headers: Record<string, string> = {
      'X-Tenant-ID': this.tenantId,
    }
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey
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

      this.parseRateLimitHeaders(response)

      if (!response.ok) {
        const body = await response.text().catch(() => '')
        let code = 'UNKNOWN'
        let message = `${response.status}: ${body}`
        let requestId = ''

        try {
          const parsed = JSON.parse(body) as ApiErrorBody
          if (parsed?.error) {
            code = parsed.error.code ?? code
            message = parsed.error.message ?? message
            requestId = parsed.error.request_id ?? requestId
          }
        } catch {
          // Body was not valid JSON
        }

        throw new LifeGraphError(message, response.status, code, requestId)
      }

      const json = await response.json()

      if (json !== null && typeof json === 'object' && 'data' in json) {
        return (json as ApiResponse<T>).data
      }

      return json as T
    } finally {
      clearTimeout(timeoutId)
    }
  }

  // ── Health (root paths — no /api/v1 prefix) ─────────────────

  /**
   * Check the API health status.
   *
   * This endpoint lives at the root (`/health`), **not** under `/api/v1`.
   *
   * @returns The current health status and version.
   *
   * @example
   * ```ts
   * const h = await lg.health()
   * console.log(h.version) // "1.0.0"
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

  /**
   * Kubernetes readiness probe.
   *
   * This endpoint lives at the root (`/ready`), **not** under `/api/v1`.
   *
   * @returns An object with a `status` field (e.g. `"ready"`).
   *
   * @example
   * ```ts
   * const r = await lg.ready()
   * console.log(r.status) // "ready"
   * ```
   */
  async ready(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/ready')
  }

  /**
   * Kubernetes liveness probe.
   *
   * This endpoint lives at the root (`/live`), **not** under `/api/v1`.
   *
   * @returns An object with a `status` field (e.g. `"alive"`).
   *
   * @example
   * ```ts
   * const l = await lg.live()
   * console.log(l.status) // "alive"
   * ```
   */
  async live(): Promise<{ status: string }> {
    return this.request<{ status: string }>('/live')
  }

  // ── Memory CRUD ─────────────────────────────────────────────

  /**
   * List memories with optional filtering.
   *
   * @param options - Optional filters for status, tags, importance, pagination.
   * @returns An array of memories matching the filters.
   *
   * @example
   * ```ts
   * // All memories
   * const all = await lg.memories()
   *
   * // Filtered
   * const important = await lg.memories({ min_importance: 0.8, limit: 20 })
   * ```
   */
  async memories(options?: {
    /** Filter by memory status (e.g. `"active"`, `"superseded"`). */
    status?: string
    /** Filter to memories with any of these tags. */
    tags?: string[]
    /** Minimum importance threshold (0–1). */
    min_importance?: number
    /** Maximum number of results. */
    limit?: number
    /** Offset for pagination. */
    offset?: number
  }): Promise<Memory[]> {
    const params = new URLSearchParams()
    if (options?.status) params.set('status', options.status)
    if (options?.tags?.length) params.set('tags', options.tags.join(','))
    if (options?.min_importance !== undefined) params.set('min_importance', String(options.min_importance))
    if (options?.limit !== undefined) params.set('limit', String(options.limit))
    if (options?.offset !== undefined) params.set('offset', String(options.offset))

    const query = params.toString()
    const path = query ? `${this.api('/memories')}?${query}` : this.api('/memories')
    const result = await this.request<Memory[]>(path)
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
    const result = await this.request<Memory>(this.api(`/memories/${encodeURIComponent(id)}`))
    this.emit('memory:retrieved', { id })
    return result
  }

  /**
   * Create one or more memories from text content.
   *
   * The API extracts entities, relationships, and semantic meaning from the
   * text and persists them as memories in the graph.
   *
   * @param content - The text content to create memories from.
   * @param options - Optional source, tags, and importance overrides.
   * @returns An array of newly created memories.
   *
   * @example
   * ```ts
   * const mems = await lg.createMemory('Alice prefers window seats', {
   *   source: 'conversation',
   *   tags: ['preference'],
   *   importance: 0.7,
   * })
   * ```
   */
  async createMemory(
    content: string,
    options?: {
      /** Source identifier (e.g. `"conversation"`, `"import"`). */
      source?: string
      /** Tags to attach to the new memory. */
      tags?: string[]
      /** Importance override (0–1). */
      importance?: number
    },
  ): Promise<Memory[]> {
    const body: Record<string, unknown> = { content }
    if (options?.source !== undefined) body['source'] = options.source
    if (options?.tags?.length) body['tags'] = options.tags
    if (options?.importance !== undefined) body['importance'] = options.importance

    const result = await this.request<Memory[]>(this.api('/memories'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('memory:created', { count: result.length, source: options?.source ?? 'text' })
    return result
  }

  /**
   * Update an existing memory by ID.
   *
   * @param id - The unique memory identifier.
   * @param updates - A partial memory object with the fields to update.
   * @returns The updated memory.
   * @throws {LifeGraphError} 404 if the memory does not exist.
   *
   * @example
   * ```ts
   * const updated = await lg.updateMemory('abc-123', {
   *   importance: 0.9,
   *   tags: ['important', 'work'],
   * })
   * ```
   */
  async updateMemory(id: string, updates: Partial<Memory>): Promise<Memory> {
    const result = await this.request<Memory>(this.api(`/memories/${encodeURIComponent(id)}`), {
      method: 'PATCH',
      body: JSON.stringify(updates),
    })
    this.emit('memory:updated', { id })
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
    await this.request<void>(this.api(`/memories/${encodeURIComponent(id)}`), {
      method: 'DELETE',
    })
    this.emit('memory:deleted', { id })
  }

  // ── Search ──────────────────────────────────────────────────

  /**
   * Perform a semantic search across all memories.
   *
   * @param query - Natural language search query.
   * @param options - Optional search parameters (limit, tag filters, min importance).
   * @returns A search result object with ranked matches.
   *
   * @example
   * ```ts
   * const results = await lg.search('meetings with Alice', { limit: 5 })
   * console.log(results)
   * ```
   */
  async search(query: string, options?: SearchOptions): Promise<SearchResult> {
    const body: Record<string, unknown> = {
      query,
      limit: options?.limit ?? 10,
    }
    if (options?.tags?.length) {
      body['tags'] = options.tags
    }
    if (options?.min_importance !== undefined) {
      body['min_importance'] = options.min_importance
    }

    const result = await this.request<SearchResult>(this.api('/search'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('search:completed', { query })
    return result
  }

  /**
   * Ask a natural-language question and get a synthesised answer
   * grounded in stored memories.
   *
   * @param question - The question to answer.
   * @param limit - Maximum number of source memories to consider. Defaults to 10.
   * @returns An answer with source memories and timing metadata.
   *
   * @example
   * ```ts
   * const result = await lg.ask('What does Alice prefer for coffee?')
   * console.log(result.answer)
   * console.log(`Used ${result.source_count} sources in ${result.query_time_ms}ms`)
   * ```
   */
  async ask(question: string, limit?: number): Promise<AskResult> {
    const body: Record<string, unknown> = { question }
    if (limit !== undefined) body['limit'] = limit

    const result = await this.request<AskResult>(this.api('/ask'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('ask:completed', { question })
    return result
  }

  /**
   * Recall memories and active intentions/decisions relevant to a context.
   *
   * Useful for building agent prompts with relevant background information.
   *
   * @param context - Arbitrary context describing the current situation.
   * @returns Relevant memories, decisions, intentions, and warnings.
   *
   * @example
   * ```ts
   * const ctx = await lg.recall({ task: 'schedule meeting', with: 'Alice' })
   * console.log(ctx.relevant_memories.length, 'relevant memories found')
   * ```
   */
  async recall(context: Record<string, unknown>): Promise<RecallContext> {
    return this.request<RecallContext>(this.api('/recall'), {
      method: 'POST',
      body: JSON.stringify({ context }),
    })
  }

  /**
   * Recall memories relevant to a specific event within a context.
   *
   * @param context - Arbitrary context describing the current situation.
   * @param event - The event name or description to recall against.
   * @returns Memories relevant to the event in the given context.
   *
   * @example
   * ```ts
   * const mems = await lg.recallEvent(
   *   { project: 'acme' },
   *   'deadline approaching',
   * )
   * ```
   */
  async recallEvent(context: Record<string, unknown>, event: string): Promise<Memory[]> {
    return this.request<Memory[]>(this.api('/recall/event'), {
      method: 'POST',
      body: JSON.stringify({ context, event }),
    })
  }

  // ── Sessions ────────────────────────────────────────────────

  /**
   * Start a new interaction session.
   *
   * @param context - Optional metadata to attach to the session.
   * @returns The newly created session.
   *
   * @example
   * ```ts
   * const session = await lg.startSession({ channel: 'slack' })
   * console.log(session.id)
   * ```
   */
  async startSession(context?: Record<string, unknown>): Promise<Session> {
    const body: Record<string, unknown> = {}
    if (context) body['context'] = context

    const result = await this.request<Session>(this.api('/sessions'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('session:start', { sessionId: result.id })
    return result
  }

  /**
   * End an active session.
   *
   * @param sessionId - The session identifier.
   * @returns The completed session with summary and stats.
   *
   * @example
   * ```ts
   * const ended = await lg.endSession('sess-42')
   * console.log(ended.summary)
   * ```
   */
  async endSession(sessionId: string): Promise<Session> {
    const result = await this.request<Session>(
      this.api(`/sessions/${encodeURIComponent(sessionId)}/end`),
      { method: 'POST' },
    )
    this.emit('session:end', { sessionId })
    return result
  }

  /**
   * Get a single session by ID.
   *
   * @param sessionId - The session identifier.
   * @returns The requested session.
   * @throws {LifeGraphError} 404 if the session does not exist.
   *
   * @example
   * ```ts
   * const s = await lg.session('sess-42')
   * console.log(s.started_at, s.ended_at)
   * ```
   */
  async session(sessionId: string): Promise<Session> {
    return this.request<Session>(this.api(`/sessions/${encodeURIComponent(sessionId)}`))
  }

  /**
   * List recent sessions.
   *
   * @param limit - Maximum number of sessions to return.
   * @returns An array of sessions, most recent first.
   *
   * @example
   * ```ts
   * const recent = await lg.sessions(5)
   * recent.forEach(s => console.log(s.id, s.summary))
   * ```
   */
  async sessions(limit?: number): Promise<Session[]> {
    const query = limit !== undefined ? `?limit=${limit}` : ''
    return this.request<Session[]>(this.api(`/sessions${query}`))
  }

  /**
   * Send a heartbeat to an active session, optionally updating its context.
   *
   * @param sessionId - The session identifier.
   * @param context - Updated context metadata.
   * @returns The updated session.
   *
   * @example
   * ```ts
   * const s = await lg.heartbeat('sess-42', { last_topic: 'project planning' })
   * ```
   */
  async heartbeat(sessionId: string, context: Record<string, unknown>): Promise<Session> {
    const result = await this.request<Session>(
      this.api(`/sessions/${encodeURIComponent(sessionId)}/heartbeat`),
      {
        method: 'POST',
        body: JSON.stringify({ context }),
      },
    )
    this.emit('session:heartbeat', { sessionId })
    return result
  }

  // ── Intentions ──────────────────────────────────────────────

  /**
   * Create a new intention (goal / to-do / reminder).
   *
   * @param content - Human-readable description of the intention.
   * @param options - Optional trigger type, condition, and priority.
   * @returns The newly created intention.
   *
   * @example
   * ```ts
   * const intent = await lg.createIntention('Follow up with Alice', {
   *   trigger_type: 'context',
   *   trigger_condition: 'meeting with Alice',
   *   priority: 'high',
   * })
   * ```
   */
  async createIntention(
    content: string,
    options?: {
      /** How the intention is triggered (e.g. `"context"`, `"time"`, `"manual"`). */
      trigger_type?: string
      /** Condition expression that activates this intention. */
      trigger_condition?: string
      /** Priority level (e.g. `"low"`, `"medium"`, `"high"`). */
      priority?: string
    },
  ): Promise<Intention> {
    const body: Record<string, unknown> = { content }
    if (options?.trigger_type) body['trigger_type'] = options.trigger_type
    if (options?.trigger_condition) body['trigger_condition'] = options.trigger_condition
    if (options?.priority) body['priority'] = options.priority

    const result = await this.request<Intention>(this.api('/intentions'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('intention:created', { id: result.id })
    return result
  }

  /**
   * List all active intentions.
   *
   * @returns An array of intentions.
   *
   * @example
   * ```ts
   * const intents = await lg.intentions()
   * intents.forEach(i => console.log(i.content, i.status))
   * ```
   */
  async intentions(): Promise<Intention[]> {
    return this.request<Intention[]>(this.api('/intentions'))
  }

  /**
   * Get intentions that are triggered by the given context.
   *
   * @param context - The current situational context to evaluate against.
   * @returns Intentions whose trigger conditions match the context.
   *
   * @example
   * ```ts
   * const triggered = await lg.triggeredIntentions({ topic: 'alice' })
   * ```
   */
  async triggeredIntentions(context: Record<string, unknown>): Promise<Intention[]> {
    return this.request<Intention[]>(this.api('/intentions/triggered'), {
      method: 'POST',
      body: JSON.stringify({ context }),
    })
  }

  /**
   * Mark an intention as completed.
   *
   * @param id - The intention identifier.
   * @returns The updated intention with `status: "completed"`.
   *
   * @example
   * ```ts
   * const done = await lg.completeIntention('int-42')
   * console.log(done.status) // "completed"
   * ```
   */
  async completeIntention(id: string): Promise<Intention> {
    const result = await this.request<Intention>(
      this.api(`/intentions/${encodeURIComponent(id)}/complete`),
      { method: 'POST' },
    )
    this.emit('intention:completed', { id })
    return result
  }

  /**
   * Dismiss an intention without completing it.
   *
   * @param id - The intention identifier.
   * @returns The updated intention with `status: "dismissed"`.
   *
   * @example
   * ```ts
   * const dismissed = await lg.dismissIntention('int-42')
   * console.log(dismissed.status) // "dismissed"
   * ```
   */
  async dismissIntention(id: string): Promise<Intention> {
    const result = await this.request<Intention>(
      this.api(`/intentions/${encodeURIComponent(id)}/dismiss`),
      { method: 'POST' },
    )
    this.emit('intention:dismissed', { id })
    return result
  }

  // ── Identity / Timeline ─────────────────────────────────────

  /**
   * Get the identity timeline, optionally filtered by domain.
   *
   * @param domain - Optional domain filter (e.g. `"work"`, `"personal"`).
   * @returns Ordered timeline chapters with active and superseded memories.
   *
   * @example
   * ```ts
   * const chapters = await lg.timeline('work')
   * chapters.forEach(c => console.log(c.period, c.active.length))
   * ```
   */
  async timeline(domain?: string): Promise<TimelineChapter[]> {
    const query = domain ? `?domain=${encodeURIComponent(domain)}` : ''
    return this.request<TimelineChapter[]>(this.api(`/identity/timeline${query}`))
  }

  /**
   * Get current beliefs (high-confidence active memories), optionally filtered by domain.
   *
   * @param domain - Optional domain filter.
   * @returns An array of memories representing current beliefs.
   *
   * @example
   * ```ts
   * const beliefs = await lg.beliefs('personal')
   * ```
   */
  async beliefs(domain?: string): Promise<Memory[]> {
    const query = domain ? `?domain=${encodeURIComponent(domain)}` : ''
    return this.request<Memory[]>(this.api(`/identity/beliefs${query}`))
  }

  /**
   * Get beliefs that may be stale and should be re-evaluated.
   *
   * @param days - Minimum days since last confirmation. Defaults to server setting.
   * @returns An array of stale beliefs with re-evaluation prompts.
   *
   * @example
   * ```ts
   * const stale = await lg.staleBeliefs(90)
   * stale.forEach(s => console.log(s.prompt, `(${s.days_stale} days)`))
   * ```
   */
  async staleBeliefs(days?: number): Promise<StaleBelief[]> {
    const query = days !== undefined ? `?days=${days}` : ''
    return this.request<StaleBelief[]>(this.api(`/identity/beliefs/stale${query}`))
  }

  /**
   * Challenge a specific belief, prompting the system to re-evaluate it.
   *
   * @param memoryId - The memory ID of the belief to challenge.
   * @returns Status of the challenge operation.
   *
   * @example
   * ```ts
   * const result = await lg.challengeBelief('mem-42')
   * console.log(result.message) // "Belief re-evaluation queued"
   * ```
   */
  async challengeBelief(
    memoryId: string,
  ): Promise<{ memory_id: string; status: string; message: string }> {
    return this.request<{ memory_id: string; status: string; message: string }>(
      this.api(`/identity/beliefs/${encodeURIComponent(memoryId)}/challenge`),
      { method: 'POST' },
    )
  }

  // ── Agent Helpers ───────────────────────────────────────────

  /**
   * Build a contextual prompt payload for an agent given a task and optional project.
   *
   * Gathers relevant memories, active intentions, and session history
   * into a single context object suitable for LLM consumption.
   *
   * @param task - Description of the task the agent is performing.
   * @param project - Optional project scope.
   * @returns A context object with memories, intentions, and session info.
   *
   * @example
   * ```ts
   * const ctx = await lg.buildContext('write weekly report', 'acme')
   * // Pass ctx to your LLM prompt
   * ```
   */
  async buildContext(task: string, project?: string): Promise<Record<string, unknown>> {
    const body: Record<string, unknown> = { task }
    if (project) body['project'] = project

    return this.request<Record<string, unknown>>(this.api('/agent/context'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  /**
   * Submit a conversation transcript for the system to learn from.
   *
   * Extracts facts, preferences, and relationships and stores them as memories.
   *
   * @param conversation - The conversation transcript text.
   * @param context - Optional metadata about the conversation.
   * @returns An array of memories created from the conversation.
   *
   * @example
   * ```ts
   * const mems = await lg.learn(
   *   'Alice said she prefers Python over JavaScript for data work.',
   *   { source: 'slack', channel: '#engineering' },
   * )
   * ```
   */
  async learn(conversation: string, context?: Record<string, unknown>): Promise<Memory[]> {
    const body: Record<string, unknown> = { conversation }
    if (context) body['context'] = context

    const result = await this.request<Memory[]>(this.api('/agent/learn'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('memory:created', { count: result.length, source: 'learn' })
    return result
  }

  // ── Admin ───────────────────────────────────────────────────

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
    return this.request<Stats>(this.api('/admin/stats'))
  }

  /**
   * List detected knowledge gaps.
   *
   * @returns An array of knowledge gaps.
   *
   * @example
   * ```ts
   * const gaps = await lg.gaps()
   * gaps.forEach(g => console.log(g.topic, `(asked ${g.query_count}x)`))
   * ```
   */
  async gaps(): Promise<KnowledgeGap[]> {
    return this.request<KnowledgeGap[]>(this.api('/admin/gaps'))
  }

  /**
   * Ingest free-form text and create memories from it.
   *
   * The API will extract entities, relationships, and semantic meaning
   * from the text and persist them as memories in the graph.
   *
   * @param text - The text to ingest.
   * @param context - Optional metadata about the source.
   * @param source - Optional source identifier.
   * @returns An array of newly created memories.
   *
   * @example
   * ```ts
   * const memories = await lg.ingest(
   *   'Had coffee with Alice at Blue Bottle today',
   *   { mood: 'great' },
   *   'journal',
   * )
   * ```
   */
  async ingest(
    text: string,
    context?: Record<string, unknown>,
    source?: string,
  ): Promise<Memory[]> {
    const body: Record<string, unknown> = { text }
    if (context) body['context'] = context
    if (source) body['source'] = source

    const result = await this.request<Memory[]>(this.api('/admin/ingest'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
    this.emit('memory:created', { count: result.length, source: source ?? 'text' })
    return result
  }

  /**
   * Export all memories as a portable JSON archive.
   *
   * @returns An object with version info, memory count, and the full memory array.
   *
   * @example
   * ```ts
   * const archive = await lg.exportMemories()
   * console.log(`Exported ${archive.memory_count} memories (v${archive.version})`)
   * ```
   */
  async exportMemories(): Promise<{
    version: string
    memory_count: number
    memories: Memory[]
  }> {
    return this.request<{ version: string; memory_count: number; memories: Memory[] }>(
      this.api('/admin/export'),
    )
  }

  /**
   * Trigger memory consolidation (deduplication, supersession, summarisation).
   *
   * @returns A result object with consolidation details.
   *
   * @example
   * ```ts
   * const result = await lg.consolidate()
   * console.log(result)
   * ```
   */
  async consolidate(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(this.api('/admin/consolidate'), {
      method: 'POST',
    })
  }

  /**
   * List recent background job runs.
   *
   * @param limit - Maximum number of job runs to return.
   * @returns An array of job run records.
   *
   * @example
   * ```ts
   * const runs = await lg.jobs(10)
   * runs.forEach(j => console.log(j.job_name, j.status))
   * ```
   */
  async jobs(limit?: number): Promise<JobRun[]> {
    const query = limit !== undefined ? `?limit=${limit}` : ''
    return this.request<JobRun[]>(this.api(`/admin/jobs${query}`))
  }

  /**
   * Enqueue a consolidation job to run in the background.
   *
   * @param tenantId - Optional tenant override. Defaults to the client's `tenantId`.
   * @returns An object with the job ID and/or status.
   *
   * @example
   * ```ts
   * const job = await lg.enqueueConsolidation()
   * console.log(job.job_id, job.status)
   * ```
   */
  async enqueueConsolidation(
    tenantId?: string,
  ): Promise<{ job_id?: string; status: string }> {
    const body: Record<string, unknown> = {}
    if (tenantId) body['tenant_id'] = tenantId

    return this.request<{ job_id?: string; status: string }>(
      this.api('/admin/consolidate/enqueue'),
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    )
  }

  // ── Knowledge Graph ─────────────────────────────────────────

  /**
   * List entities in the knowledge graph, optionally filtered by label.
   *
   * @param label - Optional Neo4j label to filter by (e.g. `"Person"`).
   * @returns Array of matching entities.
   *
   * @example
   * ```ts
   * const people = await lg.entities('Person')
   * ```
   */
  async entities(label?: string): Promise<GraphEntity[]> {
    const query = label ? `?label=${encodeURIComponent(label)}` : ''
    return this.request<GraphEntity[]>(this.api(`/graph/entities${query}`))
  }

  /**
   * Get full details for a named entity, including its neighbours and edges.
   *
   * @param name - The entity name.
   * @returns Entity detail with neighbourhood and associated memories.
   * @throws {LifeGraphError} 404 if the entity does not exist.
   *
   * @example
   * ```ts
   * const detail = await lg.entity('Alice')
   * console.log(detail.neighbors.map(n => n.name))
   * ```
   */
  async entity(name: string): Promise<EntityDetail> {
    return this.request<EntityDetail>(this.api(`/graph/entity/${encodeURIComponent(name)}`))
  }

  /**
   * Execute a raw Cypher query against the knowledge graph.
   *
   * @param cypher - A valid Cypher query string.
   * @param params - Optional query parameters for parameterised queries.
   * @param columns - Optional list of column names to return.
   * @returns Array of result rows.
   *
   * @example
   * ```ts
   * const rows = await lg.graphQuery(
   *   'MATCH (a:Person)-[:KNOWS]->(b:Person) WHERE a.name = $name RETURN b.name',
   *   { name: 'Alice' },
   *   ['b.name'],
   * )
   * ```
   */
  async graphQuery(
    cypher: string,
    params?: Record<string, unknown>,
    columns?: string[],
  ): Promise<unknown[]> {
    const body: Record<string, unknown> = { cypher }
    if (params) body['params'] = params
    if (columns?.length) body['columns'] = columns

    return this.request<unknown[]>(this.api('/graph/query'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  /**
   * Find the shortest path between two entities in the graph.
   *
   * @param from - Source entity name.
   * @param to - Target entity name.
   * @param maxDepth - Maximum path depth. Defaults to server setting.
   * @returns The path with ordered edges and hop count.
   *
   * @example
   * ```ts
   * const path = await lg.graphPath('Alice', 'Bob', 5)
   * console.log(`${path.length} hops`)
   * ```
   */
  async graphPath(from: string, to: string, maxDepth?: number): Promise<PathResult> {
    const params = new URLSearchParams({
      from_name: from,
      to_name: to,
    })
    if (maxDepth !== undefined) params.set('max_depth', String(maxDepth))

    return this.request<PathResult>(this.api(`/graph/path?${params.toString()}`))
  }

  /**
   * Hybrid search combining semantic similarity with graph structure.
   *
   * @param query - Natural language search query.
   * @param options - Optional filters for label, limit, and minimum importance.
   * @returns A result object with ranked search results and related entities.
   *
   * @example
   * ```ts
   * const results = await lg.graphSearch('coffee shops', {
   *   label: 'Place',
   *   limit: 5,
   *   min_importance: 0.5,
   * })
   * console.log(results.results.length, 'matches')
   * ```
   */
  async graphSearch(
    query: string,
    options?: {
      /** Entity label filter. */
      label?: string
      /** Maximum number of results. */
      limit?: number
      /** Minimum importance threshold. */
      min_importance?: number
    },
  ): Promise<GraphSearchResult> {
    const body: Record<string, unknown> = {
      query,
      limit: options?.limit ?? 10,
    }
    if (options?.label) body['label'] = options.label
    if (options?.min_importance !== undefined) body['min_importance'] = options.min_importance

    return this.request<GraphSearchResult>(this.api('/graph/search'), {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  // ── Multimodal Ingestion ────────────────────────────────────

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
    const result = await this.upload<IngestResult>(this.api('/ingest/voice'), file)
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
    const result = await this.upload<IngestResult>(this.api('/ingest/image'), file)
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
    const result = await this.upload<IngestResult>(this.api('/ingest/document'), file)
    this.emit('document:imported', {
      memories_created: result.memories_created,
      chunks: result.chunks,
    })
    return result
  }

  // ── Convenience ─────────────────────────────────────────────

  /**
   * Convenience alias for {@link ingest} — ingest free-form text.
   *
   * @param text - The text to remember.
   * @returns An array of newly created memories.
   *
   * @example
   * ```ts
   * const memories = await lg.remember('I had coffee with Alice at Blue Bottle today')
   * console.log(`Created ${memories.length} memories`)
   * ```
   */
  async remember(text: string): Promise<Memory[]> {
    return this.ingest(text)
  }

  // ── Events (client-side) ────────────────────────────────────

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
