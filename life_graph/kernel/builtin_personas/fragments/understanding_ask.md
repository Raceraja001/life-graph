---
# What the change_explained check asks of a production-code change
# (services/dev/proof_checks.py); asked up front so it costs no bounce.
# gpt-oss:20b ended its turn on a tool call with no text, so the section
# was missing.
---

Your last message must be text, not a tool call. If you changed anything other than
tests or docs, end your reply with a '## Understanding' section with three lines:
'Current behaviour:' (what the code did before), 'Change:' (what you changed and why)
and 'Risk:' (what could break, and which test shows it does not), naming every function
or class you changed.
