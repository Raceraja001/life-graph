# What Life Graph and Jarvis can do (for the feature watch)

The feature watch (services/feature_ideas.py) compares each new feature in other
apps with this list, to say whether Life Graph already has it (**have**), has a
piece of it (**part**), or not (**new**). Keep it short and current: one line per
capability, plain words. Update it when something ships.

## Chat
- Chat with personas (Jarvis leads; Scout research, Admin bills/mail, Tutor study, SWE lead code); a persona can hand a task to another, shown in the chat.
- Replies stream; markdown, code and tables render.
- One thread per persona in the web UI (kept in the browser); no conversation list, search, pinning, edit or regenerate yet.
- Phone app chat with cards (people, bills, approvals) and follow-up suggestions; voice mode on the phone.
- Telegram chat with voice messages.

## Memory
- Remembers what the owner says ("remember …" saves at once, with Undo on the phone); forgets on request.
- New memories wait in a review queue (Keep / Reject); unreviewed ones drop after 14 days.
- Daily summaries of conversations and work (episodes); questions about a time ("last Tuesday") find them.
- People, projects and things the memories mention, each with its own page.
- Search by meaning and words across memories.

## Knowing the day
- Daily brief (text and audio): waiting approvals, coming up, memory, night shift, tech watch, questions.
- Calendar, mail, contacts, tasks and bills from connected accounts (read-only); promises found in mail.
- Reminders, set from chat by the owner's own words.

## Life admin
- Money: transactions, budgets, monthly check-in, bank alert import.
- Documents with expiry reminders; invoices; study cards with spaced repetition; page monitors (price drops, changes).

## Research
- Research on demand: every claim with its source page.
- Tech watch: new models, coding agents and app features each night.
- Free LLM offers found and evaluated.

## Agents and code
- Dev tasks: personas change code in a project's worktree, checked by verifiers, returned as a PR for approval.
- Approvals inbox with evidence (checks, diff); scorecards, failures, budget.
- MCP server (local and over HTTP) so other assistants can use Life Graph's tools.

## Privacy and access
- Personal data goes only to local models; outside content (pages, mail, shared text) cannot trigger saves or tools.
- Paid spend capped monthly; local runs free.
- Reachable from the owner's other machines over Tailscale; phone pairs with a one-time code.
