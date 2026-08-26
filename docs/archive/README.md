# Archive — historical, not authoritative

> **Nothing in this folder describes the current system.** These are records of how Life
> Graph got here, kept because the reasoning is often worth re-reading. They were accurate
> when written and have not been maintained since.
>
> For what exists right now, read [docs/STATE.md](../STATE.md) — it is generated from the
> code. For why the project is built the way it is, read [CHARTER.md](../../CHARTER.md).

## What's in here

### `superpowers/`

Per-feature design documents and implementation plans, dated by the day the work started.
These are **build records**: each one captures the design of a single change and the plan
that delivered it. They were never intended to stay current, and several describe
intermediate states that were later replaced.

Useful when you want to know *why* a particular feature was shaped the way it was, or what
alternatives were rejected at the time. Not useful as a description of present behaviour.

- `specs/` — design documents (the "what and why" for one change)
- `plans/` — implementation plans (the task breakdown that executed it)

### `comms-specs/`

Large specification documents that lived in `.comms/specs/`. That directory was an
accretion — the inter-agent protocol documented in [`.comms/README.md`](../../.comms/README.md)
only ever defined `inbox/`, `outbox/`, `active/`, and `context/`, so `specs/` was never part
of it.

Most of these describe **adjacent or different products** rather than Life Graph itself —
commercial SaaS work, tooling platforms, and revenue planning. They are preserved here
because several run to 100KB+ of genuine design thinking.

A further twelve files from that directory were **byte-identical duplicates** of files
already in `docs/specs/` and `docs/`. Those were deleted rather than archived; the `docs/`
copies are canonical.

### `continued-from-fintech-session.md`

A loose session handoff note from an unrelated piece of work that had been sitting in the
repository root.

## A note on file dates

Filesystem timestamps in this repository are **not** a staleness signal. Everything reads
around 2026-08-20 because that is when the tree was copied onto ext4 during the Linux
migration. Use the dates in filenames and git history instead.
