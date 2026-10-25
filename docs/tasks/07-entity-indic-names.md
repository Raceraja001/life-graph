# 07: Entity keys keep Tamil and Hindi vowel signs

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-opencode`, else `code-fixer-local`; `spec_first=True` (README: How to run) |
| Depends on | none |
| Review | gates. Then a **human** step: re-run the entity backfill on live data (below) |
| Size | ~6 lines in `entities.py`, one new test file |

## Why

`services/entities.py::normalize` builds the key that the entity index (migration 053) stores
every person, place and project under. It strips characters with `[^\w+# ]`, and Python's `\w`
does not include combining marks, so the vowel signs of Tamil and Devanagari are deleted.
Different names collapse into one key, and the stored key is unreadable. Reproduced on 6459f6b:

```
normalize("ராஜா")    -> "ரஜ"
normalize("சென்னை")  -> "சனன"
normalize("राजा")    -> "रज"
```

The owner writes in Tamil as well as English, so names in Tamil are common.

## Instruction

<!-- instruction:start -->
Entities: normalize must keep combining marks so Tamil and Hindi names are not mangled

Do these five steps in order. Each one is required: without the test file (STEP 1) and the Understanding section (STEP 5) the task fails verification, however good the code is.

STEP 1. Create the new file tests/unit/test_entity_names_unicode.py with exactly the text between the ===== lines: nothing added, nothing left out. Do it first, before you read or change anything else.
- With code_edit: ONE call with only path="tests/unit/test_entity_names_unicode.py", old="" and new=<the whole text>. Do not pass start_line or end_line; with them the call fails with "Not a file".
- With OpenCode's tools: use write.
===== tests/unit/test_entity_names_unicode.py =====
import pytest

from life_graph.services.entities import is_entity, normalize

RAJA_TA = "ராஜா"
CHENNAI_TA = "சென்னை"
RAJA_HI = "राजा"
MANGLED_TA = "ரஜ"


@pytest.mark.parametrize(
    ("name", "key"),
    [
        (RAJA_TA, RAJA_TA),
        (CHENNAI_TA, CHENNAI_TA),
        (RAJA_HI, RAJA_HI),
        ("The " + RAJA_TA + " Foundation", RAJA_TA + " foundation"),
        ("O'Brien", "obrien"),
        ("C#", "c#"),
        ("Life-Graph", "life graph"),
        ("Murugan S.", "murugan s"),
    ],
)
def test_indic_names_keep_their_vowel_signs(name, key):
    assert normalize(name) == key
    assert normalize(RAJA_TA) != normalize(MANGLED_TA)
    assert is_entity(normalize(RAJA_TA)) is True


def test_composed_and_decomposed_are_one_key():
    composed = "café"
    decomposed = "café"
    assert normalize(composed) == "café"
    assert normalize(decomposed) == "café"
===== end of tests/unit/test_entity_names_unicode.py =====

STEP 2. Run it: run_tests with paths ["tests/unit/test_entity_names_unicode.py"] (on OpenCode the tool is lg_tests_run_tests). Some cases must fail now, because the source is not changed yet. An ImportError or SyntaxError means STEP 1 was copied wrong: fix the copy, never the cases.

STEP 3. Make the smallest change in life_graph/services/entities.py (normalize) that makes those cases pass. Read the code first.
1. Import unicodedata, and first apply unicodedata.normalize("NFC", ...) to the name, so a composed and a decomposed "café" give one key.
2. Replace the step re.sub(r"[^\w+# ]+", "", key) with a filter that keeps a character when ch.isalnum(), or ch is "+", "#" or " ", or unicodedata.category(ch) starts with "M" (a combining mark: Tamil and Devanagari vowel signs). Everything else is dropped, as before.
Keep the other steps (lower case, separators to spaces, collapse spaces, strip a leading "the ", cut to MAX_KEY) as they are, in the same order. The test file spells the Tamil and Hindi names as \u escapes; that is intended.

STEP 4. Run run_tests with paths ["tests/unit/test_entity_names_unicode.py", "tests/unit/test_entity_names.py"]. If anything fails, fix the SOURCE and run again until all pass. Never edit tests/unit/test_entity_names_unicode.py to make it pass, and never edit any other test file.

STEP 5. Your last message is text, not a tool call. End it with this section, every line filled in, naming every function you added or changed:
## Understanding
Current behaviour: <what normalize did before, in your words>
Change: <what you changed in normalize (and any helper you added), and why>
Risk: <what could break, and which test in tests/unit/test_entity_names_unicode.py or tests/unit/test_entity_names.py shows it does not>

Files you may touch:
- life_graph/services/entities.py (normalize)
- tests/unit/test_entity_names_unicode.py (new; created in STEP 1)

Do NOT:
- change link, known_in_text, memories_for, about or NOT_ENTITIES;
- write a migration or touch the database;
- edit, rename or delete any existing test file;
- add a database, a mock or a new dependency (this is pure logic).

## Spec
**Requirements:**
AC-1: Tamil and Devanagari names keep their vowel signs, and different names stay different — test: tests/unit/test_entity_names_unicode.py::test_indic_names_keep_their_vowel_signs
AC-2: Composed and decomposed forms of a name give one key — test: tests/unit/test_entity_names_unicode.py::test_composed_and_decomposed_are_one_key
AC-3: Existing keys are unchanged — test: tests/unit/test_entity_names.py::test_normalize
**Design:** NFC first, then a character filter that also keeps Unicode category M*, instead of the \w-based regex.
**Tasks:**
1. Create tests/unit/test_entity_names_unicode.py exactly as given, then change normalize as described until it and test_normalize pass (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged. Then do STEP 1.
<!-- instruction:end -->

## Human step after merge

Existing entity rows for Tamil or Hindi names are stored under the old, mangled keys. New
questions will now normalize differently and miss them. After merging, re-run
`scripts/backfill_entities.py` for tenant `raja`. This is a live-data job: the owner or Claude
runs it, never the pipeline. Check the script's options first; it may need its rows cleared
before it rebuilds them. The fresh start on 2026-10-23 cleared the index, so there may be few
such rows.
