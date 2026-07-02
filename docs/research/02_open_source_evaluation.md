# 🔍 Open Source Projects We Can Fork

## The Landscape — 7 Projects Worth Evaluating

There are several mature, open-source projects that already do much of what we want. Here's the honest assessment of each.

---

## 🥇 Tier 1: Fork-Worthy (closest to what we want)

### 1. OpenHands (formerly OpenDevin)
**GitHub:** `All-Hands-AI/OpenHands` | **License:** MIT | **Stars:** 50k+

> [!TIP]
> **This is the #1 candidate to fork.** It's the closest thing to what we want to build.

**What it already has:**
- ✅ Full web UI (Remix/React + TypeScript + Tailwind)
- ✅ Multi-agent support (planner-worker pattern)
- ✅ Docker-based sandboxed execution
- ✅ Model-agnostic via LiteLLM (Claude, GPT, Gemini, local)
- ✅ Built-in VS Code integration
- ✅ Git integration (clone, branch, commit)
- ✅ Custom tools (Action/Observation/Executor pattern)
- ✅ GitHub, GitLab, Slack, Linear integrations
- ✅ RBAC and audit trails
- ✅ Customizable per-repo via `.openhands/` config

**What it's missing (what we'd add):**
- ❌ Multi-agent *team* with distinct roles (Architect/Dev/QA)
- ❌ Model routing (cheap vs expensive per task)
- ❌ Custom eval loops (your test suites as quality gates)
- ❌ Codex-style parallel task dashboard
- ❌ Plan-before-execute approval flow

**Tech Stack:**
| Layer | Technology |
|---|---|
| Frontend | Remix SPA (React + Vite + React Router) |
| Styling | Tailwind CSS |
| State | Redux + TanStack Query |
| Backend | Python (openhands.agent_server) |
| LLM | LiteLLM (any provider) |
| Sandbox | Docker containers |
| Validation | Pydantic |

**Effort to customize:** 🟢 **2-4 weeks** to add our multi-agent pipeline + model router + eval loops on top

**Architecture:**
```
┌─────────────────────────────────────────────┐
│     Agent Canvas (Frontend - Remix/React)   │
│     ┌───────────┐ ┌──────────┐ ┌────────┐  │
│     │ Dashboard │ │ Agent    │ │ Code   │  │
│     │ Tasks     │ │ Activity │ │ Viewer │  │
│     └───────────┘ └──────────┘ └────────┘  │
├─────────────────────────────────────────────┤
│     Agent Server (Python Backend)           │
├─────────────────────────────────────────────┤
│     Software Agent SDK (Core Engine)        │
│     Agent Loop · Tools · Executor           │
├─────────────────────────────────────────────┤
│     Docker Runtime (Sandboxed)              │
└─────────────────────────────────────────────┘
```

---

### 2. MetaGPT
**GitHub:** `geekan/MetaGPT` | **License:** MIT | **Stars:** 45k+

> [!NOTE]
> **Best multi-agent team simulation** — it already models a software company with roles.

**What it already has:**
- ✅ Multi-agent with real roles (PM, Architect, Engineer, QA)
- ✅ SOP-driven workflows (Requirements → Design → Code → Test)
- ✅ Structured outputs (PRDs, system designs, code)
- ✅ Highly modular — custom agents & roles easy to define
- ✅ Per-role LLM configuration

**What it's missing:**
- ❌ No web UI (CLI-only, community forks have basic UIs)
- ❌ No sandboxed execution (runs on host)
- ❌ No real-time streaming dashboard
- ❌ No built-in Git worktree isolation
- ❌ No model routing

**Tech Stack:**
| Layer | Technology |
|---|---|
| Core | Python |
| Config | YAML (`config2.yaml`) |
| Frontend | ❌ None (CLI) — community forks exist |
| LLM | OpenAI, Anthropic, local (via config) |

**Effort to customize:** 🟡 **4-6 weeks** — great agent system but need to build entire UI + sandbox layer

---

### 3. Omnigent (Meta-Harness)
**GitHub:** `omnigent-ai/omnigent` | **License:** Apache 2.0 | **New (June 2026)**

> [!NOTE]
> **Not a coding agent itself** — it's an orchestration layer that wraps other agents.

**What it already has:**
- ✅ Wraps ANY agent (Claude Code, Codex, custom) under one API
- ✅ Centralized governance (budgets, tool restrictions, approvals)
- ✅ Real-time session sharing & collaboration
- ✅ MLflow tracing built-in
- ✅ YAML-based agent definitions (swap harnesses easily)
- ✅ Sandboxed execution (Omnibox)
- ✅ Terminal, web, and mobile APIs

**What it's missing:**
- ❌ Not a coding agent — it orchestrates OTHER agents
- ❌ No built-in multi-agent team (Architect/Dev/QA)
- ❌ No task dashboard UI (provides APIs, not a full app)
- ❌ No custom eval loops
- ❌ Limited Windows support (Linux/WSL2 needed)

**Effort to customize:** 🟡 **3-5 weeks** — great orchestration but need agents + UI on top

---

## 🥈 Tier 2: Useful Components (not full solutions, but great building blocks)

### 4. Aider
**GitHub:** `Aider-AI/aider` | **License:** Apache 2.0 | **Stars:** 25k+

- ✅ Best-in-class Git-native CLI coding agent
- ✅ Multi-file editing with automatic commits
- ❌ CLI only — no web UI, no multi-agent
- **Use case for us:** Could be wrapped as one of our "worker agents" inside the platform

### 5. Cline
**GitHub:** `cline/cline` | **License:** Apache 2.0

- ✅ Popular VS Code extension for autonomous coding
- ✅ File editing + terminal execution in editor
- ❌ VS Code locked — not a standalone platform
- **Use case for us:** Study its tool implementations (file edit, terminal exec)

### 6. SWE-Agent (Princeton)
**GitHub:** `princeton-nlp/swe-agent` | **License:** MIT

- ✅ Agent-Computer Interface (ACI) — excellent tool design
- ✅ Top performer on SWE-bench
- ❌ Research-focused, CLI-only, no UI
- **Use case for us:** Borrow its tool design patterns for our agent SDK

### 7. Devika
**GitHub:** `stitionai/devika` | **License:** MIT

- ✅ Has a web UI with chat + agent state visualization
- ✅ Supports local models via Ollama
- ❌ Development has slowed — community focus shifted to OpenHands
- ❌ Single agent only
- **Use case for us:** Reference for basic web UI patterns (but OpenHands is better)

---

## 📊 Comparison Matrix

| Feature | OpenHands | MetaGPT | Omnigent | Aider | Our Goal |
|---|---|---|---|---|---|
| Web UI dashboard | ✅ Rich | ❌ CLI | ❌ API only | ❌ CLI | ✅ Need |
| Multi-agent team roles | ⚠️ Basic | ✅ Full team | ❌ Wraps agents | ❌ Single | ✅ Need |
| Sandboxed execution | ✅ Docker | ❌ Host | ✅ Omnibox | ❌ Host | ✅ Need |
| Model flexibility | ✅ LiteLLM | ⚠️ Config | ✅ Any harness | ✅ LiteLLM | ✅ Need |
| Model routing (cost) | ❌ | ❌ | ❌ | ❌ | ✅ Need |
| Custom eval loops | ❌ | ❌ | ❌ | ❌ | ✅ Need |
| Git worktree isolation | ❌ Docker | ❌ | ❌ | ✅ Git-native | ✅ Need |
| Plan-before-execute | ❌ | ✅ SOP | ❌ | ❌ | ✅ Need |
| Real-time streaming | ✅ | ❌ | ✅ | ❌ | ✅ Need |
| GitHub integration | ✅ | ❌ | ✅ | ✅ | ✅ Need |
| Self-hosted | ✅ | ✅ | ✅ | ✅ | ✅ Need |
| License | MIT | MIT | Apache 2.0 | Apache 2.0 | — |

---

## 🎯 Three Concrete Strategies

### Strategy A: Fork OpenHands (🏆 Recommended)
**"Take the best platform, add our multi-agent brain"**

```
OpenHands (fork)
├── Keep: Web UI, sandbox, Git, LiteLLM, integrations
├── Replace: Single-agent loop → CrewAI multi-agent team
├── Add: Model router, eval loops, plan-approve flow
└── Add: Codex-style parallel task cards in dashboard
```

| What | Effort |
|---|---|
| Fork & set up locally | 2-3 days |
| Replace agent core with CrewAI multi-agent | 1-2 weeks |
| Add model router (LiteLLM already there) | 3-4 days |
| Add eval loop (test suite integration) | 1 week |
| Modify UI for task cards + plan approval | 1-2 weeks |
| **Total** | **~4-5 weeks** |

**Pros:** Fastest path. 70% of the platform already built. MIT license.
**Cons:** Must learn OpenHands codebase (Remix + Python). Maintenance burden of staying in sync with upstream.

---

### Strategy B: Fork MetaGPT + Build UI
**"Take the best multi-agent system, build a Codex-like UI around it"**

```
Custom Platform
├── Backend: MetaGPT (fork) for multi-agent orchestration
├── Add: FastAPI wrapper for MetaGPT
├── Add: Docker sandbox layer
├── Frontend: Build from scratch (Next.js)
└── Add: Model router, streaming, eval loops
```

| What | Effort |
|---|---|
| Fork MetaGPT & customize roles | 1 week |
| Build FastAPI backend wrapper | 1-2 weeks |
| Add Docker sandbox layer | 1-2 weeks |
| Build web UI from scratch | 3-4 weeks |
| Add model router + eval loops | 1-2 weeks |
| **Total** | **~8-10 weeks** |

**Pros:** Best multi-agent architecture out of the box. Full control over UI.
**Cons:** Much more work. Building UI from scratch. MetaGPT has no sandbox.

---

### Strategy C: Omnigent + OpenHands Hybrid
**"Use Omnigent to orchestrate, OpenHands as one execution engine"**

```
Omnigent (meta-harness)
├── Agent 1: OpenHands instance (coding)
├── Agent 2: Custom CrewAI agent (architecture)  
├── Agent 3: Custom QA agent (testing)
├── Governance: Budget, approvals, audit
└── Frontend: Custom dashboard consuming Omnigent APIs
```

| What | Effort |
|---|---|
| Set up Omnigent | 2-3 days |
| Set up OpenHands as a runner | 2-3 days |
| Build custom CrewAI agents | 1-2 weeks |
| Build web dashboard | 3-4 weeks |
| Wire up governance & model routing | 1-2 weeks |
| **Total** | **~7-8 weeks** |

**Pros:** Most architecturally elegant. Clean separation. Built-in governance.
**Cons:** Newest project (June 2026) — less battle-tested. Limited Windows support. Need custom UI.

---

## 💡 My Final Recommendation

> [!IMPORTANT]
> ### Fork OpenHands (Strategy A)
> 
> It gives us **70% of the platform for free** — the hardest parts (web UI, sandbox, Git, LLM integration, streaming) are already done and battle-tested.
> 
> We focus our energy on the **30% that makes it uniquely ours:**
> 1. Multi-agent team (Architect → Developer → QA pipeline)
> 2. Model router (cost optimization)
> 3. Custom eval loops (your quality standards)
> 4. Codex-style task dashboard

### Why OpenHands wins:
| Criteria | OpenHands | MetaGPT | Omnigent |
|---|---|---|---|
| **Time to working product** | 🟢 ~4-5 weeks | 🔴 ~8-10 weeks | 🟡 ~7-8 weeks |
| **UI ready out of box** | ✅ Yes | ❌ No | ❌ No |
| **Sandbox ready** | ✅ Docker | ❌ Must build | ✅ Omnibox |
| **Customizability** | 🟢 High (MIT) | 🟢 High (MIT) | 🟡 Medium |
| **Community & maintenance** | 🟢 Very active | 🟡 Active | 🔴 Brand new |
| **Windows support** | 🟢 Docker | 🟢 Python | 🔴 Linux/WSL |

---

## Next Steps — What do you want to do?

1. **Go with Strategy A (OpenHands fork)?** → I'll create a detailed implementation plan with exact files to modify
2. **Go with Strategy B (MetaGPT + custom UI)?** → More work but more control
3. **Go with Strategy C (Omnigent hybrid)?** → Most elegant but newest/riskiest
4. **Explore any specific project deeper?** → I can clone and analyze the codebase
5. **Something else entirely?** → Tell me what you're thinking
