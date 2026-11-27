"""Does anything in a context snapshot speak to what the question asks? (no model)

The context snapshot (services/memory/snapshot.py) lists the nearest records
for every question, related or not: search always returns its top-k. So
"something was found" says nothing about whether the question can be answered.
This module checks, with words only, whether at least one included record is
about the question's subject. It is deterministic, local and calls no model.

Terms
=====

The question is cut into *terms*: runs of adjacent content words. A run ends
at punctuation and at a word that carries no subject:

* function words (core/evidence.py's stop words and negations);
* :data:`FRAME_WORDS`, words that frame a request rather than name what it is
  about: how it is asked ("tell", "recommend", "missing"), when ("current",
  "recently", "next", "changed"), light verbs ("take", "get"), scope
  ("monthly", "household") and generic slot nouns ("name", "number", "title",
  "score", "date"). A slot noun asks for a value of something; the something
  is the subject. "What is my credit score?" is about credit, and "scored 68%
  on a practice test" is not.

Numbers of fewer than four digits are dropped (amounts break apart at their
separators: "₹1,20,000"); a four-digit year is kept. A word is a run of
letters, marks and digits of any script, so Tamil vowel signs stay in their
word (the same rule as the snapshot's keyword match, D10). The frame list is
English; a Tamil question keeps all its words as content.

Support
=======

An item's words are its own text plus its labels (a memory's tags and fact
type; a decision's domain tags; and :data:`KIND_WORDS`, the words that name the
record's kind: "decision", "commitment", "deadline" for an intention with a
due time, …). Two words match when their stems are equal, or, both being at
least five characters, they share a prefix of all but the last two characters
of the shorter (at least five): "financial" and "finance", "responsible" and
"responsibility", a Tamil case ending. Shorter words must be equal.

A one-word term is supported by an item that has the word. A longer term
needs two of its words in the same item: one generic word is not enough
("credit score" is not supported by a note about a test score, nor by one
about a credit card unless it also says "score"). The question is supported
when any of its terms is supported by any one included item.

A question with no terms at all ("what's up?") is not judged here.

A question that asks what is missing ("What information is missing before you
can recommend …?", :func:`asks_for_gaps`) is never answered by what was found:
no record says what a reliable answer needs. The terms no item supports are
the gaps, and they are reported (:attr:`Sufficiency.missing`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from life_graph.core.evidence import _NEGATIONS, _STOPWORDS

if TYPE_CHECKING:
    from collections.abc import Iterable


def _word_set(*groups: str) -> frozenset[str]:
    return frozenset(w for group in groups for w in group.split())


#: Words that frame a request rather than name its subject (see module docstring).
FRAME_WORDS = _word_set(
    # how it is asked
    "information info missing know known tell remind recommend recommending recommendation"
    " reliably reliable advice advise suggest consider considering need needed whether"
    " because instead why before after until since up down out off much many far ever"
    " already yet again right sure like please",
    # contractions, with the apostrophe gone ("what's" -> "whats")
    "whats whos wheres whens hows thats theres im ive youre youve theyre",
    # when, and change over time
    "current currently now today soon recent recently latest last next coming upcoming"
    " anymore ago active ongoing change changed changes changing happen happened",
    # light verbs
    "get got take took make made go going went give gave put let",
    # generic slot nouns: they ask for a value of the subject
    "name names number title score amount date day days time times year years month"
    " months week weeks status level value type kind list details detail thing things"
    " way ways part",
    # scope
    "household overall total combined personal monthly yearly annual weekly daily each every non",
)
#: Words that carry no subject: function words, negations and frame words.
NON_CONTENT = frozenset(_STOPWORDS) | frozenset(_NEGATIONS) | FRAME_WORDS

#: Words that name a record's kind, added to the item's own words.
KIND_WORDS = {
    "decision": "decision decide choice choose chose",
    "intention": "intention commitment promise reminder task todo plan priority",
}
#: Added to an item that has a due time.
DUE_WORDS = "due deadline"

#: "what is missing", "what information is missing", "what else do you need to know".
_GAPS = re.compile(
    r"\bwhat(?:s|\s+is|\s+are|\s+am\s+i)\s+(?:still\s+)?missing\b"
    r"|\b(?:what|which)\b[^?.!]*?\b(?:is|are)\s+(?:still\s+)?(?:missing|unknown|lacking)\b"
    r"|\bmissing\s+information\b"
    r"|\bwhat\s+else\s+(?:do|would|should)\s+you\s+need\b"
    r"|\bwhat\s+(?:do|would|should)\s+you\s+(?:still\s+)?need\s+to\s+know\b"
    r"|\bwhat\s+(?:dont|do\s+not)\s+you\s+know\b",
    re.IGNORECASE,
)

#: Shortest stem that may match another by prefix.
PREFIX_MIN = 5


def _is_word_char(ch: str) -> bool:
    """A letter, a mark or a digit of any script (Unicode categories L*, M*, N*)."""
    return unicodedata.category(ch)[0] in "LMN"


def _normalise(text_: str) -> str:
    folded = unicodedata.normalize("NFKC", text_ or "").lower()
    return folded.replace("'", "").replace("’", "")


def _tokens(text_: str) -> list[tuple[str, bool]]:
    """(word, breaks_before) in order: True after punctuation (or at the start)."""
    out: list[tuple[str, bool]] = []
    word: list[str] = []
    brk = True
    for ch in _normalise(text_) + " ":
        if _is_word_char(ch):
            word.append(ch)
            continue
        if word:
            out.append(("".join(word), brk))
            word, brk = [], False
        if not ch.isspace():
            brk = True
    return out


def stem(word: str) -> str:
    """A crude English suffix strip ("lives", "living" -> "liv"); other scripts pass."""
    for suffix, floor in (("ing", 6), ("ies", 5), ("ed", 5), ("s", 4)):
        if len(word) >= floor and word.endswith(suffix):
            word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    return word[:-1] if len(word) >= PREFIX_MIN and word.endswith("e") else word


def stems_match(a: str, b: str) -> bool:
    """Equal, or (both at least PREFIX_MIN long) a shared prefix of all but two."""
    if a == b:
        return True
    shorter = min(len(a), len(b))
    if shorter < PREFIX_MIN:
        return False
    common = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        common += 1
    return common >= max(PREFIX_MIN, shorter - 2)


def _is_content(word: str) -> bool:
    if word in NON_CONTENT:
        return False
    if word.isdigit():
        return len(word) == 4
    return len(word) > 1


@dataclass(frozen=True)
class Term:
    """A run of adjacent content words of the question."""

    words: tuple[str, ...]
    stems: tuple[str, ...]

    @property
    def text(self) -> str:
        return " ".join(self.words)

    @property
    def needed(self) -> int:
        """How many of its words one item must have: all of a one-word term, else two."""
        return min(len(self.stems), 2)


def query_terms(query: str) -> tuple[Term, ...]:
    """The question's terms, in order, each once."""
    runs: list[list[str]] = []
    run: list[str] = []
    for word, brk in _tokens(query):
        content = _is_content(word)
        if (brk or not content) and run:
            runs.append(run)
            run = []
        if content:
            run.append(word)
    if run:
        runs.append(run)
    out: list[Term] = []
    for words in runs:
        term = Term(tuple(words), tuple(stem(w) for w in words))
        if term.stems not in [t.stems for t in out]:
            out.append(term)
    return tuple(out)


def support_words(text_: str) -> frozenset[str]:
    """The stems of every word of *text_* (an item's text and labels)."""
    return frozenset(stem(w) for w, _ in _tokens(text_) if len(w) > 1 or w.isdigit())


def covered(term: Term, words: frozenset[str]) -> tuple[bool, ...]:
    """Per word of *term*: does *words* have it?"""
    return tuple(any(stems_match(s, w) for w in words) for s in term.stems)


def asks_for_gaps(query: str) -> bool:
    """Whether *query* asks what is missing or unknown (English forms only)."""
    return bool(_GAPS.search(_normalise(query)))


@dataclass(frozen=True)
class Sufficiency:
    """What the included items say about the question's terms."""

    terms: tuple[Term, ...] = ()
    #: Terms some one item supports.
    supported: tuple[str, ...] = ()
    #: Terms no item supports.
    missing_terms: tuple[str, ...] = ()
    #: (word, term) for each word of a supported longer term that its best item lacks.
    missing_words: tuple[tuple[str, str], ...] = ()
    asks_for_gaps: bool = False

    @property
    def judged(self) -> bool:
        """False when the question has no terms, so nothing was checked."""
        return bool(self.terms)

    @property
    def unsupported(self) -> bool:
        """The question has terms and no item supports any of them."""
        return self.judged and not self.supported

    @property
    def missing(self) -> tuple[str, ...]:
        """The unsupported terms, then the lacking words of supported ones."""
        return self.missing_terms + tuple(w for w, _ in self.missing_words)

    def describe_missing(self) -> str:
        """ "'credit', 'second' (in 'second home loan')": the gaps, for an explanation."""
        parts = [f"'{t}'" for t in self.missing_terms]
        parts += [f"'{w}' (in '{t}')" for w, t in self.missing_words]
        return ", ".join(parts)


def assess(query: str, item_texts: Iterable[str]) -> Sufficiency:
    """Which of *query*'s terms the items (their text and labels) support.

    For each term the best item is the one with the most of its words (the
    first such item in the given order), so the result is deterministic.
    """
    terms = query_terms(query)
    word_sets = [support_words(t) for t in item_texts]
    supported: list[str] = []
    missing_terms: list[str] = []
    missing_words: list[tuple[str, str]] = []
    for term in terms:
        best = max((covered(term, ws) for ws in word_sets), key=sum, default=None)
        if best is None or sum(best) < term.needed:
            missing_terms.append(term.text)
            continue
        supported.append(term.text)
        missing_words += [(w, term.text) for w, ok in zip(term.words, best, strict=True) if not ok]
    return Sufficiency(
        terms=terms,
        supported=tuple(supported),
        missing_terms=tuple(missing_terms),
        missing_words=tuple(missing_words),
        asks_for_gaps=asks_for_gaps(query),
    )


__all__ = [
    "DUE_WORDS",
    "FRAME_WORDS",
    "KIND_WORDS",
    "Sufficiency",
    "Term",
    "asks_for_gaps",
    "assess",
    "covered",
    "query_terms",
    "stem",
    "stems_match",
    "support_words",
]
