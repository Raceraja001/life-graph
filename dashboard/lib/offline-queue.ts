// IndexedDB-backed queue for captures made while offline. The app flushes it
// to /kernel/route on reconnect. Kept deliberately tiny — no external dep.

const DB_NAME = "life-graph-mobile";
const STORE = "capture-queue";
const VERSION = 1;

export interface QueueItem {
  id: string;
  content: string;
  createdAt: number;
}

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
  const item: QueueItem = { id: newId(), content, createdAt: Date.now() };
  await withStore("readwrite", (s) => s.add(item));
  return item;
}

export async function getAll(): Promise<QueueItem[]> {
  if (!available()) return [];
  const items = await withStore<QueueItem[]>("readonly", (s) => s.getAll());
  return (items ?? []).sort((a, b) => a.createdAt - b.createdAt);
}

export async function remove(id: string): Promise<void> {
  if (!available()) return;
  await withStore("readwrite", (s) => s.delete(id));
}

export async function count(): Promise<number> {
  if (!available()) return 0;
  return (await withStore<number>("readonly", (s) => s.count())) ?? 0;
}
