# Web chat, wave 1: Jarvis that acts, explains and forgets on request

Status: planned 2026-10-27. Web app only (life-graph-ui on :3006); the phone and other devices
come later. The owner's rule: features first, design second — each feature ships with a plain
UI on the existing template, the chat layout is mockup B (conversation list · chat · side panel)
on assistant-ui components, and no design rounds hold a feature back.

Six features, in build order. Each task is marked **[free]** (a single file with its unit test,
for the queue: OpenCode or the local model) or **[claude]** (wiring, database tests, the UI).
Free engines are reliable on scoped single-file tasks and weak on DB-mocked tests
(docs/specs/agent-condenser.md benchmark), so every database touch is [claude].

What exists (mapped 2026-10-27):

- Runtime schedules: `ScheduledJob` rows (`models/agents.py:261`, `properties` JSONB),
  `SchedulerService` (`kernel/scheduler.py:161`), fired every minute by
  `workers/tasks.py:tick_scheduled_jobs`; API `/kernel/schedules` (create, list, PATCH
  `is_active`, soft DELETE). `CronExpression` is 5-field, UTC, day-of-week 0 = Sunday.
- Chat: the web UI streams `POST /kernel/chat/stream`; the phone uses `POST /jarvis/chat`, which
  wraps it, captures the owner's words to memory and maps events to cards. A conversation is an
  `AgentSession` (`context` JSONB), a turn an `AgentTask` (`result` JSONB with `route`).
- Privacy route: `services/lead.py:route()` → personal (local) | general; `local:` prefix forces local.
- Recall: `services/memory_context.py:memory_block` on personal runs.
- Reminders: `tools/reminders.py:reminder_set` → `Intention(trigger_type="time")`; due
  `Notification` rows every 15 min; Web Push and Telegram for the brief.
- Promises in sent mail: `connectors/store.py:open_promises`.
- Outside content: `core/run_taint.py` — a tainted run cannot use write tools unless the owner's
  own typed words ask for it (`REMIND_INTENT`).
- `settings.user_timezone` (IANA) is the owner's time zone.

---

## F1 · Jarvis acts on its own (scheduled asks)

"Every Monday at 9, summarise my week." "Each evening, tell me what's due tomorrow." The owner
asks once; Jarvis runs it, says the result in the chat, and the ask can be paused or removed.

- **AC-W1.1** A new tool `ask_schedule(when, ask)` turns the owner's words into a `ScheduledJob`
  with `agent_name="jarvis"`, `properties={"origin": "chat", "ask": <owner's words>,
  "session_id": <the chat>, "when": <their phrase>}`. Like `reminder_set`, it works on a
  tainted run only when the owner's typed message asks for it; text from a page or mail never
  creates one. The reply confirms in plain words ("Every Monday at 09:00 — I'll summarise your week").
- **AC-W1.2** `parse_recurrence(text, tz)` maps the phrase to a UTC cron (see T1.1); a phrase it
  cannot read gets a question back, not a guess.
- **AC-W1.3** When it fires, the ask runs as the owner's message on the **personal** route (local
  model, memory recall on), with the same tools as chat. The reply is stored as a turn in that
  chat's session (marked `origin: "scheduled"`) and a `Notification` is written, so the phone and
  Web Push see it.
- **AC-W1.4** `GET /jarvis/asks` lists chat-origin schedules (phrase, next run, last result,
  active); `PATCH /jarvis/asks/{id}` `{active}` pauses/resumes; `DELETE` deactivates. Other
  tenants' and non-chat schedules are not listed.
- **AC-W1.5** Max 20 active asks per tenant; a 21st is refused in the reply.

Tasks:
- **T1.1 [free]** `life_graph/services/recurrence.py` — `parse_recurrence(text: str, tz: str) ->
  str | None`, pure, with `tests/unit/test_recurrence.py`. Phrases: "every day at 7", "every
  morning" (07:00), "each evening" (19:00), "every Monday at 9", "every weekday at 8:30",
  "every Sunday evening", "every hour", "every 2 hours", "on the 1st of every month at 10". Times
  are in *tz* and converted to UTC, shifting the weekday when the hour crosses midnight
  (Asia/Kolkata 09:00 Monday → `30 3 * * 1`; 02:00 Monday → `30 20 * * 0`). Day-of-week 0 =
  Sunday. Anything else → None.
- **T1.2 [claude]** `tools/schedules.py` `ask_schedule`, owner-words guard, the cap; register it
  for jarvis.
- **T1.3 [claude]** `tick_scheduled_jobs`: chat-origin jobs run as a jarvis turn in their session,
  personal route, then a Notification. Integration test with a fake worker.
- **T1.4 [claude]** `/jarvis/asks` list / pause / delete.
- **T1.5 [claude, UI]** side panel "Running on its own": the asks, next run, last result, pause.

## F2 · Nudges from your own words

"You said on Tuesday you'd call the insurer this week." At the right time, at most a few a day,
never from what someone else wrote.

- **AC-W2.1** A commitment is only ever taken from the owner's own words: their chat messages
  (captured with the owner trust tier) and their *sent* mail promises (`open_promises`). Shared
  text, received mail and web pages never make one.
- **AC-W2.2** After each chat turn, a local-model check reads the owner's message for a
  commitment with a time ("this week", "by Friday", "tomorrow") and stores it as an `Intention`
  (`trigger_type="nudge"`, `due_from`, `due_by`, the owner's sentence). Reminders the owner set
  explicitly stay reminders.
- **AC-W2.3** A job every 30 minutes picks what to nudge (T2.1): due now, not snoozed, outside
  quiet hours, at most 3 a day; each becomes a chat message in the owner's main thread plus a
  Notification, with **Done**, **Tomorrow** and **Drop**.
- **AC-W2.4** Done/Tomorrow/Drop are recorded; a dropped one never comes back. The brief lists
  open ones under "You said you would".

Tasks:
- **T2.1 [free]** `life_graph/services/nudge_pick.py` — `pick(candidates, now, *, sent_today,
  quiet_hours=(22, 7), max_per_day=3) -> list` over plain dicts (`id`, `due_from`, `due_by`,
  `snoozed_until`, `state`), soonest `due_by` first; unit tests for each rule.
- **T2.2 [claude]** commitment extraction (local model, validated JSON, owner messages only).
- **T2.3 [claude]** the nudge job, the three actions, the brief section.
- **T2.4 [claude, UI]** nudge messages with their buttons in chat; open ones in the side panel.

## F3 · Every answer shows its working

Under each reply: the memories it used (each with "that's wrong"), the tools it ran, the model,
and a lock when nothing left the PC.

- **AC-W3.1** Each chat turn's `AgentTask.result["trace"]` records: `route` (kind, model,
  reason), `local` (true only if every model call in the turn was local), `memories` (ids and a
  60-character snippet of each recalled memory that went into the prompt), `tools` (name, ok,
  ms — never arguments or results).
- **AC-W3.2** `GET /jarvis/turns/{task_id}/trace` returns it, tenant-checked.
- **AC-W3.3** "That's wrong" on a memory sends it back to review (pending, never deleted) with
  the owner's note; the next recall leaves it out.
- **AC-W3.4** The UI shows a lock for local turns and "cloud — <reason>" otherwise.

Tasks:
- **T3.1 [free]** `life_graph/services/turn_trace.py` — `build_trace(route, model_calls,
  memories, tool_calls) -> dict` and `summary_line(trace) -> str` ("Local · 3 memories · 2
  tools"), pure, with tests (snippet cut, local only when all calls local, no tool args kept).
- **T3.2 [claude]** `memory_block` returns the ids it injected; the orchestrator collects tool
  name/ok/ms; `_run_agent` stores the trace.
- **T3.3 [claude]** trace endpoint; "that's wrong" → memory back to pending with a note.
- **T3.4 [claude, UI]** "How I answered" under each reply; lock / cloud marker.

## F4 · Do it from the reply

Approve, pay, remind, open the PR — from the message, with the inbox's honest labels.

- **AC-W4.1** The web chat moves from `/kernel/chat/stream` to `/jarvis/chat`, so it gets the
  phone's cards, follow-ups and memory capture (the same thread rules as the phone).
- **AC-W4.2** Cards render with their actions: an approval (the inbox's GROUPS labels and
  confirm), a bill (mark paid), a reminder (cancel), a PR (open, review in VS Code). Every
  action asks before it acts and says what it will do.
- **AC-W4.3** An action taken in chat shows as resolved in Approvals and vice versa.

Tasks:
- **T4.1 [claude, UI]** chat client on `/jarvis/chat`, card components reusing `lib/inbox.ts`.
- **T4.2 [claude]** any missing card kinds in `api/jarvis.py:_app_event`.

## F5 · Temporary chat

One switch: local model only, nothing remembered.

- **AC-W5.1** `POST /jarvis/chat` with `temporary: true` (and a session created with it): the
  route is forced personal/local; nothing is captured; memory_save, memory_forget,
  reminder_set and ask_schedule are not offered; the session's `context.temporary` is set.
- **AC-W5.2** Temporary sessions never appear in the conversation list, search, episodes or the
  brief, and their turns are purged 24 hours after the last message.
- **AC-W5.3** The UI shows the switch at the start of a chat and a banner while it is on.

Tasks:
- **T5.1 [claude]** the flag through `/jarvis/chat` → `chat_stream` → `_run_agent` (route, tools,
  capture); integration test that nothing is stored as memory.
- **T5.2 [claude]** exclusions and the purge job.
- **T5.3 [claude, UI]** the switch and banner.

## F6 · A chat history that remembers

Every past chat, searchable by words; pin and rename; regenerate a reply with another persona
or model and keep both.

- **AC-W6.1** `GET /jarvis/conversations?q=` searches the owner's messages and replies
  (Postgres full text, newest first), skipping temporary sessions.
- **AC-W6.2** `PATCH /jarvis/conversations/{id}` `{title, pinned}` (in `AgentSession.context`);
  pinned first in the list.
- **AC-W6.3** `POST /jarvis/turns/{task_id}/regenerate` `{persona?, model?}` re-runs the turn;
  the new turn links `regenerates`; the UI switches between versions.

Tasks:
- **T6.1 [free]** `life_graph/services/chat_title.py` — `title_for(first_message) -> str`
  (≤ 60 characters, no trailing punctuation, strips `local:`/`personal:` prefixes and URLs),
  with tests.
- **T6.2 [claude]** search, pin/rename, regenerate.
- **T6.3 [claude, UI]** conversation list with search and pins; version switcher.

---

## The shared UI (built once, by Claude)

life-graph-ui `ChatPage` on assistant-ui: conversation list (F6) · chat with cards (F4),
"How I answered" (F3) and the temporary switch (F5) · side panel with "Running on its own" (F1)
and nudges (F2). Plain template styling; polish later.

## Order

1. Queue T1.1, T2.1, T3.1, T6.1 (free) tonight.
2. Claude: T5.1–T5.2 and T3.2–T3.3 (small, foundational), then T1.2–T1.4.
3. The shared UI with F1, F3, F5; then F2, F4, F6.
Each feature lands as its own PR; deploys are asked for.
