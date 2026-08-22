// Deliberately does NOT import fake-indexeddb: this file asserts the
// degradation path taken during SSR and in browsers with storage disabled,
// where `typeof indexedDB === "undefined"`. Every export must no-op rather
// than throw — an exception here would break the whole capture surface.
import { describe, expect, it } from "vitest";
import { count, enqueue, getAll, remove } from "@/lib/offline-queue";

describe("offline queue without IndexedDB", () => {
  it("confirms the environment really has no IndexedDB", () => {
    expect(typeof indexedDB).toBe("undefined");
  });

  it("enqueue returns null instead of throwing", async () => {
    await expect(enqueue("dropped")).resolves.toBeNull();
  });

  it("getAll returns an empty array", async () => {
    await expect(getAll()).resolves.toEqual([]);
  });

  it("count returns 0", async () => {
    await expect(count()).resolves.toBe(0);
  });

  it("remove resolves quietly", async () => {
    await expect(remove("anything")).resolves.toBeUndefined();
  });
});
