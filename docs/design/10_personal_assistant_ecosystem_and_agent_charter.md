# 10. Personal Assistant Ecosystem

> **Status:** Active design | **Last updated:** 2026-10-19
>
> Why Life Graph exists for its owner, and how the repos around it fit together. The rules
> themselves (one tenant, personal data stays local) are invariants in
> [CHARTER.md](../../CHARTER.md#design-invariants); this page is the context for them.
> Exact endpoints, models and jobs live in [STATE.md](../STATE.md); no numbers here.

---

## 1. The goal: a lifelong personal assistant

Life Graph is not only a multi-tenant backend. For its owner (Raja) it is meant to be a
lifelong assistant (think Jarvis), across:

* **Work and engineering:** the hospital system (HIS), ERP, architecture, DevOps.
* **Study and research:** AI and computer science, paper notes, flashcards.
* **Family and personal life:** home routines, health, promises and commitments, in Tamil,
  Tanglish and English, by voice.
* **Hobbies and growth.**

An agent working here is building a system that learns how he thinks, how he decides and
what he will not trade away. Treat his recorded preferences and decisions as the spec.

---

## 2. One identity

All of it lives in tenant `raja`, around one identity node, with domains as tags and graph
edges (`domain: work_his`, `domain: family`, `domain: study`), never as sub-tenants. A coding
agent on `his` filters to `domain: work_his` yet can still reach his core principles
(`tag: core_principle`, `tag: preference`). See CHARTER invariant 6.

---

## 3. One GPU, two jobs

The machine has one 16 GB GPU. Speech (tamil-ai's conversational model plus speech
recognition) and the coding agents (gpt-oss:20b, OpenCode with a 30B coder) cannot all fit
at once, so the GPU is scheduled, not divided:

* **While he is active** (a chat, Telegram or voice turn in the last half hour, a speech
  model loaded, or the manual switch set to active), the GPU is his. Queued coding work goes
  to a **free** cloud model (OpenRouter `:free`, NVIDIA's free API) or waits.
* **While he is away** (nights, mostly) queued coding work runs locally, as before.
* **Never paid.** When the free models are rate-limited, the task goes back on the queue for
  the GPU.

Implemented by `services/compute_router.py` and the `cloud` driver (`drivers/cloud.py`):
the cloud path drops preferences, procedures and memories from the prompt, refuses any
model that is not free, fails over only to other free models, and earns its own trust
record before anything it writes can auto-merge. The switch and the current routing are at
`GET /api/v1/kernel/drivers/compute` and `PUT /api/v1/kernel/drivers/compute/presence`.

What may leave the machine: **code and coding instructions**, on that path only. Everything
personal stays local (CHARTER invariant 7, which also lists the known exceptions: Telegram
transit and any cloud TTS voice).

---

## 4. The repos around Life Graph

To keep Life Graph from becoming a monolith, the ecosystem is split across repos:

| Repo / service | Role |
| :--- | :--- |
| **life-graph** | The brain: knowledge graph, semantic search, nightly consolidation, capture spine, judgment engine, dev agents, Telegram bot. |
| **life-graph-ui** | The cockpit: dashboard, approval queues, memory timelines, graph view. Local only, never pushed (commercial template). |
| **tamil-ai** | Ears and mouth: real-time Tamil/English voice studio; searches and captures to Life Graph (`surface: voice`). |
| **his**, **apptx-v2** | Engineering domains: the hospital system and the multi-tenant ERP. |
| **per-learn** | Study notes and guides. |

---

## 5. Working with Raja's context

1. **Look before asking.** Search Life Graph (`POST /api/v1/search/`, tenant `raja`, with the
   service API key) before proposing a big change or asking him to re-explain his stack.
2. **Plain code before a model.** If regex, an algorithm or a query can do it, do not spend
   a model call (CHARTER invariant 1).
3. **Record his decisions, not yours.** When *he* makes an architectural or product decision,
   capture it (`POST /api/v1/capture/`, `surface: "agent"`). Agents' own small choices are not
   decisions to record; logging them buries his.
4. **Keep the languages.** The assistant speaks Tamil, Tanglish and English. Never trade away
   Tamil accuracy or the warm tone for a generic reply.
