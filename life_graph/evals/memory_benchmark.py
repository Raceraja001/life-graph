"""Reproducible Memory Evaluation Laboratory (P1 — docs/LIFE_GRAPH_IMPROVEMENT_PLAN.md).

Evaluates Life Graph's memory retrieval, temporal/bitemporal filtering, correction
supersession, claim-level provenance, forgetting/deletion isolation, and adaptive
abstention on separate tuning (`test_life.json`) and held-out (`test_life_2.json`)
synthetic datasets, plus deterministic lifecycle regression cases.

Compares six retrieval configurations one variable at a time:
  1. `1_lexical_bm25`: BM25 keyword baseline over raw messages.
  2. `2_vector_ngram`: Deterministic character/word n-gram cosine similarity baseline.
  3. `3_hybrid_rrf`: Reciprocal Rank Fusion (BM25 + vector) with date-anchored rendering.
  4. `4_graph_entity_expansion`: Alias, kinship & bilingual graph expansion + semantic facet tags.
  5. `5_rerank_temporal_provenance`: Temporal supersession reranking (`current` vs `past`/`old_fact`).
  6. `6_multistep_bridge`: Multi-step bridge retrieval (a second hop over the top hits' entities).

Abstention ("I don't know") is not one of the methods. Until 2026-11 method 6
abstained through hand-written term lists that named the datasets' own
unanswerable questions ("swathi's birthday", "munnar homestay", ...), on the
held-out split too, so its abstention precision/recall of 1.0 measured the
lists, not the method. It now retrieves only. Abstention is measured separately
by `abstention_probe()`: one general rule (the best top-5 hit's lexical
entailment of the question is below a floor), its floor chosen on the tuning
split alone and then applied unchanged to the held-out split. Production
abstains through the local relevance judge (services/memory/retrieval.py),
which this offline lab does not run, so the probe is a report, not a gate.

Stages 4 and 5 run on hand-written lists: facets, aliases, question expansions,
topic slots and past/current cues. Until 2026-11 those lists also named the
held-out split's people, places and products ("senthil", "saibaba colony",
"redmi", ...), and `build_corpus` added notes written for held-out messages, so
the held-out scores of stages 4-5 were an upper bound. Every string that occurs
in the held-out split but not in the tuning split was then removed (nothing was
added), so the lists now come from the tuning split alone, and
`tests/unit/test_memory_benchmark_lab.py` fails if a held-out-only string comes
back. `lab_rule_strings()` lists what that test checks.

`compare_adaptive_early_exit()` additionally runs the top-of-ladder method twice per
split — once with the adaptive early-exit gate off and once with it on — so the
latency saved by skipping entity expansion and the bridge hop can be weighed against
any retrieval quality it costs. The gate itself is not re-implemented here: the
production `assess_hit_evidence()` decides, over the same thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from life_graph.core.evidence import (
    ABSTAIN,
    CONTRADICTED,
    SUPPORTED,
    extract_claim_evidence,
    lexical_entailment_score,
)
from life_graph.services.episodes import time_window
from life_graph.services.memory.retrieval import (
    EARLY_EXIT_CONFIDENCE,
    EARLY_EXIT_ENTAILMENT,
    assess_hit_evidence,
    is_bitemporally_valid,
)

ROOT = Path(__file__).resolve().parents[2]
TUNING_DATASET = ROOT / "evals" / "memory_structures" / "test_life.json"
HELDOUT_DATASET = ROOT / "evals" / "memory_structures" / "test_life_2.json"

BENCHMARK_METHODS = (
    "1_lexical_bm25",
    "2_vector_ngram",
    "3_hybrid_rrf",
    "4_graph_entity_expansion",
    "5_rerank_temporal_provenance",
    "6_multistep_bridge",
)

#: The only method that runs the whole expansion stack, so the only one the
#: adaptive early-exit gate can shorten. `compare_adaptive_early_exit()` uses it.
PRIMARY_METHOD = "6_multistep_bridge"

#: Early-exit modes for `retrieve_for_method`.
#: `off` is the historical path — the gate is never consulted and nothing is spent
#: assessing it. `measure` pays the assessment and records the verdict but keeps the
#: full expansion, which is what makes it the honest baseline for a latency comparison:
#: production assesses the top hit either way, so the only variable left between
#: `measure` and `on` is whether the expansion below is skipped.
EARLY_EXIT_OFF = "off"
EARLY_EXIT_MEASURE = "measure"
EARLY_EXIT_ON = "on"
EARLY_EXIT_MODES = (EARLY_EXIT_OFF, EARLY_EXIT_MEASURE, EARLY_EXIT_ON)

#: Extraction confidence for a benchmark message: the corpus stores what was said
#: verbatim, so nothing was distilled and there is no misreading to discount.
#: This is the *most* generous value available, which makes every measured exit
#: rate below an upper bound on what the production gate would fire at.
CAPTURE_EXTRACTION_CONFIDENCE = 1.0

#: Timing passes per (split, mode). Each question's reported latency is its minimum
#: across passes — the pass least contaminated by scheduler noise. Retrieval is
#: deterministic, so repeating it cannot change any quality metric.
LATENCY_PASSES = 3

#: Calibrated-confidence floors swept in the sensitivity study. The production floor
#: comes first; the rest exist because `EARLY_EXIT_CONFIDENCE` is strict enough that
#: the headline exit rate alone says little about the latency/quality curve.
CONFIDENCE_FLOOR_SWEEP = (EARLY_EXIT_CONFIDENCE, 0.90, 0.88, 0.86, 0.85)

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "she",
        "he",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "why",
        "with",
        "would",
        "you",
        "your",
        "tell",
        "about",
        "everything",
        "know",
        "remember",
        "many",
        "much",
    }
)

# Facet rules: when a message contains any trigger substring, attach semantic facet tokens
# so Stage 4+ bridges implicit category questions ("What phone do I use?" -> "Pixel 10").
FACET_TRIGGERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("my name is", "i'm ", "i am ", "calls me", "call me"), "name owner identity nickname"),
    (
        (
            "live in",
            "moved to",
            "shifted to",
            "adyar",
            "rs puram",
            "madurai",
            "coimbatore",
            "chennai",
        ),
        "live residence city address stay வசிக்கிறேன் வீடு",
    ),
    (
        ("work at", "works at", "joined", "first day at", "tessera", "freshworks", "offer"),
        "work company employer job நிறுவனம் வேலை",
    ),
    (
        (
            "engineering manager",
            "tech lead",
            "staff engineer",
            "senior developer",
            "architect",
            "doctor",
            "promoted",
        ),
        "job title role designation profession occupation do",
    ),
    (("pixel", "iphone"), "phone mobile handset device use"),
    (("creta", "i20", "hyundai", "nexon", "car"), "car vehicle drive four wheeler"),
    (("royal enfield", "ather"), "motorcycle two wheeler ride"),
    (
        ("chettinad", "vidyashram", "school", "class 2", "class 4", "studying"),
        "school attend study education பள்ளி படிக்கிறாள்",
    ),
    (("farmlink", "atlas", "side project", "lead at work"), "project app lead build"),
    (
        (
            "postgres",
            "postgresql",
            "firebase",
            "sqlite",
            "mysql",
            "mongodb",
            "next.js",
            "fastapi",
            "react",
            "flutter",
        ),
        "tech stack database db framework tool use",
    ),
    (
        ("eks", "aws", "gcp", "cloud run", "hetzner", "vercel", "deployed"),
        "run cloud host infrastructure where",
    ),
    (("dark mode", "dark theme", "light mode", "theme"), "theme app appearance preference like"),
    (
        ("dairy", "peanut", "prawn", "shellfish", "mushroom", "allergic", "allergy"),
        "allergy cannot take diet அலர்ஜி",
    ),
    (
        (
            "dosa",
            "idli",
            "pongal",
            "biryani",
            "paneer",
            "sambar",
            "rasam",
            "filter coffee",
            "coffee",
            "cook",
        ),
        "cook dish love taste தோசை",
    ),
    (
        ("diabet", "sugar", "bp", "blood pressure", "migraine", "asthma", "medicine", "metformin"),
        "health issue condition medicine take",
    ),
    (
        ("sony a7", "fujifilm", "canon", "nikon", "camera", "lens", "photography"),
        "camera photography hobby shoot",
    ),
    (
        ("swimming", "cricket", "violin", "carnatic", "music", "yoga", "ymca"),
        "class hobby activity play where when",
    ),
    (
        ("sip", "mutual fund", "nifty", "index fund", "₹", "rs.", "per month"),
        "sip investment monthly amount money",
    ),
    (("वाडகை", "வாடகை", "maintenance", "landlord"), "monthly"),
    (("birthday",), "birthday born age date பிறந்தநாள்"),
    (("anniversary", "married", "wedding"), "wedding anniversary married date"),
    (("o positive", "o+", "b+", "a+", "ab+", "blood group"), "blood group type"),
)

# Kinship & bilingual alias graph rules (Stage 4+). Keys and values come from the
# tuning split's family (Priya, Anu, Vicky, Divya, ...) plus general words.
ALIAS_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "wife": ("priyadharshini", "priya", "மனைவி", "cook"),
    "priyadharshini": ("priya", "wife", "மனைவி"),
    "priya": ("priyadharshini", "wife", "மனைவி"),
    "mother": ("amma", "mom", "lakshmi"),
    "amma": ("mother", "mom", "lakshmi"),
    "lakshmi": ("mother", "amma"),
    "father": ("appa", "dad", "rajan", "sundaram"),
    "appa": ("father", "dad", "rajan", "sundaram"),
    "daughter": ("anushka", "anu", "மகள்", "அனுஷ்கா", "அனு"),
    "anushka": ("anu", "daughter", "மகள்"),
    "anu": ("anushka", "daughter", "மகள்"),
    "son": ("vignesh", "vicky", "மகன்", "இளன்", "விக்னேஷ்"),
    "vignesh": ("vicky", "son", "மகன்"),
    "vicky": ("vignesh", "son", "மகன்"),
    "sister": ("divya", "thangachi", "அக்கா", "தங்கச்சி"),
    "divya": ("sister", "rajesh", "aadhav"),
    "brother": ("arjun", "karthik", "anna", "thambi", "அண்ணா", "தம்பி"),
    "anna": ("brother", "arjun", "karthik"),
    "rajesh": ("brother-in-law", "divya", "doctor", "aadhav"),
    "meera": ("anni", "brother", "wife", "karthik"),
    "aadhav": ("nephew", "divya", "rajesh", "son"),
    "nephew": ("aadhav", "divya", "rajesh"),
    "farmlink": ("side", "project", "postgres", "firebase", "next"),
    "atlas": ("lead", "work", "project", "eks", "aws", "tessera"),
    "இப்போது": ("now", "current", "moved", "live", "work"),
    "எங்கே": ("where", "live", "location", "city", "adyar", "chennai", "coimbatore"),
    "வசிக்கிறேன்": ("live", "residence", "adyar", "chennai", "coimbatore"),
    "மகள்": ("daughter", "anushka", "anu"),
    "மகன்": ("son", "vignesh", "vicky", "இளன்"),
    "பள்ளியில்": ("school", "chettinad", "vidyashram", "class"),
    "படிக்கிறாள்": ("school", "study", "attend", "class", "chettinad"),
    "நிறுவனத்தில்": ("company", "work", "tessera"),
    "வேலை": ("work", "company", "job", "tessera"),
    "மனைவி": ("wife", "priyadharshini", "priya"),
    "கார்": ("car", "creta", "i20", "hyundai"),
    "பைக்": ("royal enfield",),
    "போன்": ("phone", "pixel", "iphone"),
    "பிறந்தநாள்": ("birthday", "born"),
}

#: Question words that ask about the past (Stage 5). Plain phrases, joined into
#: one word-bounded regex below.
PAST_CUES: tuple[str, ...] = (
    "before",
    "previously",
    "earlier",
    "used to",
    "old",
    "first",
    "at first",
    "previous",
    "prior",
    "former",
    "initially",
    "when i was in",
    "in madurai",
    "in coimbatore",
)
#: Question words that ask about the present (Stage 5). Each entry is a regex
#: fragment; only `which .* do` uses regex syntax.
CURRENT_CUES: tuple[str, ...] = (
    "now",
    "current",
    "currently",
    "present",
    "today",
    "latest",
    "these days",
    "do i",
    "does my",
    "does he",
    "does she",
    "is my",
    "what is",
    "where do",
    "which .* do",
    "how much is",
    "இப்போது",
)

PAST_CUE_RE = re.compile(r"\b(" + "|".join(PAST_CUES) + r")\b", re.IGNORECASE)
CURRENT_CUE_RE = re.compile(r"\b(" + "|".join(CURRENT_CUES) + r")\b", re.IGNORECASE)


@dataclass
class EnrichedMemory:
    id: str
    msg_date: date
    raw_text: str
    rendered_text: str
    graph_text: str
    raw_tokens: list[str]
    rendered_tokens: list[str]
    graph_tokens: list[str]
    char_ngrams: Counter[str]
    entities: frozenset[str]
    topic_slots: frozenset[str]
    superseded_slots: frozenset[str] = field(default_factory=frozenset)


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[\w\u0B80-\u0BFF]+(?:[-+&][\w\u0B80-\u0BFF]+)*", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _char_ngrams(text: str, n: int = 3) -> Counter[str]:
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    if len(cleaned) < n:
        return Counter({cleaned: 1}) if cleaned else Counter()
    return Counter(cleaned[i : i + n] for i in range(len(cleaned) - n + 1))


def _cosine(c1: Counter[str], c2: Counter[str]) -> float:
    if not c1 or not c2:
        return 0.0
    common = set(c1) & set(c2)
    if not common:
        return 0.0
    num = sum(c1[k] * c2[k] for k in common)
    den = math.sqrt(sum(v * v for v in c1.values())) * math.sqrt(sum(v * v for v in c2.values()))
    return num / den if den > 0 else 0.0


#: Topic slots for correction supersession (Stage 5): a message belongs to
#: `slot` when it contains any `any_of` phrase and, if `also_any_of` is not
#: empty, also one of those. A later message in the same slot supersedes it.
SLOT_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("residence", ("live in", "moved to", "shifted to", "staying in"), ()),
    ("owner_phone", ("my phone", "bought a pixel", "upgraded my phone"), ()),
    ("family_car", ("our i20", "hyundai creta", "bought a creta", "drive a"), ()),
    ("employment", ("first day at", "work at", "joined tessera"), ()),
    ("job_title", ("engineering manager", "promoted to", "tech lead"), ()),
    ("farmlink_stack", ("farmlink",), ("firebase", "postgres", "next.js", "react")),
    ("sip_amount", ("sip",), ("10,000", "12,000", "15,000", "increased", "bumped", "raised")),
    (
        "child_school",
        ("chettinad", "little flower", "joined class", "started class", "studies in"),
        (),
    ),
    ("hobby_camera", ("sony a7", "fujifilm", "canon", "camera"), ()),
)


def _detect_slots(text: str) -> set[str]:
    t = text.lower()
    return {
        slot
        for slot, any_of, also_any_of in SLOT_RULES
        if any(w in t for w in any_of) and (not also_any_of or any(w in t for w in also_any_of))
    }


#: In-law and extended-family facets (Stage 4+). A message gets `label` when
#: every phrase of any one trigger group appears in it.
RELATION_FACETS: tuple[tuple[tuple[tuple[str, ...], ...], str], ...] = (
    ((("brother-in-law",), ("rajesh",)), "brother-in-law sister"),
    ((("anni",), ("meera",)), "brother wife anni sister-in-law"),
    ((("nephew",), ("aadhav",)), "nephew sister son"),
)


def _build_facets(raw_text: str) -> str:
    tl = raw_text.lower()
    facets: list[str] = []
    for triggers, label in FACET_TRIGGERS:
        if any(tr in tl for tr in triggers):
            facets.append(label)
    for groups, label in RELATION_FACETS:
        if any(all(w in tl for w in group) for group in groups):
            facets.append(label)
    return " ".join(facets)


def _extract_entities(text: str) -> set[str]:
    entities: set[str] = set()
    for m in re.finditer(r"\b[A-Z][a-zA-Z0-9&]{2,}\b", text):
        w = m.group(0).lower()
        if w not in STOPWORDS:
            entities.add(w)
    toks = set(_tokenize(text))
    for key, syns in ALIAS_EXPANSIONS.items():
        if key in toks:
            entities.add(key)
            entities.update(syns)
    return entities


def lab_rule_strings() -> list[str]:
    """Every string the stage 4-5 rules match on or add, for the leakage test.

    Facet triggers and labels, alias keys and values, slot phrases, relation
    triggers and labels, question expansions, and the past/current cues (with
    their regex `.*` split off). The test checks each string and each of its
    words against the two datasets.
    """
    out: list[str] = []
    for triggers, label in FACET_TRIGGERS:
        out.extend((*triggers, label))
    for key, syns in ALIAS_EXPANSIONS.items():
        out.extend((key, *syns))
    for _slot, any_of, also_any_of in SLOT_RULES:
        out.extend((*any_of, *also_any_of))
    for groups, label in RELATION_FACETS:
        for group in groups:
            out.extend(group)
        out.append(label)
    for triggers, words in QUESTION_EXPANSIONS:
        out.extend((*triggers, *words))
    for cue in (*PAST_CUES, *CURRENT_CUES):
        out.extend(part.strip() for part in cue.split(".*") if part.strip())
    return out


def build_corpus(data: dict[str, Any]) -> list[EnrichedMemory]:
    messages = data["messages"]
    memories: list[EnrichedMemory] = []

    # Each memory is rendered as its date plus its own words. Until 2026-11
    # this also added notes written for single held-out messages ("months after
    # joining Thenral", "Nila loves math", a birth-year age); they are gone.
    for m in messages:
        d = date.fromisoformat(m["date"])
        raw = m["text"]
        date_label = (
            f"{d.isoformat()} ({d.strftime('%-d %B %Y')}, {d.strftime('%B %-d')}, "
            f"{d.strftime('%-d %b')}, {d.strftime('%b %-d')})"
        )
        rendered = f"[{date_label}] {raw}"
        facets = _build_facets(raw)
        graph_text = f"{rendered} {facets}".strip()

        memories.append(
            EnrichedMemory(
                id=m["id"],
                msg_date=d,
                raw_text=raw,
                rendered_text=rendered,
                graph_text=graph_text,
                raw_tokens=_tokenize(raw),
                rendered_tokens=_tokenize(rendered),
                graph_tokens=_tokenize(graph_text),
                char_ngrams=_char_ngrams(rendered),
                entities=frozenset(_extract_entities(graph_text)),
                topic_slots=frozenset(_detect_slots(raw)),
            )
        )

    latest_by_slot: dict[str, date] = {}
    for mem in memories:
        for slot in mem.topic_slots:
            if slot not in latest_by_slot or mem.msg_date > latest_by_slot[slot]:
                latest_by_slot[slot] = mem.msg_date

    for i, mem in enumerate(memories):
        sup = {s for s in mem.topic_slots if latest_by_slot.get(s, mem.msg_date) > mem.msg_date}
        if sup:
            memories[i] = EnrichedMemory(
                id=mem.id,
                msg_date=mem.msg_date,
                raw_text=mem.raw_text,
                rendered_text=mem.rendered_text,
                graph_text=mem.graph_text,
                raw_tokens=mem.raw_tokens,
                rendered_tokens=mem.rendered_tokens,
                graph_tokens=mem.graph_tokens,
                char_ngrams=mem.char_ngrams,
                entities=mem.entities,
                topic_slots=mem.topic_slots,
                superseded_slots=frozenset(sup),
            )
    return memories


def _bm25_from_token_lists(
    query_tokens: list[str],
    doc_tok_lists: list[list[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    n_docs = len(doc_tok_lists)
    if n_docs == 0 or not query_tokens:
        return [0.0] * n_docs
    avgdl = sum(len(dl) for dl in doc_tok_lists) / max(1, n_docs)
    df: Counter[str] = Counter()
    for dl in doc_tok_lists:
        for w in set(dl):
            df[w] += 1

    scores: list[float] = []
    for dl in doc_tok_lists:
        tf = Counter(dl)
        dl_len = len(dl)
        s = 0.0
        for q in query_tokens:
            if tf[q] == 0:
                continue
            idf = math.log(1.0 + (n_docs - df[q] + 0.5) / (df[q] + 0.5))
            denom = tf[q] + k1 * (1.0 - b + b * (dl_len / max(1.0, avgdl)))
            s += idf * ((tf[q] * (k1 + 1.0)) / denom)
        scores.append(s)
    return scores


#: Question phrases that add search words (Stage 4+): when the question
#: contains any phrase of the first tuple, the words of the second are added.
QUESTION_EXPANSIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("brother-in-law",), ("rajesh", "divya", "doctor")),
    (("sister-in-law",), ("meera", "anni")),
    (("side project",), ("farmlink", "next", "postgres", "firebase")),
    (("lead at work",), ("atlas", "eks", "aws")),
    (("cannot take",), ("allergy", "allergic", "prawn", "peanut")),
)


def _expand_alias_tokens(question: str, base_tokens: list[str]) -> list[str]:
    ql = question.lower()
    extra: list[str] = []
    for phrases, words in QUESTION_EXPANSIONS:
        if any(p in ql for p in phrases):
            extra.extend(words)

    for tok in base_tokens:
        for syn in ALIAS_EXPANSIONS.get(tok, ()):
            for st in _tokenize(syn):
                if st not in base_tokens and st not in extra:
                    extra.append(st)
    return extra


def _as_evidence_memory(mem: EnrichedMemory) -> SimpleNamespace:
    """A benchmark memory shaped like the row `assess_hit_evidence` sees in production.

    The provenance is the most favourable one a real row can carry — the owner's own
    words (`trust_tier="self"` → evidence kind `said`), stored verbatim, never
    expired — so the only component of the calibrated confidence that varies across
    the corpus is freshness, measured from the message's own date.
    """
    recorded = datetime(mem.msg_date.year, mem.msg_date.month, mem.msg_date.day, 12, tzinfo=UTC)
    return SimpleNamespace(
        id=mem.id,
        content=mem.raw_text,
        summary=None,
        properties={"kind": "fact", "source_excerpt": mem.raw_text},
        confidence=CAPTURE_EXTRACTION_CONFIDENCE,
        trust_tier="self",
        source_type="chat",
        status="active",
        recorded_at=recorded,
        created_at=recorded,
        updated_at=recorded,
        valid_to=None,
    )


def assess_corpus_hit(
    question: str,
    mem: EnrichedMemory,
    *,
    today: date,
    confidence_floor: float = EARLY_EXIT_CONFIDENCE,
) -> dict[str, Any]:
    """The production early-exit verdict for one corpus hit.

    Delegates to `assess_hit_evidence` so the benchmark measures the shipped gate
    rather than a copy of it. `confidence_floor` only re-derives `sufficient` from
    the components the assessment already returned; the entailment rule is untouched,
    which is what lets the sensitivity sweep move one threshold at a time.
    """
    now = datetime(today.year, today.month, today.day, 12, tzinfo=UTC)
    evidence = assess_hit_evidence(question, _as_evidence_memory(mem), now=now)
    if confidence_floor != EARLY_EXIT_CONFIDENCE:
        entailed = evidence["support_status"] == SUPPORTED and (
            evidence["keywords_covered"] or evidence["entailment_score"] >= EARLY_EXIT_ENTAILMENT
        )
        evidence["sufficient"] = bool(
            evidence["calibrated_confidence"] >= confidence_floor and entailed
        )
    evidence["confidence_floor"] = confidence_floor
    return evidence


def retrieve_for_method(
    question: dict[str, Any],
    corpus: list[EnrichedMemory],
    method: str,
    *,
    top_k: int = 5,
    rrf_k: int = 20,
    early_exit_mode: str = EARLY_EXIT_OFF,
    today: date | None = None,
    confidence_floor: float = EARLY_EXIT_CONFIDENCE,
    trace: dict[str, Any] | None = None,
) -> tuple[list[EnrichedMemory], bool]:
    """Return `(top_k_memories, abstained)` for a single question and method.

    With `early_exit_mode` left at its default `off` this is the original ladder,
    unchanged and unmeasured. `measure` and `on` additionally consult the adaptive
    early-exit gate on the hybrid stage's top hit (see `EARLY_EXIT_MODES`); `on`
    acts on it, skipping graph/alias expansion and the multi-step bridge. `trace`,
    when given, receives the gate's verdict for the caller to aggregate.
    """
    q_text = question["q"]
    q_kind = question.get("kind", "simple")
    base_tokens = _tokenize(q_text)

    if method == "1_lexical_bm25":
        bm25 = _bm25_from_token_lists(base_tokens, [m.raw_tokens for m in corpus])
        ranked = sorted(range(len(corpus)), key=lambda i: (-bm25[i], i))
        return [corpus[i] for i in ranked[:top_k]], False

    if method == "2_vector_ngram":
        q_ng = _char_ngrams(q_text)
        vec = [_cosine(q_ng, m.char_ngrams) for m in corpus]
        ranked = sorted(range(len(corpus)), key=lambda i: (-vec[i], i))
        return [corpus[i] for i in ranked[:top_k]], False

    # Stage 3+: Hybrid RRF over rendered tokens + character n-grams
    bm25_base = _bm25_from_token_lists(base_tokens, [m.rendered_tokens for m in corpus])
    q_ng = _char_ngrams(q_text)
    vec = [_cosine(q_ng, m.char_ngrams) for m in corpus]

    bm25_order = sorted(range(len(corpus)), key=lambda i: (-bm25_base[i], i))
    vec_order = sorted(range(len(corpus)), key=lambda i: (-vec[i], i))
    bm25_rank = {idx: r + 1 for r, idx in enumerate(bm25_order)}
    vec_rank = {idx: r + 1 for r, idx in enumerate(vec_order)}

    combined = [
        (1.0 / (rrf_k + bm25_rank[i]))
        + (1.0 / (rrf_k + vec_rank[i]))
        + 0.15 * bm25_base[i]
        + 0.35 * vec[i]
        for i in range(len(corpus))
    ]

    if method == "3_hybrid_rrf":
        ranked = sorted(range(len(corpus)), key=lambda i: (-combined[i], i))
        return [corpus[i] for i in ranked[:top_k]], False

    # §3.C adaptive early exit. The hybrid ranking above is this benchmark's analogue
    # of the production hybrid search, so the gate reads the same thing it reads in
    # services/memory/retrieval.py: the top hit's own calibrated confidence and
    # entailment, not its search score. When they already account for the question,
    # the expansions below can only add distractors and latency.
    exited_early = False
    if early_exit_mode != EARLY_EXIT_OFF:
        if today is None:
            raise ValueError("early_exit_mode requires `today` (the dataset's reference date)")
        hybrid_top = min(range(len(corpus)), key=lambda i: (-combined[i], i)) if corpus else None
        evidence = (
            assess_corpus_hit(
                q_text, corpus[hybrid_top], today=today, confidence_floor=confidence_floor
            )
            if hybrid_top is not None
            else None
        )
        sufficient = bool(evidence and evidence["sufficient"])
        exited_early = sufficient and early_exit_mode == EARLY_EXIT_ON
        if trace is not None:
            trace["evidence"] = evidence
            trace["sufficient"] = sufficient
            trace["early_exit"] = exited_early

    # Stage 4+: Graph entity/alias expansion + semantic facet matching
    if exited_early:
        graph_query = base_tokens
    else:
        alias_tokens = _expand_alias_tokens(q_text, base_tokens)
        graph_query = base_tokens + alias_tokens
        bm25_graph = _bm25_from_token_lists(graph_query, [m.graph_tokens for m in corpus])
        bm25_alias_only = (
            _bm25_from_token_lists(alias_tokens, [m.graph_tokens for m in corpus])
            if alias_tokens
            else [0.0] * len(corpus)
        )

        for i in range(len(corpus)):
            combined[i] += 0.12 * bm25_graph[i] + 0.10 * bm25_alias_only[i]

    if method == "4_graph_entity_expansion":
        ranked = sorted(range(len(corpus)), key=lambda i: (-combined[i], i))
        return [corpus[i] for i in ranked[:top_k]], False

    # Stage 5+: Temporal supersession & provenance reranking
    is_past = q_kind in ("past", "old_fact") or bool(PAST_CUE_RE.search(q_text))
    is_current = (q_kind == "current" or bool(CURRENT_CUE_RE.search(q_text))) and not is_past

    for i, mem in enumerate(corpus):
        if q_kind == "current":
            days_ord = (mem.msg_date - date(2025, 1, 1)).days / 700.0
            combined[i] += 0.15 * max(0.0, min(1.0, days_ord))
            if mem.superseded_slots:
                combined[i] -= 0.85
            elif mem.topic_slots:
                combined[i] += 0.35
        elif is_current:
            days_ord = (mem.msg_date - date(2025, 1, 1)).days / 700.0
            combined[i] += 0.06 * max(0.0, min(1.0, days_ord))
            if mem.superseded_slots:
                combined[i] -= 0.10
        elif is_past:
            if mem.superseded_slots:
                combined[i] += 0.65

    if method == "5_rerank_temporal_provenance":
        ranked = sorted(range(len(corpus)), key=lambda i: (-combined[i], i))
        return [corpus[i] for i in ranked[:top_k]], False

    # Stage 6: Multi-step bridge retrieval. It never abstains: see the module
    # docstring and `abstention_probe()` for how abstention is measured.
    ranked = sorted(range(len(corpus)), key=lambda i: (-combined[i], i))
    # Multi-step bridge: preserve top-3 primary hits and promote complementary 2nd-hop entity memories into ranks 4..top_k
    if len(ranked) > 3 and q_kind in ("multi_hop", "about", "connected") and not exited_early:
        bridge_ents: list[str] = []
        for idx in ranked[:2]:
            for ent in sorted(corpus[idx].entities):
                if ent not in graph_query and len(ent) >= 3 and ent not in bridge_ents:
                    bridge_ents.append(ent)
        if bridge_ents:
            hop2_bm25 = _bm25_from_token_lists(
                base_tokens + bridge_ents[:6], [m.graph_tokens for m in corpus]
            )
            top_fixed = ranked[:3]
            rest = sorted(ranked[3:], key=lambda i: (-(combined[i] + 0.08 * hop2_bm25[i]), i))
            ranked = top_fixed + rest

    return [corpus[i] for i in ranked[:top_k]], False


def _memory_matches_group(mem: EnrichedMemory, group: list[str]) -> bool:
    text_l = mem.rendered_text.lower()
    return any(alt.lower() in text_l for alt in group)


def score_question(
    question: dict[str, Any],
    retrieved: list[EnrichedMemory],
    abstained: bool,
) -> dict[str, Any]:
    """Score a single question for Recall@1, Recall@3, Recall@5, MRR, NDCG@5, and support."""
    is_abstain_gold = bool(question.get("abstain"))
    if is_abstain_gold:
        correct_abstain = abstained or len(retrieved) == 0
        return {
            "id": question["id"],
            "kind": question.get("kind", "abstain"),
            "is_abstain": True,
            "abstained": abstained,
            "abstain_correct": correct_abstain,
            "hit_at_1": 1.0 if correct_abstain else 0.0,
            "hit_at_3": 1.0 if correct_abstain else 0.0,
            "hit_at_5": 1.0 if correct_abstain else 0.0,
            "mrr": 1.0 if correct_abstain else 0.0,
            "ndcg_at_5": 1.0 if correct_abstain else 0.0,
            "full_support_at_5": 1.0 if correct_abstain else 0.0,
            "supersession_clean": True,
        }

    must_groups: list[list[str]] = question.get("must") or []
    must_not: list[str] = [x.lower() for x in (question.get("must_not") or [])]

    if abstained or not retrieved:
        return {
            "id": question["id"],
            "kind": question.get("kind", "simple"),
            "is_abstain": False,
            "abstained": abstained,
            "abstain_correct": False,
            "hit_at_1": 0.0,
            "hit_at_3": 0.0,
            "hit_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "full_support_at_5": 0.0,
            "supersession_clean": False,
        }

    rels: list[float] = []
    for mem in retrieved[:5]:
        matched_groups = sum(1 for g in must_groups if _memory_matches_group(mem, g))
        has_trap = any(bad in mem.raw_text.lower() for bad in must_not) if must_not else False
        if matched_groups > 0 and not has_trap:
            rels.append(matched_groups / max(1, len(must_groups)))
        elif matched_groups > 0 and has_trap:
            rels.append(0.25 * (matched_groups / max(1, len(must_groups))))
        else:
            rels.append(0.0)

    first_hit_rank: int | None = None
    for idx, r in enumerate(rels):
        if r > 0.0:
            first_hit_rank = idx + 1
            break

    hit_1 = 1.0 if (first_hit_rank is not None and first_hit_rank <= 1) else 0.0
    hit_3 = 1.0 if (first_hit_rank is not None and first_hit_rank <= 3) else 0.0
    hit_5 = 1.0 if (first_hit_rank is not None and first_hit_rank <= 5) else 0.0
    mrr = (1.0 / first_hit_rank) if first_hit_rank is not None else 0.0

    dcg = sum((2.0**r - 1.0) / math.log2(idx + 2) for idx, r in enumerate(rels))
    ideal = sorted(rels, reverse=True)
    idcg = sum((2.0**r - 1.0) / math.log2(idx + 2) for idx, r in enumerate(ideal))
    ndcg_5 = (dcg / idcg) if idcg > 0 else hit_5

    combined_top5 = " \n ".join(m.rendered_text.lower() for m in retrieved[:5])
    all_groups_met = all(any(alt.lower() in combined_top5 for alt in grp) for grp in must_groups)
    top1_clean = not any(bad in retrieved[0].raw_text.lower() for bad in must_not) and not (
        question.get("kind") == "current" and bool(retrieved[0].superseded_slots)
    )
    full_support = 1.0 if (all_groups_met and top1_clean) else 0.0

    return {
        "id": question["id"],
        "kind": question.get("kind", "simple"),
        "is_abstain": False,
        "abstained": False,
        "abstain_correct": True,
        "hit_at_1": hit_1,
        "hit_at_3": hit_3,
        "hit_at_5": hit_5,
        "mrr": mrr,
        "ndcg_at_5": ndcg_5,
        "full_support_at_5": full_support,
        "supersession_clean": top1_clean,
    }


def evaluate_lifecycle_invariants() -> dict[str, Any]:
    """Deterministic checks for bitemporal validity, forgetting/deletion isolation, and provenance."""
    june_14_v1 = SimpleNamespace(
        id="ep_v1",
        status="superseded",
        properties={
            "kind": "episode",
            "date": "2025-06-14",
            "recorded_at": "2025-06-15T08:00:00Z",
            "superseded_at": "2025-06-18T09:00:00Z",
        },
    )
    june_14_late = SimpleNamespace(
        id="ep_late",
        status="active",
        properties={
            "kind": "episode",
            "date": "2025-06-14",
            "recorded_at": "2025-06-20T10:00:00Z",
        },
    )
    as_of = datetime(2025, 6, 15, 12, 0, tzinfo=UTC)
    valid_june_16 = [
        m
        for m in (june_14_v1, june_14_late)
        if is_bitemporally_valid(m, valid_at=as_of, recorded_at=datetime(2025, 6, 16, tzinfo=UTC))
    ]
    valid_june_21 = [
        m
        for m in (june_14_v1, june_14_late)
        if is_bitemporally_valid(m, valid_at=as_of, recorded_at=datetime(2025, 6, 21, tzinfo=UTC))
    ]
    bitemporal_ok = (
        [m.id for m in valid_june_16] == ["ep_v1"]
        and [m.id for m in valid_june_21] == ["ep_late"]
        and time_window("What happened last year?", date(2025, 6, 15))
        == (date(2024, 1, 1), date(2024, 12, 31))
    )

    pool = [
        SimpleNamespace(
            id="m_active", status="active", created_at=datetime(2026, 11, 1, tzinfo=UTC)
        ),
        SimpleNamespace(
            id="m_deleted", status="deleted", created_at=datetime(2026, 11, 1, tzinfo=UTC)
        ),
        SimpleNamespace(
            id="m_rejected", status="rejected", created_at=datetime(2026, 11, 1, tzinfo=UTC)
        ),
        SimpleNamespace(
            id="m_pre_fresh_start", status="active", created_at=datetime(2026, 10, 1, tzinfo=UTC)
        ),
    ]
    fresh_start = datetime(2026, 10, 23, tzinfo=UTC)
    visible = [m for m in pool if m.status == "active" and m.created_at >= fresh_start]
    leaked = [m.id for m in visible if m.id != "m_active"]

    contradicting_memories = [
        {
            "id": "1",
            "content": "The owner is allergic to peanuts and shellfish.",
            "source_type": "user_explicit",
            "trust_tier": "self",
            "created_at": datetime(2026, 10, 1, tzinfo=UTC),
            "properties": {},
        },
        {
            "id": "2",
            "content": "The owner is not allergic to peanuts and shellfish.",
            "source_type": "user_explicit",
            "trust_tier": "self",
            "created_at": datetime(2026, 10, 2, tzinfo=UTC),
            "properties": {},
        },
    ]
    ev = extract_claim_evidence(
        "The owner is allergic to peanuts and shellfish [Memory 1] [Memory 2].",
        contradicting_memories,
        now=datetime(2026, 11, 1, tzinfo=UTC),
    )
    provenance_ok = (
        bool(ev)
        and ev[0]["support_status"] == CONTRADICTED
        and ev[0]["recommended_action"] == ABSTAIN
    )

    return {
        "bitemporal_accuracy": 1.0 if bitemporal_ok else 0.0,
        "forgetting_leakage_rate": len(leaked) / max(1, len(pool) - 1),
        "forgetting_clean": len(leaked) == 0,
        "provenance_contradiction_gate_ok": provenance_ok,
    }


def _percentile(sorted_samples: list[float], fraction: float) -> float:
    """The benchmark's long-standing percentile convention, kept exactly as it was."""
    if not sorted_samples:
        return 0.0
    if fraction >= 1.0:
        return sorted_samples[-1]
    if fraction == 0.5:
        return sorted_samples[len(sorted_samples) // 2]
    return sorted_samples[min(len(sorted_samples) - 1, int(len(sorted_samples) * fraction))]


def latency_stats(samples: list[float]) -> dict[str, float]:
    """Mean/p50/p95/min/max over per-question latencies, in milliseconds."""
    if not samples:
        return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        "mean": round(sum(ordered) / len(ordered), 3),
        "p50": round(_percentile(ordered, 0.5), 3),
        "p95": round(_percentile(ordered, 0.95), 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
    }


def summarize_scores(
    scored: list[dict[str, Any]],
    latencies_ms: list[float],
) -> dict[str, Any]:
    """The `overall` / `by_kind` / `sample_failures` report for one scored run."""
    answerable = [s for s in scored if not s["is_abstain"]]
    abstain_qs = [s for s in scored if s["is_abstain"]]
    temporal_qs = [s for s in scored if s["kind"] in ("current", "past", "old_fact")]
    current_qs = [s for s in scored if s["kind"] == "current"]

    pred_abstain = [s for s in scored if s["abstained"]]
    tp_abstain = sum(1 for s in pred_abstain if s["is_abstain"])
    abstain_prec = (
        tp_abstain / len(pred_abstain) if pred_abstain else (1.0 if not abstain_qs else 0.0)
    )
    abstain_rec = tp_abstain / max(1, len(abstain_qs))

    by_kind: dict[str, dict[str, float]] = {}
    kinds = sorted({s["kind"] for s in scored})
    for k in kinds:
        sub = [s for s in scored if s["kind"] == k]
        by_kind[k] = {
            "count": len(sub),
            "recall_at_1": round(sum(s["hit_at_1"] for s in sub) / len(sub), 4),
            "recall_at_5": round(sum(s["hit_at_5"] for s in sub) / len(sub), 4),
            "mrr": round(sum(s["mrr"] for s in sub) / len(sub), 4),
            "full_support_at_5": round(sum(s["full_support_at_5"] for s in sub) / len(sub), 4),
        }

    lat_sorted = sorted(latencies_ms)
    p50 = _percentile(lat_sorted, 0.5)
    p95 = _percentile(lat_sorted, 0.95)

    failures = [{"id": s["id"], "kind": s["kind"]} for s in scored if s["full_support_at_5"] < 1.0][
        :10
    ]

    return {
        "overall": {
            "total_questions": len(scored),
            "answerable_questions": len(answerable),
            "abstain_questions": len(abstain_qs),
            "recall_at_1": round(
                sum(s["hit_at_1"] for s in answerable) / max(1, len(answerable)), 4
            ),
            "recall_at_3": round(
                sum(s["hit_at_3"] for s in answerable) / max(1, len(answerable)), 4
            ),
            "recall_at_5": round(
                sum(s["hit_at_5"] for s in answerable) / max(1, len(answerable)), 4
            ),
            "mrr": round(sum(s["mrr"] for s in answerable) / max(1, len(answerable)), 4),
            "ndcg_at_5": round(
                sum(s["ndcg_at_5"] for s in answerable) / max(1, len(answerable)), 4
            ),
            "full_support_at_5": round(
                sum(s["full_support_at_5"] for s in scored) / max(1, len(scored)), 4
            ),
            "temporal_accuracy": round(
                sum(s["full_support_at_5"] for s in temporal_qs) / max(1, len(temporal_qs)), 4
            ),
            "correction_supersession_rate": round(
                sum(1.0 for s in current_qs if s["supersession_clean"]) / max(1, len(current_qs)),
                4,
            ),
            "abstention_precision": round(abstain_prec, 4),
            "abstention_recall": round(abstain_rec, 4),
            "latency_ms_p50": round(p50, 3),
            "latency_ms_p95": round(p95, 3),
        },
        "by_kind": by_kind,
        "sample_failures": failures,
    }


def evaluate_split(
    split_name: str,
    dataset_path: Path,
    methods: tuple[str, ...] = BENCHMARK_METHODS,
) -> dict[str, Any]:
    raw_bytes = dataset_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    data = json.loads(raw_bytes.decode("utf-8"))
    corpus = build_corpus(data)
    questions = data["questions"]

    method_reports: dict[str, Any] = {}
    for method in methods:
        latencies_ms: list[float] = []
        scored: list[dict[str, Any]] = []
        for q in questions:
            t0 = time.perf_counter()
            retrieved, abstained = retrieve_for_method(q, corpus, method)
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            scored.append(score_question(q, retrieved, abstained))
        method_reports[method] = summarize_scores(scored, latencies_ms)

    return {
        "split": split_name,
        "dataset_file": str(dataset_path.relative_to(ROOT)),
        "dataset_sha256": sha256,
        "person": data.get("person"),
        "today": data.get("today"),
        "message_count": len(corpus),
        "question_count": len(questions),
        "methods": method_reports,
    }


# --------------------------------------------------------------------------
# Adaptive early-exit comparison (Track 2)
# --------------------------------------------------------------------------

#: Labels for the two arms of the comparison, in report order.
BASELINE_ARM = "baseline"
ADAPTIVE_ARM = "adaptive_early_exit"

#: Quality metrics the comparison reports and gates on.
COMPARED_METRICS = (
    "recall_at_1",
    "recall_at_5",
    "mrr",
    "full_support_at_5",
    "abstention_precision",
    "abstention_recall",
)

#: Metrics that must not fall when the gate is switched on, and by how much they
#: are allowed to. Zero: skipping an expansion because the top hit already answers
#: the question is only sound if it costs no recall at all.
NO_REGRESSION_METRICS = ("recall_at_1", "recall_at_5", "mrr", "full_support_at_5")
REGRESSION_TOLERANCE = 0.0


def _run_early_exit_pass(
    questions: list[dict[str, Any]],
    corpus: list[EnrichedMemory],
    *,
    method: str,
    mode: str,
    today: date,
    confidence_floor: float,
) -> tuple[list[float], list[dict[str, Any]], list[dict[str, Any]]]:
    """One timed pass over every question: latencies, scores, and gate verdicts."""
    latencies_ms: list[float] = []
    scored: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for q in questions:
        trace: dict[str, Any] = {}
        t0 = time.perf_counter()
        retrieved, abstained = retrieve_for_method(
            q,
            corpus,
            method,
            early_exit_mode=mode,
            today=today,
            confidence_floor=confidence_floor,
            trace=trace,
        )
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        scored.append(score_question(q, retrieved, abstained))
        traces.append(trace)
    return latencies_ms, scored, traces


def _timed_arm(
    questions: list[dict[str, Any]],
    corpus: list[EnrichedMemory],
    *,
    method: str,
    mode: str,
    today: date,
    confidence_floor: float,
    passes: int,
) -> tuple[list[float], list[dict[str, Any]], list[dict[str, Any]]]:
    """`passes` identical passes, keeping each question's fastest observed latency.

    Retrieval is deterministic, so the scores and verdicts of every pass are the
    same and the last pass's are returned; only the timings differ, and the minimum
    is the one least inflated by whatever else the machine was doing.
    """
    best: list[float] | None = None
    scored: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for _ in range(max(1, passes)):
        latencies_ms, scored, traces = _run_early_exit_pass(
            questions,
            corpus,
            method=method,
            mode=mode,
            today=today,
            confidence_floor=confidence_floor,
        )
        best = (
            latencies_ms
            if best is None
            else [min(a, b) for a, b in zip(best, latencies_ms, strict=True)]
        )
    return best or [], scored, traces


def _early_exit_summary(
    traces: list[dict[str, Any]],
    *,
    acted: bool,
    confidence_floor: float,
) -> dict[str, Any]:
    """How many questions the gate fired on, and on which.

    `acted` separates the two arms: both consult the gate, but only the adaptive arm
    skips anything, so the baseline reports what it *would* have skipped (its exit
    rate is 0 by construction) and the adaptive arm reports what it did.
    """
    sufficient = [i for i, t in enumerate(traces) if t.get("sufficient")]
    exited = [i for i, t in enumerate(traces) if t.get("early_exit")]
    total = len(traces)
    return {
        "total_questions": total,
        "evidence_sufficient": len(sufficient),
        "early_exited": len(exited),
        "exit_rate_pct": round(100.0 * len(exited) / total, 2) if total else 0.0,
        "would_exit_rate_pct": round(100.0 * len(sufficient) / total, 2) if total else 0.0,
        "acted_on_gate": acted,
        "confidence_floor": confidence_floor,
        "entailment_floor": EARLY_EXIT_ENTAILMENT,
    }


def _relative_pct(baseline: float, adaptive: float) -> float | None:
    """Change from *baseline* to *adaptive* as a percentage, or None at a zero base."""
    if baseline == 0:
        return None
    return round(100.0 * (adaptive - baseline) / abs(baseline), 2)


def _arm_delta(
    base: dict[str, Any],
    adapt: dict[str, Any],
    *,
    base_lat: list[float],
    adapt_lat: list[float],
    exited: list[int],
) -> dict[str, Any]:
    """Baseline → adaptive movement, in quality and in latency."""
    quality: dict[str, Any] = {}
    for metric in COMPARED_METRICS:
        b = base["overall"][metric]
        a = adapt["overall"][metric]
        quality[metric] = {
            "baseline": b,
            "adaptive": a,
            "delta": round(a - b, 4),
            "relative_pct": _relative_pct(b, a),
        }

    latency: dict[str, Any] = {}
    for stat in ("mean", "p50", "p95"):
        b = base["latency_ms"][stat]
        a = adapt["latency_ms"][stat]
        latency[stat] = {
            "baseline_ms": b,
            "adaptive_ms": a,
            "delta_ms": round(a - b, 3),
            "relative_pct": _relative_pct(b, a),
        }

    # The paired measurement: the same questions, timed both ways. With a strict
    # gate the fleet-wide means barely move, so this is where the saving is visible.
    paired_base = [base_lat[i] for i in exited]
    paired_adapt = [adapt_lat[i] for i in exited]
    saved = [b - a for b, a in zip(paired_base, paired_adapt, strict=True)]
    on_exited = {
        "count": len(exited),
        "baseline": latency_stats(paired_base),
        "adaptive": latency_stats(paired_adapt),
        "mean_saving_ms": round(sum(saved) / len(saved), 3) if saved else 0.0,
        "mean_saving_pct": (
            round(100.0 * sum(saved) / sum(paired_base), 2) if sum(paired_base) > 0 else 0.0
        ),
    }
    return {"quality": quality, "latency": latency, "on_early_exited_questions": on_exited}


def _regression_gates(delta: dict[str, Any]) -> dict[str, Any]:
    """Whether switching the gate on cost any retrieval quality."""
    checks: dict[str, bool] = {}
    for metric in NO_REGRESSION_METRICS:
        checks[f"{metric}_no_regression"] = (
            delta["quality"][metric]["delta"] >= -REGRESSION_TOLERANCE
        )
    checks["abstention_precision_no_regression"] = (
        delta["quality"]["abstention_precision"]["delta"] >= -REGRESSION_TOLERANCE
    )
    checks["abstention_recall_no_regression"] = (
        delta["quality"]["abstention_recall"]["delta"] >= -REGRESSION_TOLERANCE
    )
    return {"checks": checks, "passed": all(checks.values())}


def evaluate_early_exit_split(
    split_name: str,
    dataset_path: Path,
    *,
    method: str = PRIMARY_METHOD,
    confidence_floor: float = EARLY_EXIT_CONFIDENCE,
    passes: int = LATENCY_PASSES,
) -> dict[str, Any]:
    """Run *method* over one split twice — gate off, then gate on — and compare.

    Both arms pay for assessing the top hit's evidence, exactly as production does,
    so the single variable between them is whether a sufficient verdict is acted on.
    """
    raw_bytes = dataset_path.read_bytes()
    data = json.loads(raw_bytes.decode("utf-8"))
    corpus = build_corpus(data)
    questions = data["questions"]
    today = date.fromisoformat(data.get("today", "2026-10-31"))

    arms: dict[str, Any] = {}
    latencies: dict[str, list[float]] = {}
    traces_by_arm: dict[str, list[dict[str, Any]]] = {}
    for label, mode in ((BASELINE_ARM, EARLY_EXIT_MEASURE), (ADAPTIVE_ARM, EARLY_EXIT_ON)):
        per_q, scored, traces = _timed_arm(
            questions,
            corpus,
            method=method,
            mode=mode,
            today=today,
            confidence_floor=confidence_floor,
            passes=passes,
        )
        report = summarize_scores(scored, per_q)
        report["latency_ms"] = latency_stats(per_q)
        report["early_exit"] = _early_exit_summary(
            traces, acted=mode == EARLY_EXIT_ON, confidence_floor=confidence_floor
        )
        arms[label] = report
        latencies[label] = per_q
        traces_by_arm[label] = traces

    exited = [i for i, t in enumerate(traces_by_arm[ADAPTIVE_ARM]) if t.get("early_exit")]
    delta = _arm_delta(
        arms[BASELINE_ARM],
        arms[ADAPTIVE_ARM],
        base_lat=latencies[BASELINE_ARM],
        adapt_lat=latencies[ADAPTIVE_ARM],
        exited=exited,
    )
    return {
        "split": split_name,
        "dataset_file": str(dataset_path.relative_to(ROOT)),
        "dataset_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "today": data.get("today"),
        "message_count": len(corpus),
        "question_count": len(questions),
        "method": method,
        "confidence_floor": confidence_floor,
        "entailment_floor": EARLY_EXIT_ENTAILMENT,
        "timing_passes": max(1, passes),
        "early_exited_question_ids": [questions[i]["id"] for i in exited],
        "arms": arms,
        "delta": delta,
        "gates": _regression_gates(delta),
    }


def sweep_confidence_floors(
    dataset_path: Path,
    *,
    method: str = PRIMARY_METHOD,
    floors: tuple[float, ...] = CONFIDENCE_FLOOR_SWEEP,
    passes: int = LATENCY_PASSES,
) -> list[dict[str, Any]]:
    """Exit rate, quality and latency as the calibrated-confidence floor is relaxed.

    The shipped floor is strict enough that it fires on only a handful of these
    questions, which tells us the gate is safe but almost nothing about the shape of
    the trade-off. Walking the floor down traces the curve the floor sits on.
    """
    data = json.loads(dataset_path.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    questions = data["questions"]
    today = date.fromisoformat(data.get("today", "2026-10-31"))

    rows: list[dict[str, Any]] = []
    for floor in floors:
        per_q, scored, traces = _timed_arm(
            questions,
            corpus,
            method=method,
            mode=EARLY_EXIT_ON,
            today=today,
            confidence_floor=floor,
            passes=passes,
        )
        summary = summarize_scores(scored, per_q)
        lat = latency_stats(per_q)
        exit_info = _early_exit_summary(traces, acted=True, confidence_floor=floor)
        rows.append(
            {
                "confidence_floor": floor,
                "early_exited": exit_info["early_exited"],
                "exit_rate_pct": exit_info["exit_rate_pct"],
                "recall_at_1": summary["overall"]["recall_at_1"],
                "recall_at_5": summary["overall"]["recall_at_5"],
                "mrr": summary["overall"]["mrr"],
                "full_support_at_5": summary["overall"]["full_support_at_5"],
                "latency_mean_ms": lat["mean"],
                "latency_p50_ms": lat["p50"],
                "latency_p95_ms": lat["p95"],
            }
        )
    return rows


def compare_adaptive_early_exit(
    *,
    method: str = PRIMARY_METHOD,
    passes: int = LATENCY_PASSES,
    sweep: bool = True,
) -> dict[str, Any]:
    """The full baseline-vs-adaptive-early-exit comparison over both splits."""
    splits = {
        "tuning_dev": evaluate_early_exit_split(
            "tuning_dev", TUNING_DATASET, method=method, passes=passes
        ),
        "held_out": evaluate_early_exit_split(
            "held_out", HELDOUT_DATASET, method=method, passes=passes
        ),
    }
    report: dict[str, Any] = {
        "benchmark": "life_graph_adaptive_early_exit_comparison_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "method": method,
        "timing_passes": max(1, passes),
        "thresholds": {
            "calibrated_confidence": EARLY_EXIT_CONFIDENCE,
            "entailment": EARLY_EXIT_ENTAILMENT,
            "extraction_confidence_assumed": CAPTURE_EXTRACTION_CONFIDENCE,
        },
        "splits": splits,
        "gates_passed": all(s["gates"]["passed"] for s in splits.values()),
    }
    if sweep:
        report["confidence_floor_sensitivity"] = {
            "tuning_dev": sweep_confidence_floors(TUNING_DATASET, method=method, passes=passes),
            "held_out": sweep_confidence_floors(HELDOUT_DATASET, method=method, passes=passes),
        }
    return report


# --------------------------------------------------------------------------
# Abstention probe: one general rule, chosen on the tuning split only
# --------------------------------------------------------------------------

#: Floors tried on the tuning split. The chosen one is applied unchanged to the
#: held-out split, which is what makes the held-out number honest.
ABSTENTION_FLOOR_GRID = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

#: The rule, in words, for the report.
ABSTENTION_RULE = (
    "abstain when no top-5 hit of the primary method accounts for at least `floor` "
    "of the question's content words (core.evidence.lexical_entailment_score); "
    "questions with no scorable English content words never abstain"
)


def abstention_signal(question: str, retrieved: list[EnrichedMemory]) -> float | None:
    """The best lexical entailment of *question* by any retrieved memory, 0-1.

    None when the question has no word the scorer can read (the scorer reads
    English letters and digits only, so an all-Tamil question scores 0 against
    everything). That is no evidence either way, so it never abstains.
    """
    if not re.search(r"[a-z0-9]", question.lower()):
        return None
    return max((lexical_entailment_score(question, m.raw_text) for m in retrieved), default=0.0)


def _abstention_scores(signals: list[tuple[bool, float | None]], floor: float) -> dict[str, Any]:
    """Precision/recall/F1 of abstaining below *floor*, and its cost on answerable questions."""
    gold = sum(1 for is_abstain, _ in signals if is_abstain)
    answerable = len(signals) - gold
    predicted = [(g, sig is not None and sig < floor) for g, sig in signals]
    tp = sum(1 for g, p in predicted if g and p)
    fp = sum(1 for g, p in predicted if p and not g)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "floor": floor,
        "abstained": tp + fp,
        "abstain_questions": gold,
        "true_abstentions": tp,
        "false_abstentions": fp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        # Answerable questions the rule would have refused: the price of the recall.
        "false_abstain_rate": round(fp / answerable, 4) if answerable else 0.0,
    }


def _split_signals(dataset_path: Path, method: str) -> list[tuple[bool, float | None]]:
    data = json.loads(dataset_path.read_bytes().decode("utf-8"))
    corpus = build_corpus(data)
    out: list[tuple[bool, float | None]] = []
    for q in data["questions"]:
        retrieved, _ = retrieve_for_method(q, corpus, method)
        out.append((bool(q.get("abstain")), abstention_signal(q["q"], retrieved)))
    return out


def abstention_probe(
    *,
    method: str = PRIMARY_METHOD,
    floors: tuple[float, ...] = ABSTENTION_FLOOR_GRID,
) -> dict[str, Any]:
    """How well one general evidence rule tells unanswerable questions apart.

    The floor with the best F1 on the tuning split is chosen (ties go to the
    lower floor, which refuses fewer answerable questions) and then applied
    unchanged to the held-out split. Nothing in the rule names a dataset's
    people, places or questions. It is reported, not gated: evals/score-
    separability.md showed that ranking scores do not separate answerable from
    unanswerable questions, and this probe measures the same for the lexical
    evidence the lab can compute. Production abstains through the local
    relevance judge, which this lab does not run.
    """
    tuning = _split_signals(TUNING_DATASET, method)
    held_out = _split_signals(HELDOUT_DATASET, method)
    sweep = [_abstention_scores(tuning, f) for f in floors]
    best = max(sweep, key=lambda r: (r["f1"], -r["floor"]))
    floor = best["floor"]
    return {
        "rule": ABSTENTION_RULE,
        "method": method,
        "floor": floor,
        "floor_chosen_on": "tuning_dev",
        "gated": False,
        "splits": {
            "tuning_dev": _abstention_scores(tuning, floor),
            "held_out": _abstention_scores(held_out, floor),
        },
        "tuning_sweep": sweep,
    }


def run_memory_benchmark() -> dict[str, Any]:
    tuning = evaluate_split("tuning_dev", TUNING_DATASET)
    held_out = evaluate_split("held_out", HELDOUT_DATASET)
    lifecycle = evaluate_lifecycle_invariants()
    return {
        "benchmark": "life_graph_memory_evaluation_laboratory_v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "splits": {
            "tuning_dev": tuning,
            "held_out": held_out,
        },
        "lifecycle_invariants": lifecycle,
        "abstention_probe": abstention_probe(),
    }
