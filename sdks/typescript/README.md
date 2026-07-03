# @life-graph/sdk

TypeScript SDK for the **Life Graph** memory system — zero runtime dependencies, full type safety, works in browsers and Node.js 18+.

## Installation

```bash
npm install @life-graph/sdk
# or
pnpm add @life-graph/sdk
# or
yarn add @life-graph/sdk
```

## Quick Start

```typescript
import { LifeGraph } from '@life-graph/sdk'

const lg = new LifeGraph({ apiUrl: 'http://localhost:8000' })

// Store a memory
const memories = await lg.remember('Had coffee with Alice at Blue Bottle today')
console.log(`Created ${memories.length} memories`)

// Search memories
const results = await lg.search('coffee')
results.forEach(r => console.log(r.content, r.score))

// Check system health
const health = await lg.health()
console.log(health.version)
```

## Configuration

```typescript
const lg = new LifeGraph({
  apiUrl: 'http://localhost:8000',  // Required — API base URL
  apiKey: 'your-api-key',           // Optional — Bearer token
  timeout: 30000,                   // Optional — request timeout in ms (default: 30s)
})
```

---

## API Reference

### Health

| Method | Returns | Description |
|--------|---------|-------------|
| `health()` | `HealthStatus` | Full health check with version info |
| `ping()` | `boolean` | Quick connectivity check — `true` if API is reachable |

```typescript
if (await lg.ping()) {
  const h = await lg.health()
  console.log(`Life Graph v${h.version} is online`)
}
```

### Memory CRUD

| Method | Returns | Description |
|--------|---------|-------------|
| `memories()` | `Memory[]` | List all memories |
| `memory(id)` | `Memory` | Get a single memory by ID |
| `deleteMemory(id)` | `void` | Delete a memory by ID |

```typescript
const all = await lg.memories()
const one = await lg.memory(all[0].id)
await lg.deleteMemory(one.id)
```

### Text Ingestion

| Method | Returns | Description |
|--------|---------|-------------|
| `remember(text)` | `Memory[]` | Ingest text → extract entities → create memories |

```typescript
const memories = await lg.remember(`
  Met with Bob and Carol at the park.
  We discussed the Q3 roadmap and decided to focus on mobile.
`)
```

### Multi-Modal Ingestion

| Method | Returns | Description |
|--------|---------|-------------|
| `ingestVoice(file)` | `IngestResult` | Upload audio → transcribe → create memories |
| `ingestImage(file)` | `IngestResult` | Upload image → OCR → create memories |
| `ingestDocument(file)` | `IngestResult` | Upload document → extract text → create memories |

```typescript
// Voice
const audioBlob = new Blob([audioBuffer], { type: 'audio/webm' })
const voiceResult = await lg.ingestVoice(audioBlob)
console.log(voiceResult.transcript)

// Image
const imageResult = await lg.ingestImage(imageFile)
console.log(imageResult.ocr_text)

// Document (PDF, DOCX, etc.)
const docResult = await lg.ingestDocument(pdfFile)
console.log(`${docResult.chunks} chunks → ${docResult.memories_created} memories`)
```

### Search

| Method | Returns | Description |
|--------|---------|-------------|
| `search(query, options?)` | `SearchResult[]` | Semantic search across all memories |

**Options:**
- `limit` — max results (default: 10)
- `tags` — filter by tags

```typescript
const results = await lg.search('meetings about roadmap', { limit: 5 })
results.forEach(r => {
  console.log(`[${r.score?.toFixed(2)}] ${r.content}`)
})
```

### Knowledge Graph

| Method | Returns | Description |
|--------|---------|-------------|
| `entities(label?)` | `GraphEntity[]` | List entities, optionally filtered by label |
| `entity(name)` | `EntityDetail` | Get entity detail with neighbors and edges |
| `graphQuery(cypher, columns?)` | `any[]` | Execute raw Cypher query |
| `graphPath(from, to)` | `PathResult` | Find shortest path between two entities |
| `graphSearch(query, filter?, limit?)` | `SearchResult[]` | Hybrid semantic + graph search |

```typescript
// List all people
const people = await lg.entities('Person')

// Explore Alice's connections
const alice = await lg.entity('Alice')
console.log(alice.neighbors.map(n => n.name))

// Raw Cypher
const rows = await lg.graphQuery(
  'MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name',
  ['a.name', 'b.name']
)

// Shortest path
const path = await lg.graphPath('Alice', 'Bob')
console.log(`${path.length} hops: ${path.path.map(e => e.label).join(' → ')}`)

// Hybrid search
const hybrid = await lg.graphSearch('coffee', { label: 'Place' }, 5)
```

### Admin & Stats

| Method | Returns | Description |
|--------|---------|-------------|
| `stats()` | `Stats` | System statistics (memory count, sessions, etc.) |

```typescript
const s = await lg.stats()
console.log(`${s.memory_count} memories across ${s.session_count} sessions`)
```

### Events

Client-side event emitter for reacting to SDK operations:

```typescript
// Listen for specific events
const unsub = lg.on('memory:created', (event) => {
  console.log('New memory created:', event.payload)
})

// Listen to everything
lg.on('*', (event) => {
  console.log(`[${event.type}]`, event.payload)
})

// Unsubscribe
unsub()
// or: lg.off('memory:created', handler)
```

**Available events:**
`memory:created` · `memory:retrieved` · `memory:updated` · `memory:deleted` · `session:start` · `session:end` · `voice:transcribed` · `image:processed` · `document:imported`

### Error Handling

All API errors throw `LifeGraphError` with the HTTP status code:

```typescript
import { LifeGraphError } from '@life-graph/sdk'

try {
  await lg.memory('nonexistent-id')
} catch (err) {
  if (err instanceof LifeGraphError) {
    console.log(err.statusCode) // 404
    console.log(err.message)    // "404 Not Found: ..."
  }
}
```

---

## React Integration

The SDK ships optional React hooks. Requires React 18+ as a peer dependency.

### Setup

```tsx
import { initLifeGraph } from '@life-graph/sdk'

// Call once at app startup
initLifeGraph({ apiUrl: 'http://localhost:8000' })
```

### Hooks

#### `useBrain()`

Returns the shared LifeGraph client instance.

```tsx
import { useBrain } from '@life-graph/sdk'

function RememberButton() {
  const brain = useBrain()

  const save = async () => {
    await brain.remember('User clicked the remember button')
  }

  return <button onClick={save}>Remember This</button>
}
```

#### `useSearch(query, limit?)`

Reactive semantic search — re-runs when `query` changes.

```tsx
import { useSearch } from '@life-graph/sdk'

function SearchBox() {
  const [q, setQ] = useState('')
  const { results, loading, error } = useSearch(q)

  return (
    <div>
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search memories…" />
      {loading && <p>Searching…</p>}
      {error && <p>Error: {error.message}</p>}
      {results.map(r => (
        <div key={r.content}>
          <p>{r.content}</p>
          <small>Score: {r.score?.toFixed(2)}</small>
        </div>
      ))}
    </div>
  )
}
```

#### `useMemories()`

Fetches all memories with manual refresh.

```tsx
import { useMemories } from '@life-graph/sdk'

function MemoryList() {
  const { memories, loading, refresh } = useMemories()

  return (
    <div>
      <button onClick={refresh}>↻ Refresh</button>
      {memories.map(m => <p key={m.id}>{m.content}</p>)}
    </div>
  )
}
```

#### `useStats()`

Reactive system statistics.

```tsx
import { useStats } from '@life-graph/sdk'

function Dashboard() {
  const { stats, loading } = useStats()
  if (loading || !stats) return <p>Loading…</p>

  return (
    <ul>
      <li>{stats.memory_count} memories</li>
      <li>{stats.session_count} sessions</li>
      <li>{stats.intention_count} intentions</li>
      <li>{stats.gap_count} knowledge gaps</li>
    </ul>
  )
}
```

---

## Integration Examples

### Web App (Vanilla)

```html
<script type="module">
  import { LifeGraph } from './node_modules/@life-graph/sdk/dist/index.mjs'

  const lg = new LifeGraph({ apiUrl: 'http://localhost:8000' })

  document.getElementById('search-form').addEventListener('submit', async (e) => {
    e.preventDefault()
    const query = document.getElementById('query').value
    const results = await lg.search(query)
    document.getElementById('results').innerHTML =
      results.map(r => `<p>${r.content} (${r.score?.toFixed(2)})</p>`).join('')
  })
</script>
```

### React Native

```tsx
import { LifeGraph } from '@life-graph/sdk'

const lg = new LifeGraph({ apiUrl: 'https://your-api.example.com' })

export function useLifeGraph() {
  const remember = async (text: string) => {
    return lg.remember(text)
  }

  const search = async (query: string) => {
    return lg.search(query, { limit: 20 })
  }

  return { remember, search, lg }
}
```

### Chrome Extension

```typescript
// background.ts
import { LifeGraph } from '@life-graph/sdk'

const lg = new LifeGraph({ apiUrl: 'http://localhost:8000' })

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'REMEMBER') {
    lg.remember(msg.text).then(sendResponse)
    return true // async response
  }
  if (msg.type === 'SEARCH') {
    lg.search(msg.query).then(sendResponse)
    return true
  }
})
```

### Node.js Script

```typescript
import { LifeGraph } from '@life-graph/sdk'

async function main() {
  const lg = new LifeGraph({ apiUrl: 'http://localhost:8000' })

  // Check connectivity
  if (!(await lg.ping())) {
    console.error('Life Graph API is not reachable')
    process.exit(1)
  }

  // Ingest a journal entry
  const memories = await lg.remember(`
    Today I learned about graph databases.
    Neo4j uses Cypher as its query language.
    I found it similar to SQL but for graph traversals.
  `)
  console.log(`Created ${memories.length} memories`)

  // Search
  const results = await lg.search('graph databases')
  console.log('Search results:')
  results.forEach(r => console.log(`  - ${r.content}`))

  // Stats
  const stats = await lg.stats()
  console.log(`Total: ${stats.memory_count} memories`)
}

main().catch(console.error)
```

---

## Types

All TypeScript interfaces are exported for full type safety:

```typescript
import type {
  Memory,
  SearchResult,
  SearchOptions,
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
  LifeGraphConfig,
} from '@life-graph/sdk'
```

## License

MIT
