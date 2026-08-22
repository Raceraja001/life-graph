import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // An underscore prefix is this codebase's existing marker for a
      // deliberately unused parameter — the stub hooks in lib/hooks.ts keep
      // their real signatures so the call sites do not change when the
      // feature is built. Flagging those was noise.
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

      // `any` is warned, not errored. The backend returns loosely-typed JSON
      // envelopes and the client mappers (lib/mobile-api.ts) exist precisely
      // to narrow them at the edge; lib/api.ts already carries an explicit
      // eslint-disable saying so. Typing all 86 sites would mean inventing
      // interfaces for payloads the server is free to change, and the mappers
      // — which is where wrong assumptions actually bite — are covered by
      // tests instead. Left visible as warnings so the debt is not hidden.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
]);

export default eslintConfig;
