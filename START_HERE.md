# START_HERE.md — moved

This was the onboarding document. It was retired on 2026-08-25 because it had become layered
sediment: an "Era 9" section bolted on top of a "Prior state (as of July 11)" section on top
of a roadmap table that predated both, with Windows-only paths and status claims that no
longer matched the code.

Start here instead, in this order:

1. **[CHARTER.md](CHARTER.md)** — what Life Graph is, the problem it solves, the five design
   invariants, the layer model, non-goals, and the current frontier. Read this first; it is
   the only document that states intent.
2. **[docs/STATE.md](docs/STATE.md)** — what exists right now, generated from the code by
   `scripts/gen_state.py`. Endpoints, tables, events, personas, tools, scheduled jobs,
   configuration, migrations, tests, dashboard routes, and spec status. Never hand-edited,
   so it cannot drift.
3. **[AGENTS.md](AGENTS.md)** — developer preferences, code conventions, the spec-driven
   build loop, the "you want to… look at…" file map, and the `.comms/` inter-agent protocol.
4. **[CLAUDE.md](CLAUDE.md)** — commands for running the stack, tests, and migrations.

Then, as needed: [README.md](README.md) for the public overview,
[docs/QUICKSTART.md](docs/QUICKSTART.md) to get it running,
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for depth,
[docs/specs/](docs/specs/) for per-feature specs (each now carries a status header), and
[docs/archive/](docs/archive/) for historical build records — which are explicitly *not*
authoritative.

The strategy behind the current direction is recorded in
[docs/design/07_strategic_direction_2026-07.md](docs/design/07_strategic_direction_2026-07.md).
Read it before proposing a new direction.
