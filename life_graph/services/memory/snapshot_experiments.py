"""Eval-only precision experiments for the context snapshot (M8). All off by default.

The context snapshot (services/memory/snapshot.py) holds every candidate the
reads found: search hits, linked memories, matching and standing decisions and
intentions. On the M8 eval (scripts/eval_context_quality.py, bge-m3 arm)
recall is 0.88-1.0 but precision only 0.16-0.41: most items are noise. These
options try ways to cut that noise. They exist to be measured, not shipped.

How they are switched on
========================

Only through ``assemble_context(..., experiments=frozenset({...}))``. There is
no setting, no environment variable and no API parameter: the kernel, the API
and shadow mode never pass it, so production snapshots never change. The eval
passes it from ``--experiments A,B,...`` and records it in its report. With
no experiment the snapshot is byte-identical to before
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

The constants are first guesses, not tuned values; the eval can set them
for a run (:data:`TUNABLE`) and should tune on its ``--split tune`` half.
"""

from __future__ import annotations

import re
import unicodedata
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

#: Option letter -> name, as the eval's ``--experiments`` takes them.
OPTIONS = {
    "A": RANK,
    "B": QUERY_TYPE,
    "C": LINKS,
    "D": DEDUPE,
    "E": EVIDENCE,
    "F": BUDGET,
    "G": HUB,
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
)


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
        if item.source_ref.kind in KIND_OF_STANDING.values():
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
    items: list[Any], links: dict[str, set[str]], protected: set[str]
) -> tuple[list[Any], list[Any]]:
    """(kept, left out): learned neighbours below LINK_FLOOR with no typed link to a seed."""
    kept: list[Any] = []
    out: list[Any] = []
    for item in items:
        weak = item.reason == NEIGHBOUR and item.score < LINK_FLOOR
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


def near_duplicate(a: Any, b: Any) -> bool:
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
    return len(wa & wb) / len(wa | wb) >= DUPLICATE_SIMILARITY


def dedupe(items: list[Any], protected: set[str]) -> tuple[list[Any], list[Any]]:
    """(kept, left out): each near-duplicate after the first (in the given order) goes."""
    kept: list[Any] = []
    out: list[Any] = []
    for item in items:
        if item.source_ref.key() not in protected and any(near_duplicate(k, item) for k in kept):
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
        if tie and top - item.score > max(1e-9, abs(top) * TIE_TOLERANCE):
            out += [i for _, i in sorted(tie, key=tie_key)]
            tie = []
        if not tie:
            top = item.score
        tie.append((pos, item))
    out += [i for _, i in sorted(tie, key=tie_key)]
    return out


# ── F: adaptive cut ───────────────────────────────────────────


def hub_adjusted(
    similarity: dict[str, float], probe_similarity: dict[str, list[float]]
) -> dict[str, float]:
    """G: each similarity minus HUB_WEIGHT x its mean similarity to the probes.

    A record with no probe similarities keeps its own. Only the relevance F
    cuts on (and the order A ties on) changes; the item's shown score does not.
    """
    out: dict[str, float] = {}
    for key, value in similarity.items():
        probes = probe_similarity.get(key) or []
        mean = sum(probes) / len(probes) if probes else 0.0
        out[key] = value - HUB_WEIGHT * mean
    return out


#: Reasons F cuts when a cosine is known: what search and the learned links
#: brought. Entity links (the question names the thing) and C's typed-link
#: pulls are kept for B and C to judge.
CUT_REASONS = frozenset({SEARCH_HIT, NEIGHBOUR})


def adaptive_cut(
    items: list[Any], protected: set[str], relevance: dict[str, float] | None = None
) -> tuple[list[Any], list[Any]]:
    """(kept, left out): the memory hits after the relevance drop-off (see module doc).

    *relevance* is item key -> cosine similarity to the question (hub-adjusted
    under G). Without it, the search hits' fused rank score is used.
    """
    if relevance:
        floor, gap = COSINE_FLOOR, COSINE_GAP
        scored = [
            (relevance[i.source_ref.key()], i)
            for i in items
            if i.reason in CUT_REASONS and i.source_ref.key() in relevance
        ]
    else:
        floor, gap = RELATIVE_FLOOR, ELBOW_GAP
        scored = [(i.score, i) for i in items if i.reason == SEARCH_HIT]
    hits = sorted(scored, key=lambda p: (-p[0], p[1].source_ref.kind, p[1].source_ref.id))
    if len(hits) <= MIN_KEEP or hits[0][0] <= 0:
        return list(items), []
    top = hits[0][0]
    cut = len(hits)
    for n in range(int(MIN_KEEP), len(hits)):
        score, before = hits[n][0], hits[n - 1][0]
        if score < floor * top or before - score >= gap * top:
            cut = n
            break
    gone = {i.source_ref.key() for _, i in hits[cut:]} - protected
    return (
        [i for i in items if i.source_ref.key() not in gone],
        [i for i in items if i.source_ref.key() in gone],
    )


__all__ = [
    "LINKED_EVIDENCE",
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
    "near_duplicate",
    "parse",
    "query_type_filter",
    "ranked",
]
