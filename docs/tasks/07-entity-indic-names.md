# 07: Entity keys keep Tamil and Hindi vowel signs

| | |
|---|---|
| Theme | C. Memory recall |
| Engine | `code-fixer-local`, `spec_first=True` |
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

Read first:
- life_graph/services/entities.py: normalize and is_entity (lines 91-107).
- tests/unit/test_entity_names.py (must keep passing unchanged).

Change (life_graph/services/entities.py, normalize only):
1. First apply unicodedata.normalize("NFC", ...) to the name, so a composed and a decomposed "café" give one key.
2. Replace the step re.sub(r"[^\w+# ]+", "", key) with a filter that keeps a character when ch.isalnum(), or ch is one of "+", "#", " ", or unicodedata.category(ch) starts with "M" (a combining mark). Everything else is dropped, as before.
Keep the other steps (lower case, separators to spaces, collapse spaces, strip a leading "the ", cut to MAX_KEY) exactly as they are, in the same order.

Cases (copy exactly). normalize(name) ==:
- "ராஜா" -> "ராஜா"
- "சென்னை" -> "சென்னை"
- "राजा" -> "राजा"
- "The ராஜா Foundation" -> "ராஜா foundation"
- "O'Brien" -> "obrien"
- "C#" -> "c#"
- "Life-Graph" -> "life graph"
- "Murugan S." -> "murugan s"
Also:
- normalize("café") == normalize("café") == "café"
- normalize("ராஜா") != normalize("ரஜ")
- is_entity(normalize("ராஜா")) is True

Files you may touch:
- life_graph/services/entities.py (normalize, and the import of unicodedata)
- tests/unit/test_entity_names_unicode.py (new)

Do NOT:
- change link, known_in_text, memories_for, about or NOT_ENTITIES;
- write a migration or touch the database;
- edit tests/unit/test_entity_names.py or any other existing test.

## Spec
**Requirements:**
AC-1: Tamil and Devanagari names keep their vowel signs, and different names stay different — test: tests/unit/test_entity_names_unicode.py::test_indic_names_keep_their_vowel_signs
AC-2: Composed and decomposed forms of a name give one key — test: tests/unit/test_entity_names_unicode.py::test_composed_and_decomposed_are_one_key
AC-3: Existing keys are unchanged — test: tests/unit/test_entity_names.py::test_normalize
**Design:** NFC first, then a character filter that also keeps Unicode category M*, instead of the \w-based regex.
**Tasks:**
1. Change normalize as described and add tests/unit/test_entity_names_unicode.py with the cases above (AC-1, AC-2, AC-3)

Start your reply with the ## Spec section above, copied unchanged, then implement it.
<!-- instruction:end -->

## Human step after merge

Existing entity rows for Tamil or Hindi names are stored under the old, mangled keys. New
questions will now normalize differently and miss them. After merging, re-run
`scripts/backfill_entities.py` for tenant `raja`. This is a live-data job: the owner or Claude
runs it, never the pipeline. Check the script's options first; it may need its rows cleared
before it rebuilds them. The fresh start on 2026-10-23 cleared the index, so there may be few
such rows.
