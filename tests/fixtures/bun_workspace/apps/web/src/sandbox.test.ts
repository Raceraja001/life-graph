// Runs inside the verifier sandbox (tests/unit/test_bun_sandbox_smoke.py).
import { expect, test } from "bun:test";
import { writeFileSync } from "node:fs";
import isNumber from "is-number";
import { parity } from "@fx/lib";

test("workspace and registry dependencies resolve from the mounted node_modules", () => {
  expect(isNumber(5)).toBe(true);
  expect(parity(3)).toBe("odd");
});

test("the worktree is read-only", () => {
  expect(() => writeFileSync("/work/escaped.txt", "x")).toThrow();
  expect(() => writeFileSync("/work/node_modules/escaped.txt", "x")).toThrow();
});

test("there is no network", async () => {
  await expect(fetch("https://registry.npmjs.org/")).rejects.toThrow();
});
