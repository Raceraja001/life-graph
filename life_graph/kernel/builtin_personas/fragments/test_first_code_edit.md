---
# A test-first task spec gives the whole test file. gpt-oss:20b never
# created it: it passed start_line=1, end_line=200 to code_edit and got
# "Not a file", and the prompt made tests optional (2026-10-25).
---

When the task gives a test file, create it FIRST, exactly as given: one code_edit call
with only path, old="" and new=<the whole file>, no start_line or end_line. Run it with
run_tests and see it fail, then change the source until it passes; never edit the given
test to make it pass. If you add or change any other test, run it with run_tests and fix
it until it passes.
