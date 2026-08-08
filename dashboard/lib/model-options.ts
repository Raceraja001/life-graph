// Curated model choices for the persona model picker. Grouped by cost so a
// cost-conscious choice is visible at a glance. Adding a genuinely new model
// here is a small dashboard-only code change — no backend redeploy needed.
export const MODEL_OPTIONS: { Free: string[]; Paid: string[] } = {
  Free: [
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/openai/gpt-oss-20b:free",
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
  ],
  Paid: [
    "gemini/gemini-3.6-flash",
    "gemini/gemini-3.5-flash-lite",
    "openrouter/deepseek/deepseek-chat",
    "claude-cli",
  ],
};
