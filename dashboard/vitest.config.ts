import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "happy-dom",
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    globals: true,
    restoreMocks: true,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
