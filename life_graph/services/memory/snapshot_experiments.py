"""Eval-only precision experiments for the context snapshot (M8). All off by default.

The context snapshot (services/memory/snapshot.py) holds every candidate the
reads found: search hits, linked memories, matching and standing decisions and
intentions. On the M8 eval (scripts/eval_context_quality.py, bge-m3 arm)
recall is 0.88-1.0 but precision only 0.16-0.41: most items are noise. These
options try ways to cut that noise. They exist to be measured, not shipped.

How they are switched on
========================

For the eval, through ``assemble_context(..., experiments=frozenset({...}),
tunables=...)``: the eval passes them from ``--experiments A,B,...`` and
``--xp-set`` and records them in its report. Nothing else passes
``experiments``. Production code can reach only the fixed sets of
:data:`MODES`, through ``assemble_context(..., mode=...)`` and the default-off
``context_precision_mode`` / ``context_precision_shadow`` settings. With no
experiment and no mode the snapshot is byte-identical to before
(tests/unit/test_context_snapshot_default_identity.py).

What never changes, whatever is on
==================================

The options only reorder or leave out candidates that the normal reads already
passed, except ``links`` (C), which can add a typed-link neighbour after the
same safety checks (tenant, active, not hostile, valid now, not replaced).
Tenant scoping, the hostile and pending exclusions, retrieve's abstention,
conflicts, timings, labels (origin, confirmed, evidence) and the hard budget
stay as they are. Every left-out item is counted in ``exclusions`` as
``experiment_<option>``. Conflicts are read over all candidates, not only
the ones kept, so leaving an item out never hides a disagreement.

The options
===========

* **A** ``rank`` -- order by relevance first. Items whose scores are within
  :data:`TIE_TOLERANCE` of each other are a tie; a tie is broken by current
  before historical, then confirmed, then confidence, then evidence kind,
  then freshness. Freshness never overrides relevance. On its own it only
  changes the order (and what a tight budget keeps).
* **B** ``query_type`` -- classify the question (:func:`classify`: fact,
  decision, goal, commitment, relationship, history, change; English, Tamil
  and Tanglish words, Tamil-safe tokens as in D10). A decision or intention,
  question-independent (``due_intention``, ``current_decision``) or keyword
  matched, stays only when the question asks for its kind or its own words
  support one of the question's terms (services/memory/sufficiency.py). A
  standing item the question asks for counts as answering in the
  sufficiency check. When the question is only about a kind
  ("what did I decide recently?", "which commitments are not done?"), a
  memory stays only when its words support the question or name that kind.
* **C** ``links`` -- typed links (#419, services/memory/links.py) from the top
  hits pull their connected memories in (``linked_evidence``), and a learned
  neighbour (``neighbour``) that no typed link joins to a top hit, below
  :data:`LINK_FLOOR`, is left out.
* **D** ``dedupe`` -- collapse near-duplicates: same kind, slot (dimension),
  origin and evidence, the same numbers and negations, and word overlap of at
  least :data:`DUPLICATE_SIMILARITY`. Records from different sources are
  independent evidence and are never collapsed; stored memories are not
  touched.
* **E** ``evidence`` -- among ties, confirmed and the owner's own words
  first, inferred last. Labels are never changed, so an inferred item is never
  shown as confirmed. Both sides of a conflict among the candidates are
  protected: no other option leaves them out.
* **F** ``budget`` -- an adaptive cut of the memory hits on their cosine
  similarity to the question (read once for the candidates, eval-only; the
  search's fused score is rank-based and has no floor): keep at least
  :data:`MIN_KEEP`; stop at the first hit below :data:`COSINE_FLOOR` of the
  top similarity, or more than :data:`COSINE_GAP` of it below the hit
  before. With no cosine (no stored vectors) the fused score is used with
  :data:`RELATIVE_FLOOR` / :data:`ELBOW_GAP`. Only search hits and learned
  neighbours are cut; decisions, intentions and entity links carry fixed
  priors, not relevance (snapshot.REASON_SCORE), so F leaves them to B and
  C. The hard budget is still the maximum.
* **G** ``hub`` -- a hub penalty for F: a record close to almost any
  first-person question (``p_constraint_travel`` is noise in 21 of 45) has
  its similarity lowered by :data:`HUB_WEIGHT` x its mean similarity to
  :data:`HUB_PROBES`. A penalty, not a drop: alone it changes nothing; with
  F it moves the cut.

Structural recall options (the misses B + C + F leave,
docs/audits/2026-11-28-m8-context-precision-evaluation.md §5):

* **H** ``undated`` -- open intentions with no due time at all (no trigger
  time, no promise ``due_by``, no expiry: ``i_aws_book``, O3) are never "due"
  and so reach a snapshot only by sharing a word with the question. H reads
  them (this tenant's, open, not expired, at most :data:`SIDE_PULL`) and
  adds one (reason ``undated_intention``) when the question asks for
  commitments as a whole (:func:`asks_for`; not when it asks about due
  times, :func:`asks_for_due`), when its words support the
  question, or when its meaning does: the cosine of its text's local
  embedding to the question's is at least :data:`INTENTION_FLOOR`. Not for
  an ``as_of`` question.
* **I** ``goals`` -- goals are stored as ordinary memories (a ``goal`` tag,
  or the extractor's ``intention`` fact type with goal words: "wants to",
  "plans to"), which search does not know as a kind, so "what are my active
  goals?" missed ``l_aws_goal`` (O1, O2). I reads this tenant's active goal
  records (:func:`is_goal_memory`, at most :data:`GOAL_PULL`, the same
  checks as C's pulls) and adds one (reason ``goal_record``) when the
  question asks for goals as a whole, or when its words support the
  question. They are the "goal kind" B's gate reads (KIND_TAG_WORDS).
* **J** ``overview`` -- an overview or aggregate question ("my finances",
  "what should you consider before ...", "what is missing before ...",
  :func:`is_overview`) needs many records, and F's cut took the tail (O9
  ``f_emi``, O10). For such a question F keeps at least
  :data:`OVERVIEW_MIN_KEEP` hits and cuts below :data:`OVERVIEW_FLOOR` of the
  top similarity instead (whichever is looser). Alone it changes nothing.
* **K** ``domain`` -- for an overview question that names a life domain
  (finance, health, work, family, learning: :data:`DOMAINS`), F never cuts a
  memory tagged with that domain (O9's ``f_emi``, ``f_husband_income_new``).
  A hold, not a pull: only candidates the reads already found. Alone it
  changes nothing.
* **L** ``blockers`` -- "what are my current priorities?" missed the record
  that says the Billing migration is blocked (O1 ``w_blocker``): a blocker
  shares no word with a priorities question. On a priorities, work-overview
  or "what is stopping me" question (:func:`asks_for_blockers`), L reads this
  tenant's blocker and dependency records (:func:`is_blocker_text`: "blocked",
  "waiting on", "depends on", "stuck", a ``blocker``/``dependency`` tag; English,
  Tanglish, Tamil) and adds the current, unresolved ones (reason
  ``blocker_record``, at most :data:`BLOCKER_PULL`, the same checks as C's
  pulls). A record is resolved when its own words say so ("shipped",
  "unblocked", "no longer"), or when a newer record that says so is joined
  to it by a typed link, or shares its blocker/dependency tag and at least
  :data:`RESOLVE_OVERLAP` of its subject words (``w_dep``, resolved by
  ``w_dep_done``): a resolved dependency shown as current would be wrong.
  When the question names a subject of its own, only the blockers whose
  words support it are added.

H, I and the hold of K never bypass a safety check, and B keeps what H and
I added (they passed their own gate).

The constants are first guesses, not tuned values; the eval can set them
for a run (:data:`TUNABLE`) and should tune on its ``--split tune`` half.

Tunables are values, not globals
================================

The module constants are only the defaults of :class:`Tunables`. A run's
values travel with the call (``assemble_context(..., tunables=...)``); nothing
writes the module's globals at run time, so two snapshots built at once
with different values never see each other's.

Precision modes
===============

:data:`MODES` names two fixed configurations, each a frozen experiment set
and its tunables, measured on the 45-question M8 set (bge-m3, 2026-11-28,
docs/audits/2026-11-28-m8-context-precision-evaluation.md). They are the
only way production code reaches these options: the
``context_precision_mode`` setting (config/memory.py, default "", off) picks
one for ``GET /api/v1/context/snapshot``, and ``context_precision_shadow``
compares one with the default snapshot in the turn trace. "" is today's
snapshot exactly.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from life_graph.core import evidence as ev
from life_graph.services.memory import sufficiency

if TYPE_CHECKING:
    from collections.abc import Iterable

RANK = "rank"
QUERY_TYPE = "query_type"
LINKS = "links"
DEDUPE = "dedupe"
EVIDENCE = "evidence"
BUDGET = "budget"
HUB = "hub"
UNDATED = "undated"
GOALS = "goals"
OVERVIEW = "overview"
DOMAIN = "domain"
BLOCKERS = "blockers"

#: Option letter -> name, as the eval's ``--experiments`` takes them.
OPTIONS = {
    "A": RANK,
    "B": QUERY_TYPE,
    "C": LINKS,
    "D": DEDUPE,
    "E": EVIDENCE,
    "F": BUDGET,
    "G": HUB,
    "H": UNDATED,
    "I": GOALS,
    "J": OVERVIEW,
    "K": DOMAIN,
    "L": BLOCKERS,
}
LETTERS = {name: letter for letter, name in OPTIONS.items()}
NAMES = frozenset(OPTIONS.values())

#: The reason a typed-link neighbour pulled in by C carries.
LINKED_EVIDENCE = "linked_evidence"
#: Reasons that do not depend on the question (snapshot.STANDING_REASONS).
DUE_INTENTION = "due_intention"
CURRENT_DECISION = "current_decision"
SEARCH_HIT = "search_hit"
NEIGHBOUR = "neighbour"
#: The reasons H and I give what they add.
UNDATED_INTENTION = "undated_intention"
GOAL_RECORD = "goal_record"
BLOCKER_RECORD = "blocker_record"
#: Added by an option's own gate: B does not judge them again.
PULLED_REASONS = frozenset({UNDATED_INTENTION, GOAL_RECORD, BLOCKER_RECORD})

#: A: scores this close (relative to the higher one) are a tie.
TIE_TOLERANCE = 0.02
#: C: top memory items whose typed links are followed.
LINK_SEEDS = 5
#: C: most typed-link neighbours pulled in.
LINK_PULL = 6
#: C: a learned neighbour scoring below this, with no typed link to a top hit, is left out.
LINK_FLOOR = 0.25
#: D: least word overlap (Jaccard) for two items to be near-duplicates.
DUPLICATE_SIMILARITY = 0.85
#: F: memory hits always kept.
MIN_KEEP = 3
#: F on the fused rank score (no cosine known): a hit below this share of the
#: top score ends the list ...
RELATIVE_FLOOR = 0.6
#: ... and so does a drop of this share of the top score from the hit before.
ELBOW_GAP = 0.2
#: F on cosine similarity (the normal case): the same two rules.
COSINE_FLOOR = 0.8
COSINE_GAP = 0.08
#: G: how much of a memory's mean similarity to the generic probes is taken
#: off its similarity to the question (CSLS-style hub penalty).
HUB_WEIGHT = 0.5
#: G: generic first-person questions. A record close to all of them is a hub
#: (close to almost any question), not an answer to this one.
HUB_PROBES = (
    "What should I know about me?",
    "Tell me about my life.",
    "What is going on with me right now?",
    "What do I usually do?",
    "What is my situation?",
    "What did I say about myself?",
)
#: H: most open intentions with no due time read.
SIDE_PULL = 10
#: H: least cosine (question vs the intention's text) for a match by meaning.
INTENTION_FLOOR = 0.6
#: I: most goal records added.
GOAL_PULL = 8
#: J: for an overview question F keeps at least this many hits ...
OVERVIEW_MIN_KEEP = 8
#: ... and cuts only below this share of the top similarity (fused: RELATIVE_FLOOR's role).
OVERVIEW_FLOOR = 0.6
#: L: most blocker records added.
BLOCKER_PULL = 4
#: Constants the eval may set for a run (``--xp-set NAME=VALUE``), recorded in its report.
TUNABLE = (
    "TIE_TOLERANCE",
    "LINK_SEEDS",
    "LINK_PULL",
    "LINK_FLOOR",
    "DUPLICATE_SIMILARITY",
    "MIN_KEEP",
    "RELATIVE_FLOOR",
    "ELBOW_GAP",
    "COSINE_FLOOR",
    "COSINE_GAP",
    "HUB_WEIGHT",
    "SIDE_PULL",
    "INTENTION_FLOOR",
    "GOAL_PULL",
    "OVERVIEW_MIN_KEEP",
    "OVERVIEW_FLOOR",
    "BLOCKER_PULL",
)


@dataclass(frozen=True)
class Tunables:
    """One run's values of the :data:`TUNABLE` constants; the defaults are the constants."""

    tie_tolerance: float = TIE_TOLERANCE
    link_seeds: int = LINK_SEEDS
    link_pull: int = LINK_PULL
    link_floor: float = LINK_FLOOR
    duplicate_similarity: float = DUPLICATE_SIMILARITY
    min_keep: int = MIN_KEEP
    relative_floor: float = RELATIVE_FLOOR
    elbow_gap: float = ELBOW_GAP
    cosine_floor: float = COSINE_FLOOR
    cosine_gap: float = COSINE_GAP
    hub_weight: float = HUB_WEIGHT
    side_pull: int = SIDE_PULL
    intention_floor: float = INTENTION_FLOOR
    goal_pull: int = GOAL_PULL
    overview_min_keep: int = OVERVIEW_MIN_KEEP
    overview_floor: float = OVERVIEW_FLOOR
    blocker_pull: int = BLOCKER_PULL

    def named(self) -> dict[str, float]:
        """NAME -> value, in :data:`TUNABLE` order (what the eval's report records)."""
        return {name: getattr(self, name.lower()) for name in TUNABLE}

    def with_values(self, values: dict[str, Any]) -> Tunables:
        """A copy with *values* (NAME -> value, any case) set, cast to each field's type.

        An int field takes "4" or "4.0"; an unknown name is a ValueError.
        """
        changes: dict[str, Any] = {}
        for raw, value in values.items():
            name = str(raw).strip().upper()
            if name not in TUNABLE:
                raise ValueError(f"unknown tunable {raw!r} (known: {', '.join(TUNABLE)})")
            field_ = name.lower()
            cast = type(getattr(self, field_))
            changes[field_] = cast(float(value)) if cast is int else cast(value)
        return dataclasses.replace(self, **changes)


DEFAULT_TUNABLES = Tunables()


@dataclass(frozen=True)
class Mode:
    """A named, frozen experiment set and its tunables (a precision mode)."""

    name: str
    experiments: frozenset[str]
    tunables: Tunables
    #: What the M8 eval measured for it (bge-m3, all 45 questions / held-out test split).
    measured: str


#: The precision modes (config/memory.py ``context_precision_mode``). Frozen:
#: changing one is a change of production behaviour and needs a new eval run.
#: Numbers: the M8 eval, bge-m3, 2026-11-28, tune / test split (P / R).
#: Without H-K (docs/audits/2026-11-28-m8-context-precision-evaluation.md):
#: recall B+C+F 0.401/0.978 tune, 0.539/0.882 test. With H-K (below) recall
#: on the held-out split rises 0.882 -> 0.961. Caveat: H-K's keyword lists
#: (overview, domains, due-time words) were written with sight of all 45
#: questions, so the test split is not fully blind for them.
_STRUCTURAL = frozenset({UNDATED, GOALS, OVERVIEW, DOMAIN})
MODES: MappingProxyType[str, Mode] = MappingProxyType(
    {
        "recall": Mode(
            name="recall",
            experiments=frozenset({QUERY_TYPE, LINKS, BUDGET}) | _STRUCTURAL,
            tunables=Tunables(cosine_floor=0.70),
            measured="B+C+F+H+I+J+K, COSINE_FLOOR 0.70: tune P 0.400 R 1.000, "
            "test P 0.547 R 0.961 (owner's ten R 1.00 / 0.94)",
        ),
        "precision": Mode(
            name="precision",
            experiments=frozenset({QUERY_TYPE, LINKS, BUDGET, HUB}) | _STRUCTURAL,
            tunables=Tunables(cosine_floor=0.75),
            measured="B+C+F+G+H+I+J+K, COSINE_FLOOR 0.75: tune P 0.490 R 0.957, "
            "test P 0.605 R 0.961",
        ),
    }
)
#: The values ``context_precision_mode`` takes: "" (off, today's snapshot) or a mode.
MODE_NAMES = ("", *MODES)


def mode(name: str) -> Mode | None:
    """The mode called *name*; None for "" (off); ValueError for an unknown one."""
    key = (name or "").strip().lower()
    if not key:
        return None
    if key not in MODES:
        raise ValueError(f"unknown precision mode {name!r} (known: {', '.join(MODES)})")
    return MODES[key]


def parse(spec: str | Iterable[str] | None) -> frozenset[str]:
    """Option names from letters or names ("A,F", "rank,budget"); ValueError if unknown."""
    if not spec:
        return frozenset()
    tokens = spec.split(",") if isinstance(spec, str) else list(spec)
    out: set[str] = set()
    for raw in tokens:
        token = str(raw).strip()
        if not token:
            continue
        name = OPTIONS.get(token.upper(), token.lower())
        if name not in NAMES:
            known = ", ".join(f"{k}={v}" for k, v in OPTIONS.items())
            raise ValueError(f"unknown snapshot experiment {token!r} (known: {known})")
        out.add(name)
    return frozenset(out)


def letters(names: Iterable[str]) -> list[str]:
    """The options' letters, sorted: ["A", "F"]."""
    return sorted(LETTERS[n] for n in names)


# ── B: the question's type ────────────────────────────────────

FACT = "fact"
DECISION = "decision"
GOAL = "goal"
COMMITMENT = "commitment"
RELATIONSHIP = "relationship"
HISTORY = "history"
CHANGE = "change"
QUERY_TYPES = (FACT, DECISION, GOAL, COMMITMENT, RELATIONSHIP, HISTORY, CHANGE)


def _phrases(*groups: str) -> tuple[tuple[str, ...], ...]:
    """Keywords and phrases, "|"-separated; each one a tuple of words."""
    return tuple(tuple(p.split()) for g in groups for p in g.split("|") if p.strip())


#: Per type: English, Tanglish (Tamil in Latin letters) and Tamil keywords. A
#: keyword is one word or a phrase of words in a row. An ASCII word matches
#: only itself; a Tamil word matches as a prefix (case endings: முடிவு, முடிவை).
KEYWORDS: dict[str, tuple[tuple[str, ...], ...]] = {
    DECISION: _phrases(
        "decide|decided|decides|deciding|decision|decisions|chose|choose|chosen|choice|choices"
        "|opted|picked",
        "mudivu|mudivedutha|mudivu panniten|theermanam",
        "முடிவ|தீர்மான|தேர்ந்தெடு",
    ),
    GOAL: _phrases(
        "goal|goals|aim|aims|ambition|ambitions|aspiration|aspirations|aspire|target|targets"
        "|objective|objectives|priority|priorities|want to become|want to be",
        "ilakku|latchiyam|lakshiyam",
        "இலக்க|குறிக்கோள|லட்சிய",
    ),
    COMMITMENT: _phrases(
        "commitment|commitments|committed|promise|promises|promised|task|tasks|todo|todos"
        "|deadline|deadlines|due|overdue|reminder|reminders|remind|pending|responsible"
        "|responsibility|responsibilities|priority|priorities|appointment|appointments"
        "|afford|constraint|constraints|obligation|obligations|must|owe|have to|has to"
        "|need to do|not done|look after|take care",
        "pannanum|seiyanum|seyyanum|kattanum|mudikkanum|kadamai|poruppu",
        "கடம|நினைவூட்ட|கெடு|பொறுப்ப|செய்ய வேண்ட",
    ),
    RELATIONSHIP: _phrases(
        "why|because|cause|causes|caused|reason|reasons|connect|connects|connected|connection"
        "|connections|relate|relates|related|relation|relations|relationship|depend|depends"
        "|depended|dependency|dependencies|dependent|blocked|blocking|blocker|blockers|affect"
        "|affects|affected|consequence|consequences|result|resulted|led|leads|lead to|held up"
        "|who|whom",
        "yen|kaaranam|karanam|sambandham|thodarbu",
        "ஏன|காரண|தொடர்ப|சம்பந்த|யார",
    ),
    HISTORY: _phrases(
        "was|were|previously|previous|earlier|former|formerly|ago|originally|used to|back then"
        "|in the past|at that time",
        "munnadi|munbu|pazhaya|appo|irundhen|irundhuchu",
        "முன்ப|முன்னர|பழைய|அப்போத|இருந்த",
    ),
    CHANGE: _phrases(
        "change|changes|changed|changing|replaced|replace|replaces|superseded|supersede"
        "|updated|update|updates|different|anymore|since|no longer",
        "maari|maariduchu|maaridichu|maathitten|maathunom|maatram",
        "மாற",
    ),
}
#: Words that make a question broad ("what are my priorities?"): it is a fact
#: question too, so the memories are not narrowed to one kind.
BROAD_WORDS = frozenset({"priority", "priorities", "focus", "important", "overview"})
#: A four-digit year in the question: it asks about that time.
_YEAR = re.compile(r"^(19|20)\d\d$")
#: The kinds a question can be only about; with no fact, relationship or
#: history part, memories are narrowed to that kind (see query_type_filter).
KIND_TYPES = frozenset({DECISION, GOAL, COMMITMENT})
WIDE_TYPES = frozenset({FACT, RELATIONSHIP, HISTORY})
#: Question type -> the standing reason that answers it.
STANDING_FOR = {DECISION: CURRENT_DECISION, COMMITMENT: DUE_INTENTION}
STANDING = frozenset(STANDING_FOR.values())
#: Standing reason -> the record kind (source_ref.kind) it brings.
KIND_OF_STANDING = {CURRENT_DECISION: "decision", DUE_INTENTION: "intention"}
#: Words that name a kind in a memory's text, tags or fact type.
KIND_TAG_WORDS = {
    DECISION: frozenset({"decision", "decid", "decided"}),
    GOAL: frozenset({"goal", "aim", "ambition", "aspiration", "target", "objective"}),
    COMMITMENT: frozenset(
        {"task", "todo", "deadlin", "deadline", "commitment", "promis", "promise", "reminder"}
    ),
}


def tokens(text_: str) -> list[str]:
    """Lower-case words of *text_*: runs of letters, marks and digits of any script.

    Apostrophes are dropped first ("mother's" -> "mothers"). Tamil vowel signs
    are marks, so they stay in their word (D10).
    """
    folded = unicodedata.normalize("NFKC", text_ or "").lower()
    folded = folded.replace("'", "").replace("’", "")
    out: list[str] = []
    word: list[str] = []
    for ch in folded + " ":
        if unicodedata.category(ch)[0] in "LMN":
            word.append(ch)
        elif word:
            out.append("".join(word))
            word = []
    return out


def _word_matches(token: str, keyword: str) -> bool:
    if keyword.isascii():
        return token == keyword
    return token.startswith(keyword)


def _has_phrase(words: list[str], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    return any(
        all(_word_matches(words[i + j], phrase[j]) for j in range(n))
        for i in range(len(words) - n + 1)
    )


def _is_keyword(word: str) -> bool:
    return any(
        len(p) == 1 and _word_matches(word, p[0]) for group in KEYWORDS.values() for p in group
    )


def classify(query: str, *, as_of: bool = False) -> frozenset[str]:
    """The question's types (one or more of QUERY_TYPES); deterministic, no model.

    A type is present when one of its keywords is. An ``as_of`` question or one
    naming a year is about history. It is a fact question too when it has a
    subject word that is no keyword (sufficiency.query_terms), when it is
    broad, or when nothing else matched.
    """
    words = tokens(query)
    types = {t for t, group in KEYWORDS.items() if any(_has_phrase(words, p) for p in group)}
    if as_of or any(_YEAR.match(w) for w in words):
        types.add(HISTORY)
    subject = any(
        not _is_keyword(w) and not _YEAR.match(w)
        for term in sufficiency.query_terms(query)
        for w in term.words
    )
    if subject or not types or BROAD_WORDS & set(words):
        types.add(FACT)
    return frozenset(types)


def supports(query: str, text_: str) -> bool:
    """Whether *text_* (an item's words and labels) supports any term of *query*."""
    return bool(sufficiency.assess(query, [text_]).supported)


def names_kind(text_: str, types: Iterable[str]) -> bool:
    """Whether *text_* has a word that names one of the kinds in *types*."""
    words = sufficiency.support_words(text_) | {w for w in tokens(text_)}
    return any(words & KIND_TAG_WORDS[t] for t in types if t in KIND_TAG_WORDS)


def query_type_filter(
    query: str,
    items: list[Any],
    support: dict[str, str],
    types: frozenset[str],
    protected: set[str],
) -> tuple[list[Any], list[Any], set[str]]:
    """(kept, left out, standing keys the question asks for) under B.

    A decision or intention, standing or matched by a keyword, stays when the
    question asks for its kind or when its own words support one of the
    question's terms. The keyword match ORs every word, so one shared word
    ("job" in "Postgres job queue", the "000" of two amounts) brought records
    in; support needs a whole one-word term or two words of a longer one,
    and light verbs ("take") and short numbers are no terms at all.
    """
    wanted = {STANDING_FOR[t] for t in types if t in STANDING_FOR}
    wanted_kinds = {KIND_OF_STANDING[r] for r in wanted}
    narrow = bool(types & KIND_TYPES) and not types & WIDE_TYPES
    kinds = types & KIND_TYPES
    kept: list[Any] = []
    out: list[Any] = []
    asked: set[str] = set()
    for item in items:
        key = item.source_ref.key()
        text_ = support.get(key, item.content)
        if item.reason in PULLED_REASONS:
            keep = True
        elif item.source_ref.kind in KIND_OF_STANDING.values():
            keep = item.source_ref.kind in wanted_kinds or supports(query, text_)
            if item.reason in wanted:
                asked.add(key)
        elif narrow and item.source_ref.kind == "memory":
            keep = supports(query, text_) or names_kind(text_, kinds)
        else:
            keep = True
        (kept if keep or key in protected else out).append(item)
    return kept, out, asked


# ── C: typed links ────────────────────────────────────────────


def link_seeds(items: list[Any], order_key: Any, n: int = LINK_SEEDS) -> list[Any]:
    """The top *n* memory items in snapshot order: the hits whose links C follows.

    Learned neighbours are not seeds: they are what C judges.
    """
    hits = (i for i in items if i.source_ref.kind == "memory" and i.reason != NEIGHBOUR)
    return sorted(hits, key=order_key)[: int(n)]


def linked_to(rows: list[tuple[Any, ...]], seed_ids: set[str]) -> dict[str, set[str]]:
    """memory id -> the seeds a typed link (either way) joins it to; a seed is linked."""
    out: dict[str, set[str]] = {s: set() for s in seed_ids}
    for source, target, *_ in rows:
        a, b = str(source), str(target)
        if a == b:
            continue
        if a in seed_ids:
            out.setdefault(b, set()).add(a)
        if b in seed_ids:
            out.setdefault(a, set()).add(b)
    return out


def drop_unlinked_neighbours(
    items: list[Any],
    links: dict[str, set[str]],
    protected: set[str],
    *,
    t: Tunables = DEFAULT_TUNABLES,
) -> tuple[list[Any], list[Any]]:
    """(kept, left out): learned neighbours below LINK_FLOOR with no typed link to a seed."""
    kept: list[Any] = []
    out: list[Any] = []
    for item in items:
        weak = item.reason == NEIGHBOUR and item.score < t.link_floor
        unlinked = item.source_ref.id not in links
        if weak and unlinked and item.source_ref.key() not in protected:
            out.append(item)
        else:
            kept.append(item)
    return kept, out


# ── D: near-duplicates ────────────────────────────────────────

_NEGATIONS = frozenset(ev._NEGATIONS)


def _shape(text_: str) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """(words, numbers, negations) of *text_*, punctuation gone."""
    words = frozenset(tokens(text_))
    numbers = frozenset(w for w in words if any(ch.isdigit() for ch in w))
    return words, numbers, words & _NEGATIONS


def near_duplicate(a: Any, b: Any, *, t: Tunables = DEFAULT_TUNABLES) -> bool:
    """Same kind, slot, origin and evidence; same numbers and negations; high overlap."""
    if (a.source_ref.kind, a.dimension, a.origin, a.evidence) != (
        b.source_ref.kind,
        b.dimension,
        b.origin,
        b.evidence,
    ):
        return False
    wa, na, xa = _shape(a.content)
    wb, nb, xb = _shape(b.content)
    if na != nb or xa != xb or not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= t.duplicate_similarity


def dedupe(
    items: list[Any], protected: set[str], *, t: Tunables = DEFAULT_TUNABLES
) -> tuple[list[Any], list[Any]]:
    """(kept, left out): each near-duplicate after the first (in the given order) goes."""
    kept: list[Any] = []
    out: list[Any] = []
    for item in items:
        if item.source_ref.key() not in protected and any(
            near_duplicate(k, item, t=t) for k in kept
        ):
            out.append(item)
        else:
            kept.append(item)
    return kept, out


# ── E: evidence; A: rank ──────────────────────────────────────

#: Evidence kinds, strongest first (core/evidence.py).
EVIDENCE_ORDER = (ev.SAID, ev.DOCUMENT, ev.OBSERVED, ev.OUTSIDE, ev.SUMMARY, ev.INFERRED)
FRESHNESS_ORDER = ("fresh", "recent", "aging", "stale", "unknown")
#: Statuses that describe how things were, not how they are.
HISTORICAL = frozenset({"superseded", "archived", "expired"})


def _rank_of(value: str, order: tuple[str, ...]) -> int:
    return order.index(value) if value in order else len(order)


def conflict_sides(conflicts: Iterable[Any]) -> set[str]:
    """The item keys ("memory:<id>") on either side of any of *conflicts*."""
    return {s.source_ref.key() for c in conflicts for s in c.sides}


def ranked(
    items: list[Any],
    order_key: Any,
    *,
    rank: bool,
    evidence: bool,
    confidence: dict[str, float] | None = None,
    t: Tunables = DEFAULT_TUNABLES,
) -> list[Any]:
    """*items* in snapshot order, ties (TIE_TOLERANCE) broken by A and/or E.

    The base order is the snapshot's own (score, then recorded time, kind,
    id), so relevance always leads: a tie-break only reorders items whose
    scores are within the tolerance of the tie's first item.
    """
    base = sorted(items, key=order_key)
    if not (rank or evidence) or len(base) < 2:
        return base
    confidence = confidence or {}

    def tie_key(pos_item: tuple[int, Any]) -> tuple[Any, ...]:
        pos, i = pos_item
        ev_rank = _rank_of(i.evidence, EVIDENCE_ORDER)
        if rank:
            return (
                i.status in HISTORICAL,
                not i.confirmed,
                -confidence.get(i.source_ref.key(), 0.0),
                ev_rank,
                _rank_of(i.freshness, FRESHNESS_ORDER),
                pos,
            )
        return (not i.confirmed, ev_rank, pos)

    out: list[Any] = []
    tie: list[tuple[int, Any]] = []
    top = 0.0
    for pos, item in enumerate(base):
        if tie and top - item.score > max(1e-9, abs(top) * t.tie_tolerance):
            out += [i for _, i in sorted(tie, key=tie_key)]
            tie = []
        if not tie:
            top = item.score
        tie.append((pos, item))
    out += [i for _, i in sorted(tie, key=tie_key)]
    return out


# ── F: adaptive cut ───────────────────────────────────────────


def hub_adjusted(
    similarity: dict[str, float],
    probe_similarity: dict[str, list[float]],
    *,
    t: Tunables = DEFAULT_TUNABLES,
) -> dict[str, float]:
    """G: each similarity minus HUB_WEIGHT x its mean similarity to the probes.

    A record with no probe similarities keeps its own. Only the relevance F
    cuts on (and the order A ties on) changes; the item's shown score does not.
    """
    out: dict[str, float] = {}
    for key, value in similarity.items():
        probes = probe_similarity.get(key) or []
        mean = sum(probes) / len(probes) if probes else 0.0
        out[key] = value - t.hub_weight * mean
    return out


#: Reasons F cuts when a cosine is known: what search and the learned links
#: brought. Entity links (the question names the thing) and C's typed-link
#: pulls are kept for B and C to judge.
CUT_REASONS = frozenset({SEARCH_HIT, NEIGHBOUR})


def adaptive_cut(
    items: list[Any],
    protected: set[str],
    relevance: dict[str, float] | None = None,
    *,
    t: Tunables = DEFAULT_TUNABLES,
) -> tuple[list[Any], list[Any]]:
    """(kept, left out): the memory hits after the relevance drop-off (see module doc).

    *relevance* is item key -> cosine similarity to the question (hub-adjusted
    under G). Without it, the search hits' fused rank score is used.
    """
    if relevance:
        floor, gap = t.cosine_floor, t.cosine_gap
        scored = [
            (relevance[i.source_ref.key()], i)
            for i in items
            if i.reason in CUT_REASONS and i.source_ref.key() in relevance
        ]
    else:
        floor, gap = t.relative_floor, t.elbow_gap
        scored = [(i.score, i) for i in items if i.reason == SEARCH_HIT]
    hits = sorted(scored, key=lambda p: (-p[0], p[1].source_ref.kind, p[1].source_ref.id))
    if len(hits) <= t.min_keep or hits[0][0] <= 0:
        return list(items), []
    top = hits[0][0]
    cut = len(hits)
    for n in range(int(t.min_keep), len(hits)):
        score, before = hits[n][0], hits[n - 1][0]
        if score < floor * top or before - score >= gap * top:
            cut = n
            break
    gone = {i.source_ref.key() for _, i in hits[cut:]} - protected
    return (
        [i for i in items if i.source_ref.key() not in gone],
        [i for i in items if i.source_ref.key() in gone],
    )


# ── H, I: asked for as a whole ─────────────────────────────────


def asks_for(query: str, types: frozenset[str], kind: str) -> bool:
    """Whether the question asks for *kind* (GOAL, COMMITMENT) as a whole.

    It does when *kind* is one of its types and it has no subject of its own
    (no FACT type: "what are my active goals?") or is broad ("what are my
    current priorities?", BROAD_WORDS). "my goal of becoming an engineering
    manager" names a subject, so only the records that support it count.
    """
    if kind not in types:
        return False
    return FACT not in types or bool(BROAD_WORDS & set(tokens(query)))


#: H: words of a question about due times ("which deadlines are coming up?"):
#: an intention with no due time cannot answer it by kind, only by words or meaning.
DUE_ASK = _phrases(
    "deadline|deadlines|due|overdue|coming up|upcoming|this week|next week|today|tomorrow"
    "|next few days",
    "kedu|naalaikku|indha vaaram|adutha vaaram",
    "கெடு|நாளை|இந்த வார|அடுத்த வார",
)


def asks_for_due(query: str) -> bool:
    """Whether *query* asks about due times (DUE_ASK)."""
    words = tokens(query)
    return any(_has_phrase(words, p) for p in DUE_ASK)


#: I: tags that make a memory a goal record.
GOAL_TAGS = frozenset(
    {"goal", "goals", "aim", "ambition", "aspiration", "target", "objective", "ilakku", "இலக்கு"}
)
#: I: words that make an extractor ``intention`` a goal ("wants to run", "plans to pass").
GOAL_WORDS = frozenset(
    {
        "goal",
        "goals",
        "want",
        "wants",
        "plan",
        "plans",
        "planning",
        "aim",
        "aims",
        "aspire",
        "aspires",
        "hope",
        "hopes",
        "target",
        "become",
        "ambition",
    }
)
#: I: the fact type the extractor gives a want or a plan (extraction/llm.py).
GOAL_FACT_TYPE = "intention"


def is_goal_memory(tags: Iterable[str] | None, fact_type: str | None, text_: str) -> bool:
    """A goal record: tagged as a goal, or an extracted ``intention`` in goal words."""
    tagged = {str(t).strip().lower() for t in (tags or []) if isinstance(t, str)}
    if tagged & GOAL_TAGS:
        return True
    if str(fact_type or "").strip().lower() != GOAL_FACT_TYPE:
        return False
    return bool(GOAL_WORDS & set(tokens(text_)))


def cosine(a: list[float] | None, b: list[float] | None) -> float | None:
    """Cosine similarity of two vectors; None when either is missing, empty or mismatched."""
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else None


# ── J, K: overview questions ──────────────────────────────────

#: J: words and phrases of an overview or aggregate question (English,
#: Tanglish, Tamil; matched like KEYWORDS: an ASCII word itself, a Tamil word
#: as a prefix). A question that asks what is missing
#: (sufficiency.asks_for_gaps) is one too.
OVERVIEW_KEYWORDS = _phrases(
    "overview|summary|summarise|summarize|sum up|overall|everything|in general|big picture"
    "|whole picture|situation|finances|financial|consider|considerations|factors|constraints"
    "|what else|all my|all of my|state of",
    "ellam|ellaamae|ellame|motham|mothama|nilamai|nelamai|panam vishayam|kanakku",
    "எல்லா|மொத்த|சுருக்க|நிலைம|நிதி நிலை",
)


def is_overview(query: str) -> bool:
    """Whether *query* asks for an overview (OVERVIEW_KEYWORDS) or for what is missing."""
    words = tokens(query)
    if any(_has_phrase(words, p) for p in OVERVIEW_KEYWORDS):
        return True
    return sufficiency.asks_for_gaps(query)


#: K: a life domain -> (the question's words for it, the tags its records carry).
DOMAINS: dict[str, tuple[tuple[tuple[str, ...], ...], frozenset[str]]] = {
    "finance": (
        _phrases(
            "finance|finances|financial|money|loan|loans|emi|salary|income|budget|savings"
            "|spending|expenses|expense|afford|debt|investment|investments",
            "panam|kaasu|selavu|sambalam|kadan|varumanam|semippu",
            "பண|காசு|செலவ|சம்பள|கடன|வருமான|சேமிப்ப|நிதி",
        ),
        frozenset({"finance", "money", "loan", "income", "budget", "savings", "investment"}),
    ),
    "health": (
        _phrases(
            "health|medical|doctor|clinic|hospital|medicine|medicines|illness|diabetes",
            "udambu|udal nalam|maruthuvam|maruthuvar|aaspathiri",
            "உடல்நல|உடல் நல|மருத்துவ|மருந்த|நோய",
        ),
        frozenset({"health", "medical"}),
    ),
    "work": (
        _phrases(
            "work|job|career|office|project|projects|manager|promotion",
            "velai|office velai|udhyogam",
            "வேலை|பணிய|அலுவலக",
        ),
        frozenset({"work", "career", "project"}),
    ),
    "family": (
        _phrases(
            "family|kids|children|child|daughter|son|husband|wife|mother|father|parents",
            "kudumbam|amma|appa|pasanga|kuzhandhai|purushan|manaivi",
            "குடும்ப|அம்மா|அப்பா|குழந்த|மகள|மகன|கணவ|மனைவ",
        ),
        frozenset({"family"}),
    ),
    "learning": (
        _phrases(
            "learning|learn|study|studying|course|courses|exam|exams|certification",
            "padippu|padikkuren|thervu",
            "படிப்ப|படிக்க|தேர்வ|பயிற்சி",
        ),
        frozenset({"learning"}),
    ),
}


def query_domains(query: str) -> frozenset[str]:
    """The life domains *query* names (DOMAINS keys)."""
    words = tokens(query)
    return frozenset(
        name
        for name, (phrases, _) in DOMAINS.items()
        if any(_has_phrase(words, p) for p in phrases)
    )


def domain_tags(domains: Iterable[str]) -> frozenset[str]:
    """The tags of the records of *domains*."""
    return frozenset(t for d in domains if d in DOMAINS for t in DOMAINS[d][1])


def overview_tunables(t: Tunables) -> Tunables:
    """J: *t* with F's cut loosened for an overview question (never tightened)."""
    return dataclasses.replace(
        t,
        min_keep=max(int(t.min_keep), int(t.overview_min_keep)),
        cosine_floor=min(t.cosine_floor, t.overview_floor),
        relative_floor=min(t.relative_floor, t.overview_floor),
    )


# ── L: blockers and dependencies ──────────────────────────────

#: L: words of a question that asks what holds things up, or for priorities
#: (a blocker is part of the answer). English, Tanglish, Tamil; matched like
#: KEYWORDS (an ASCII word itself, a Tamil word as a prefix).
BLOCKER_ASK = _phrases(
    "priority|priorities|focus|stopping|stopping me|holding me back|held up|blocked|blocking"
    "|blocker|blockers|stuck|waiting on|waiting for|bottleneck|bottlenecks|obstacle|obstacles"
    "|in my way",
    "thadai|thadangal|mudiyala|nikkudhu|nikkuthu|kaathirukken|kaathiruken|stuck aayiduchu",
    "தடை|தடங்கல|முன்னுரிமை|காத்திருக்க|நிற்கிற|நின்றுவிட",
)
#: L: words and tags of a record that is a blocker or a dependency.
BLOCKER_TEXT = _phrases(
    "blocked|blocking|blocker|blockers|stuck|held up|on hold|waiting on|waiting for|depends on"
    "|depend on|dependent on|dependency|dependencies|still has not|still hasnt",
    "thadai|nikkudhu|nikkuthu|kaathirukku|kaathirukkudhu|depend aagudhu",
    "தடை|தடங்கல|காத்திருக்க|சார்ந்து|நின்றுவிட",
)
BLOCKER_TAGS = frozenset(
    {"blocker", "blockers", "blocked", "dependency", "dependencies", "waiting", "தடை"}
)
#: L: words that say a blocker or a dependency is over.
RESOLVED_TEXT = _phrases(
    "resolved|unblocked|shipped|finished|fixed|delivered|completed|done|no longer|not blocked"
    "|can use|is available|now available|got access|received access|cleared|sorted",
    "mudinjiduchu|mudinjudhu|ready aayiduchu|kedachiduchu|kidaichiduchu|sari aayiduchu",
    "முடிந்துவிட|முடிந்தது|தீர்ந்த|கிடைத்துவிட|சரியாகிவிட",
)
#: L: a newer record of the same kind resolves a blocker when they share at
#: least this many subject words, and half of the blocker's (and the newer
#: one says it is over).
RESOLVE_OVERLAP = 3


def _phrase_in(text_: str, phrases: tuple[tuple[str, ...], ...]) -> bool:
    words = tokens(text_)
    return any(_has_phrase(words, p) for p in phrases)


def asks_for_blockers(query: str) -> bool:
    """Whether *query* asks for priorities, what holds things up, or a work overview."""
    if _phrase_in(query, BLOCKER_ASK):
        return True
    return is_overview(query) and "work" in query_domains(query)


def _blocker_ask_words() -> frozenset[str]:
    return frozenset(w for p in BLOCKER_ASK if len(p) == 1 for w in p)


def blocker_subject(query: str) -> bool:
    """Whether *query* names a subject beyond the blocker words ("blocked on PayFlow").

    Its terms' words (sufficiency.query_terms) that are no keyword, no blocker
    word and no year. Without one, every current blocker answers it.
    """
    asked = _blocker_ask_words()
    return any(
        not _is_keyword(w) and w not in asked and not _YEAR.match(w)
        for term in sufficiency.query_terms(query)
        for w in term.words
    )


def _tag_set(tags: Iterable[str] | None) -> set[str]:
    return {str(t).strip().lower() for t in (tags or []) if isinstance(t, str)}


def is_resolved_text(text_: str) -> bool:
    """Whether *text_* says a blocker or a dependency is over."""
    return _phrase_in(text_, RESOLVED_TEXT)


def is_blocker_text(tags: Iterable[str] | None, text_: str) -> bool:
    """A blocker or dependency record that does not itself say it is over."""
    if is_resolved_text(text_):
        return False
    return bool(_tag_set(tags) & BLOCKER_TAGS) or _phrase_in(text_, BLOCKER_TEXT)


def subject_words(text_: str) -> frozenset[str]:
    """*text_*'s content words: no stop or frame words, no numbers, no blocker words."""
    skip = {w for g in (BLOCKER_TEXT, RESOLVED_TEXT) for p in g for w in p}
    return frozenset(
        w
        for w in tokens(text_)
        if w not in sufficiency.NON_CONTENT
        and w not in skip
        and not any(ch.isdigit() for ch in w)
        and len(w) > 2
    )


def resolves(newer_text: str, newer_tags: Iterable[str] | None, blocker: Any) -> bool:
    """Whether a newer record (*newer_text*, *newer_tags*) resolves *blocker*, unlinked.

    It says it is over, it carries one of the blocker's blocker/dependency
    tags, and they share at least RESOLVE_OVERLAP subject words and at least
    half of the blocker's own.
    """
    if not is_resolved_text(newer_text):
        return False
    shared_tags = _tag_set(newer_tags) & _tag_set(getattr(blocker, "tags", None)) & BLOCKER_TAGS
    if not shared_tags:
        return False
    own = subject_words(str(getattr(blocker, "content", "") or ""))
    overlap = subject_words(newer_text) & own
    return len(overlap) >= RESOLVE_OVERLAP and len(overlap) * 2 >= len(own)


__all__ = [
    "DEFAULT_TUNABLES",
    "LINKED_EVIDENCE",
    "MODES",
    "MODE_NAMES",
    "NAMES",
    "OPTIONS",
    "QUERY_TYPES",
    "adaptive_cut",
    "classify",
    "conflict_sides",
    "dedupe",
    "drop_unlinked_neighbours",
    "letters",
    "link_seeds",
    "linked_to",
    "mode",
    "near_duplicate",
    "parse",
    "query_type_filter",
    "ranked",
    "Mode",
    "Tunables",
]
