// IndexedDB-backed queue for captures made while offline. The app flushes it
// to /kernel/route on reconnect. Kept deliberately tiny — no external dep.

const DB_NAME = "life-graph-mobile";
const STORE = "capture-queue";
const VERSION = 1;

export interface QueueItem {
  id: string;
  content: string;
  createdAt: number;
  /**
   * Tiebreak for items enqueued within the same millisecond.
   *
   * createdAt is Date.now(), so two captures made in quick succession share a
   * timestamp and sorting by it alone leaves their replay order undefined.
   * Absent on rows written before this field existed, hence the ?? 0 below.
   */
  seq?: number;
}

// Monotonic within a page session, which is the window in which same-
// millisecond collisions actually happen. Across sessions createdAt separates
// the items on its own.
let seq = 0;

function available() {
  return typeof indexedDB !== "undefined";
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.round(Math.random() * 1e9)}`;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const req = fn(db.transaction(STORE, mode).objectStore(STORE));
      req.onsuccess = () => resolve(req.result as T);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

export async function enqueue(content: string): Promise<QueueItem | null> {
  if (!available()) return null;
  const item: QueueItem = { id: newId(), content, createdAt: Date.now(), seq: seq++ };
  await withStore("readwrite", (s) => s.add(item));
  return item;
}

export async function getAll(): Promise<QueueItem[]> {
  if (!available()) return [];
  const items = await withStore<QueueItem[]>("readonly", (s) => s.getAll());
  return (items ?? []).sort(
    (a, b) => a.createdAt - b.createdAt || (a.seq ?? 0) - (b.seq ?? 0),
  );
}

export async function remove(id: string): Promise<void> {
  if (!available()) return;
  await withStore("readwrite", (s) => s.delete(id));
}

export async function count(): Promise<number> {
  if (!available()) return 0;
  return (await withStore<number>("readonly", (s) => s.count())) ?? 0;
}
