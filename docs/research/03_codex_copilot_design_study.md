# 🔬 Design Study: Codex Desktop App & GitHub Copilot App

## How They're Built — Architecture Deep Dive

---

## 1. OpenAI Codex Desktop App

### Architecture: Three-Tier Decoupled Design

```
┌─────────────────────────────────────────────────────────┐
│                    ELECTRON SHELL                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │              RENDERER PROCESS (UI)                │  │
│  │                                                    │  │
│  │   React + ProseMirror (not Monaco!)               │  │
│  │   ┌──────────┐ ┌────────┐ ┌──────────────────┐   │  │
│  │   │ Sidebar  │ │Composer│ │ Diff/File Viewer │   │  │
│  │   │ Projects │ │ Input  │ │  (visual tree)   │   │  │
│  │   │ Threads  │ │ Panel  │ │                  │   │  │
│  │   └──────────┘ └────────┘ └──────────────────┘   │  │
│  │                                                    │  │
│  │          Centralized IPC Handler Registry          │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│              Bidirectional JSON-RPC (stdio)              │
│                        │                                 │
│  ┌─────────────────────▼─────────────────────────────┐  │
│  │            CODEX APP SERVER (Core Logic)           │  │
│  │                                                    │  │
│  │   Agent Loop · Thread Manager · Tool Executor     │  │
│  │   Context Window · Streaming · Approvals          │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│              LLM APIs + Local Tools + Git                │
│                        │                                 │
│  ┌─────────────────────▼─────────────────────────────┐  │
│  │              SANDBOXED EXECUTION                   │  │
│  │                                                    │  │
│  │   Git Worktrees (per-agent branch isolation)      │  │
│  │   OS-level sandbox (Seatbelt/Landlock)            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | What They Did | Why |
|---|---|---|
| **Shell** | Electron | Cross-platform (macOS, Windows, Linux) with fast iteration |
| **UI Framework** | React | Industry standard, component-based |
| **Editor** | ProseMirror (NOT Monaco) | Schema-based — supports inline tool calls, diffs, diagrams mixed with text. Monaco is code-only. |
| **Communication** | JSON-RPC over stdio | Bidirectional, supports streaming, pauses, structured diffs. REST can't do this well. |
| **IPC** | Centralized handler registry | Maps method names → async handlers. Cleaner than ad-hoc Electron IPC. |
| **Isolation** | Git worktrees | Multiple agents edit same repo on different branches without file collision. |
| **Sandbox** | OS-level (Seatbelt/Landlock) | Kernel-level isolation — agents can't escape to harm the system. |

### UI Components Breakdown

#### Left Sidebar — Navigation
```
┌─────────────────┐
│ 🏠 Home          │
│ ─────────────── │
│ 📁 Projects      │
│   ├─ project-a  │
│   └─ project-b  │
│ ─────────────── │
│ 🧵 Threads       │
│   ├─ Fix auth   │  ← Each thread = independent agent session
│   ├─ Add tests  │
│   └─ Refactor   │
│ ─────────────── │
│ ⚡ Automations   │
│ 🔧 Skills        │
│ ⚙️ Settings      │
└─────────────────┘
```

#### Center — Composer + Agent Activity
```
┌──────────────────────────────────────────┐
│  AGENT ACTIVITY STREAM                   │
│                                          │
│  🤖 Analyzing repository structure...    │
│  📂 Reading src/auth/middleware.ts       │
│  💭 Planning approach...                 │
│  ┌────────────────────────────────────┐  │
│  │ 📋 PLAN                            │  │
│  │ 1. Update JWT validation logic     │  │
│  │ 2. Add refresh token support       │  │
│  │ 3. Write integration tests         │  │
│  │                    [Approve] [Edit] │  │
│  └────────────────────────────────────┘  │
│  🔧 Editing src/auth/middleware.ts       │
│  🔧 Creating src/auth/refresh.ts        │
│  🧪 Running: npm test                   │
│  ✅ All 24 tests passing                 │
│                                          │
├──────────────────────────────────────────┤
│  COMPOSER INPUT                          │
│  ┌────────────────────────────────────┐  │
│  │ Add refresh token support to the  │  │
│  │ auth system with tests...         │  │
│  │                          [Submit] │  │
│  └────────────────────────────────────┘  │
│  📎 Context: 42 files indexed            │
│  🧠 Model: GPT-5.4                      │
└──────────────────────────────────────────┘
```

#### Right Panel — Diff Viewer / File Tree
```
┌──────────────────────────────────────────┐
│  📄 CHANGED FILES (unstaged)             │
│                                          │
│  ├─ 🟡 src/auth/middleware.ts  (+23 -7) │
│  ├─ 🟢 src/auth/refresh.ts    (new)     │
│  ├─ 🟡 src/auth/index.ts      (+3 -1)  │
│  └─ 🟡 tests/auth.test.ts     (+45)    │
│                                          │
│  ─────────────────────────────────────── │
│                                          │
│  DIFF: src/auth/middleware.ts            │
│  ┌────────────────────────────────────┐  │
│  │ - const token = req.headers.auth  │  │
│  │ + const token = extractBearerToken│  │
│  │ +   (req.headers.authorization)   │  │
│  │                                    │  │
│  │ + // Refresh token validation     │  │
│  │ + if (isExpired(decoded)) {       │  │
│  │ +   return handleRefresh(req,res) │  │
│  │ + }                               │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [Accept All]  [Reject]  [Give Feedback] │
└──────────────────────────────────────────┘
```

---

## 2. GitHub Copilot App

### Architecture: Agent-Native Runtime

```
┌──────────────────────────────────────────────────────────┐
│                  COPILOT DESKTOP APP                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │              "MY WORK" DASHBOARD                   │  │
│  │                                                     │  │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────────┐  │  │
│  │  │ Active   │  │ Agent     │  │ Issues / PRs   │  │  │
│  │  │ Sessions │  │ Fleet     │  │ Tracker        │  │  │
│  │  └──────────┘  └───────────┘  └────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │                  CANVASES                           │  │
│  │  Bidirectional interactive surfaces for:           │  │
│  │  • Spec/plan editing (you + agent co-edit)         │  │
│  │  • PR review (inline comments + agent responses)   │  │
│  │  • Terminal (live shared session)                   │  │
│  │  • Browser (agent browses, you watch/steer)        │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │              AGENT RUNTIME                         │  │
│  │  • Isolated Git worktrees per agent                │  │
│  │  • Copilot SDK (6 languages)                       │  │
│  │  • MCP tool integration                            │  │
│  │  • BYOM (Bring Your Own Model)                     │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | What They Did | Why |
|---|---|---|
| **Dashboard** | "My Work" unified view | Single pane for repos, sessions, issues, PRs — reduces context switching |
| **Canvases** | Bidirectional interactive surfaces | Both you AND agent can edit the same plan/PR/terminal in real-time |
| **Plan Mode** | Agent presents plan BEFORE coding | Trust-building — you approve the approach, not just the output |
| **Model Picker** | Visible in UI | Users can switch models (GPT-4o, Claude, Gemini, o3) per task |
| **Agent Merge** | End-to-end PR lifecycle | Agent handles review → fix → test → merge autonomously |
| **Worktrees** | Git worktree per agent | Same as Codex — parallel work without conflicts |
| **Extensibility** | MCP + BYOM | Open tool/model ecosystem, not locked in |

### Unique UI Patterns in Copilot

#### "Canvases" — The Killer Feature
Unlike Codex's chat-style stream, Copilot uses **shared interactive surfaces**:

```
┌─ CANVAS: Implementation Plan ──────────────────┐
│                                                  │
│  ## Auth System Redesign                        │
│                                                  │
│  ### Step 1: Migrate to JWT v3                  │
│  Status: ✅ Complete                             │
│  Agent note: Updated 3 files, all tests pass    │
│                                                  │
│  ### Step 2: Add RBAC middleware      ← 🤖 🧑   │
│  Status: 🔄 In Progress               co-editing│
│  [Your edit]: Use enum for roles, not strings   │
│  [Agent]: Updated. Using RoleEnum now.          │
│                                                  │
│  ### Step 3: Integration tests                  │
│  Status: ⏳ Queued                               │
│                                                  │
└──────────────────────────────────────────────────┘
```

Both you and the agent see and edit the same canvas in real-time.

---

## 3. Side-by-Side Comparison

| Aspect | Codex Desktop | Copilot App |
|---|---|---|
| **Shell** | Electron | Electron |
| **UI Framework** | React + ProseMirror | React (likely) |
| **Layout** | 3-panel (sidebar/activity/diff) | Dashboard + Canvases |
| **Agent I/O** | Chat-style activity stream | Bidirectional Canvases |
| **Plan presentation** | Inline plan block in chat | Dedicated Canvas surface |
| **Diff viewer** | Right panel with file tree | Inline in Canvas or PR view |
| **Multi-agent** | Threads (tabs per agent) | Fleet view (cards per agent) |
| **Isolation** | Git worktrees | Git worktrees |
| **Communication** | JSON-RPC over stdio | SDK-based runtime |
| **Model flexibility** | OpenAI only | BYOM (any model) |
| **Tool system** | Skills + Automations | MCP + Skills panel |
| **Collaboration** | Remote steering (mobile) | Cloud automations |

---

## 4. The Emerging Standard: AG-UI Protocol

Both apps are converging toward this protocol stack:

```
┌─────────────────────────────────────────┐
│           YOUR APP (Frontend)           │
│         React · Electron · Web          │
├─────────────────────────────────────────┤
│     AG-UI Protocol (Agent ↔ User)       │  ← Standardized event stream
│     Events: text, tool_call, state,     │     (HTTP/SSE/WebSocket)
│     diff, approval_request, progress    │
├─────────────────────────────────────────┤
│     A2A Protocol (Agent ↔ Agent)        │  ← Cross-agent communication
├─────────────────────────────────────────┤
│     MCP Protocol (Agent ↔ Tools)        │  ← Standardized tool access
├─────────────────────────────────────────┤
│     LLM APIs (Agent ↔ Model)           │  ← Any provider
└─────────────────────────────────────────┘
```

### AG-UI Event Types We Should Support
| Event | Description |
|---|---|
| `TEXT_STREAM` | Streaming text from agent |
| `TOOL_CALL_START` | Agent is invoking a tool (file edit, git, shell) |
| `TOOL_CALL_RESULT` | Tool execution result |
| `STATE_UPDATE` | Agent state change (thinking → acting → done) |
| `APPROVAL_REQUEST` | Human-in-the-loop gate |
| `DIFF_EMIT` | Code changes to review |
| `PROGRESS` | Task completion percentage |
| `ERROR` | Something went wrong |

---

## 5. Key Design Lessons for Our Build

### ✅ Patterns to Adopt

| Pattern | From | What to do |
|---|---|---|
| **Three-tier decoupled architecture** | Codex | Separate UI ↔ App Server ↔ Agent Runtime. Don't couple them. |
| **JSON-RPC over stdio/WebSocket** | Codex | Bidirectional, streaming-capable protocol between UI and backend. |
| **Git worktrees for isolation** | Both | Each agent task gets its own worktree — no file conflicts. |
| **Plan-before-execute** | Both | Agent presents a plan for approval before writing code. |
| **ProseMirror over Monaco** | Codex | Rich content (diffs, tool calls, diagrams) inline — not just code. |
| **Canvases / shared surfaces** | Copilot | Interactive, co-editable surfaces for plans and reviews. |
| **Agent fleet view** | Copilot | Dashboard showing all active agents as cards with status. |
| **Model picker in UI** | Copilot | Let users choose which model per task. |
| **Centralized IPC registry** | Codex | Clean method→handler mapping instead of spaghetti IPC. |

### ❌ Patterns to Skip (for now)

| Pattern | Why Skip |
|---|---|
| OS-level sandboxing (Seatbelt/Landlock) | Too complex for v1. Docker is sufficient. |
| Mobile remote steering | Nice-to-have, not essential. |
| Computer Use (screen control) | Way too complex. Focus on code first. |
| Multi-surface dispatch (Slack, GitHub, etc.) | Phase 4 territory. |

---

## 6. Proposed Architecture for Our App

Based on studying both apps, here's the architecture I recommend:

```
┌──────────────────────────────────────────────────────────┐
│                   OUR APP (Tauri or Electron)             │
│  ┌────────────────────────────────────────────────────┐  │
│  │          FRONTEND (React + TypeScript)              │  │
│  │                                                     │  │
│  │  ┌──────────┐ ┌──────────────┐ ┌────────────────┐  │  │
│  │  │ Sidebar  │ │ Agent Canvas │ │ Diff Panel     │  │  │
│  │  │ Projects │ │ Activity     │ │ File Changes   │  │  │
│  │  │ Agents   │ │ Plan Mode   │ │ Code Review    │  │  │
│  │  │ History  │ │ Composer     │ │ Accept/Reject  │  │  │
│  │  └──────────┘ └──────────────┘ └────────────────┘  │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │ WebSocket / AG-UI events       │
│  ┌───────────────────────▼────────────────────────────┐  │
│  │          BACKEND (FastAPI / Python)                 │  │
│  │                                                     │  │
│  │  Task Queue · Agent Orchestrator · Model Router    │  │
│  │  Session Manager · Git Manager · WebSocket Hub     │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │                                │
│  ┌───────────────────────▼────────────────────────────┐  │
│  │          AGENT RUNTIME (CrewAI / Python)            │  │
│  │                                                     │  │
│  │  Architect · Developer · QA · DevOps Agents        │  │
│  │  Tool Registry (MCP) · Eval Loops                  │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │                                │
│  ┌───────────────────────▼────────────────────────────┐  │
│  │          SANDBOX (Docker + Git Worktrees)           │  │
│  └───────────────────────┬────────────────────────────┘  │
│                          │                                │
│          Claude · Gemini · GPT · Local LLMs              │
└──────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> ### Key Architectural Choice: Web-first or Desktop-first?
> 
> **Option A: Web app (Next.js)** — Simpler to build, works everywhere, no Electron/Tauri overhead. Backend runs locally or on a server.
> 
> **Option B: Desktop app (Tauri)** — Native feel, better fs/git access, lighter than Electron. But more complex to build.
> 
> **Option C: Desktop app (Electron)** — What Codex and Copilot use. Heavier but proven, massive ecosystem.
> 
> **My recommendation: Start with Web (Option A)**, then wrap in Tauri for desktop later. The backend (Python/FastAPI) stays the same either way.

---

## 7. What We Should Build (Informed by This Study)

### MVP Feature Map (Inspired by both apps)

| Feature | Codex Inspiration | Copilot Inspiration | Our Implementation |
|---|---|---|---|
| Task submission | Composer input | Issue assignment | Rich text input with repo/branch picker |
| Agent activity | Chat-style stream | Canvas updates | Real-time streaming activity panel |
| Plan mode | Inline plan blocks | Plan Canvas | Agent presents plan → user approves |
| Diff viewer | Right panel file tree | PR-style inline | Side-by-side diff with accept/reject |
| Multi-agent view | Threads (tabs) | Fleet cards | Agent cards with status + expand to detail |
| Model selection | Hidden (GPT only) | Visible picker | Prominent model picker per task |
| Git isolation | Worktrees | Worktrees | Git worktrees per task |
| Tool transparency | Tool call logs | Action stream | Collapsible tool call timeline |
