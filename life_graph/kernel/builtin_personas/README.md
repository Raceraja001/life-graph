# Built-in personas

One file per built-in persona. `kernel/persona_files.py` loads them into
`kernel/personas.py`'s `_BUILTIN_PERSONAS` when the API starts, and
`seed_builtins` brings every tenant's row in line with the file. To change a
prompt, edit its file and restart the API; no Python change is needed.

## A file

`NN-<name>.md`. The number sets the seeding order and `<name>` must match the
`name` field.

```markdown
---
name: scout
display_name: Knowledge Scout
icon: 🧭
description: Ambiently researches topics useful to the user and surfaces findings.
intent_tags: [research, scout, digest]
temperature: 0.5
# YAML comments are fine; say why a tool is or isn't granted.
allowed_tools:
- web_search
---

You are Scout. You research topics the user cares about ...
```

- **The header** is YAML. Required fields: `name`, `display_name`, `icon`,
  `description`, `intent_tags`, `temperature`, `allowed_tools` (`null` means
  every tool). Optional: `driver`, `task_types`, `verifier_chain`,
  `context_profile`. Any other key fails the load.
- **The body** is the system prompt. Wrap lines however you like: the lines
  of a paragraph are joined with single spaces. A blank line starts a new
  paragraph, which the model sees as one blank line (`\n\n`).
- **`<<name>>`** puts in a shared passage: a file in `fragments/` (its header
  holds comments only) or `agent_task_propose_contract` /
  `command_propose_contract` from `kernel/propose_contract.py`. Leave a space
  before the marker, as between two sentences.

A mistake (an unknown key, a misspelt marker, a name that doesn't match the
file) raises at startup and in `tests/unit/test_persona_files.py`, so it never
seeds a broken persona.

## What stays in code

`RETIRED_PERSONAS` and `HOST_TOOLS` in `personas.py` are policy, not prompt
text: which personas are switched off, and which tools Jarvis must never hold.
`tests/` check Jarvis's `allowed_tools` against `HOST_TOOLS`, so granting one
here fails CI.
