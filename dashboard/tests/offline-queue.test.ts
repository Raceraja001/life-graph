// fake-indexeddb must be imported before the module under test reads
// `typeof indexedDB` — happy-dom does not implement IndexedDB.
import "fake-indexeddb/auto";

import { beforeEach, describe, expect, it } from "vitest";
import { count, enqueue, getAll, remove } from "@/lib/offline-queue";

// This queue holds captures made while offline and is flushed to /kernel/route
// on reconnect. A silent failure here loses whatever the user typed with no
// network, which is the one situation where nothing else has a copy.

async function drain() {
  for (const item of await getAll()) await remove(item.id);
}

describe("offline capture queue", () => {
  beforeEach(drain);

  it("starts empty", async () => {
    expect(await count()).toBe(0);
    expect(await getAll()).toEqual([]);
  });

  it("enqueues and returns the stored item", async () => {
    const item = await enqueue("captured while offline");

    expect(item).not.toBeNull();
    expect(item!.content).toBe("captured while offline");
    expect(item!.id).toBeTruthy();
    expect(item!.createdAt).toBeTypeOf("number");
  });

  it("persists across reads", async () => {
    await enqueue("one");
    await enqueue("two");

    expect(await count()).toBe(2);
    expect((await getAll()).map((i) => i.content)).toEqual(["one", "two"]);
  });

  it("returns items oldest-first so replay preserves order", async () => {
    const a = await enqueue("first");
    const b = await enqueue("second");
    // guard against same-millisecond creation making the order arbitrary
    expect(b!.createdAt).toBeGreaterThanOrEqual(a!.createdAt);

    const ids = (await getAll()).map((i) => i.id);
    expect(ids.indexOf(a!.id)).toBeLessThan(ids.indexOf(b!.id));
  });

  it("assigns unique ids", async () => {
    const items = await Promise.all([enqueue("a"), enqueue("b"), enqueue("c")]);
    const ids = items.map((i) => i!.id);
    expect(new Set(ids).size).toBe(3);
  });

  it("removes only the named item", async () => {
    const keep = await enqueue("keep");
    const drop = await enqueue("drop");

    await remove(drop!.id);

    const left = await getAll();
    expect(left).toHaveLength(1);
    expect(left[0].id).toBe(keep!.id);
  });

  it("removing an unknown id is a no-op", async () => {
    await enqueue("still here");
    await remove("no-such-id");
    expect(await count()).toBe(1);
  });

  it("preserves empty content rather than dropping it", async () => {
    const item = await enqueue("");
    expect(item).not.toBeNull();
    expect((await getAll())[0].content).toBe("");
  });

  it("round-trips unicode and newlines intact", async () => {
    const content = "line one\nline two — ✓ 日本語";
    await enqueue(content);
    expect((await getAll())[0].content).toBe(content);
  });
});
