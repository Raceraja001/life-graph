"""Tamil and Tanglish decision statements in the owner's own words.

The capture spine's English patterns (``_DECISION_PATTERNS`` in
services/capture_processors.py) never saw "முடிவு செய்தோம்" or "decide
panniten", so a decision the owner said in Tamil made no candidate. This
module finds those, by rule, with no model call. It only makes *candidates*,
like the English path: the owner confirms or drops each one (#436), and the
caller only asks for the owner's own words (the SELF tier gate ``_is_self``).

How a sentence fires, on Tamil-safe tokens (``typed_links.tokens``: letters
and vowel signs stay together, audit D10):

1. **Decided, first person.** A decision word, matched as the start of a token
   so case endings still match (முடிவு, முடிவை, முடிவா; mudivu, mudiva;
   decide, decided, decision; finalize), followed within two tokens by a
   first-person past "did / took" verb: செய்தோம், பண்ணேன், எடுத்தோம்;
   pannen, panniten, panninom, senjom, eduthen. Only those exact forms count,
   so "decide pannalaam" (let's decide), "decide pannuvom" (we will),
   "decide pannala" (did not), "decide pannina" (if) and "decide
   pannitaanga" (they did) never fire.
2. **It is decided.** One token: முடிவாச்சு, mudivaachu, mudivaayiduchu.
3. **"X venaam nu mudivu".** A decision word that ends the sentence right
   after a quotative (nu, னு, என்று): "Kafka venaam nu mudivu."
4. **"X venaam, Y -laam".** "Kafka venaam, Postgres pogalaam": no to one
   thing, then "let's" (-laam, -லாம்) with something in between.

A sentence never fires when it is a question ("?" or a question word such as
enna, ethu, என்ன), a hypothetical or a hedge (oruvela, maybe, if,
நினைக்கிறேன்), negated (illa, இல்லை), or reported speech (sonnaanga,
சொன்னார், கூறினார்): precision first. Each sentence gives at most one
candidate, its own words as the title.
"""

from __future__ import annotations

import re

from life_graph.services.memory.typed_links import tokens

#: Decision words, matched as token starts (case endings follow).
DECISION_STEMS: tuple[str, ...] = ("முடிவ", "mudiv", "decid", "decis", "finali", "டிசைட")

#: First-person past "did / took / have done" verbs that make a decision word a
#: decision. Whole tokens only: other endings mean let's, will, not, if or they.
DID_VERBS = frozenset(
    # Tamil script
    {"செய்தேன்", "செய்தோம்", "செஞ்சேன்", "செஞ்சோம்", "செய்துவிட்டேன்", "செய்துவிட்டோம்"}
    | {"செய்திட்டேன்", "செய்திட்டோம்", "பண்ணேன்", "பண்ணினேன்", "பண்ணோம்", "பண்ணினோம்"}
    | {"பண்ணிட்டேன்", "பண்ணிட்டோம்", "பண்ணியாச்சு", "எடுத்தேன்", "எடுத்தோம்"}
    | {"எடுத்துட்டேன்", "எடுத்துட்டோம்", "எடுத்துவிட்டேன்", "எடுத்துவிட்டோம்"}
    # Tanglish
    | {"pannen", "panninen", "pannunen", "panniten", "pannitten", "pannitaen", "panniteen"}
    | {"pannom", "panninom", "pannunom", "pannitom", "pannittom", "pannitoom", "panniyachu"}
    | {"panniyaachu", "senjen", "senjom", "senjiten", "senjitom", "seithen", "seithom"}
    | {"seidhen", "seidhom", "seythen", "seythom", "eduthen", "eduthom", "edutthen"}
    | {"edutthom", "eduthuten", "eduthutten", "eduthutom", "eduthuttom"}
)

#: "It is decided" in one token, matched as a token start.
DECIDED_STEMS: tuple[str, ...] = (
    "முடிவாச்ச",
    "முடிவாயிடுச்ச",
    "முடிவாகிவிட்ட",
    "mudivaach",
    "mudivaayiduch",
    "mudivayiduch",
)

#: Quotatives ("... nu", "that ...") before a closing decision word.
QUOTATIVES = frozenset({"nu", "nnu", "னு", "ன்னு", "endru", "enru", "என்று"})
#: Tamil-script quotative endings glued to the word before ("வேண்டாம்னு").
QUOTATIVE_ENDINGS: tuple[str, ...] = ("னு", "venaamnu", "vendaamnu")

#: "Don't want / no to" for the "X venaam, Y -laam" choice.
NOT_WANTED = frozenset({"venaam", "vendaam", "vendam", "வேண்டாம்", "வேணாம்"})
#: "Let's / may" verb endings; "ellaam" (all) is not a verb.
LETS_ENDINGS: tuple[str, ...] = ("laam", "லாம்")
NOT_LETS = frozenset({"ellaam", "ellam", "எல்லாம்"})

#: A sentence holding any of these never fires.
QUESTION_WORDS = frozenset(
    {"enna", "yenna", "ennanu", "eppadi", "epdi", "ethu", "edhu", "yethu", "ethai", "edhai"}
    | {"yen", "yaen", "ethukku", "edhukku", "evlo", "yaaru", "yaar", "eppo"}
    | {"என்ன", "எப்படி", "எது", "எதை", "ஏன்", "எதுக்கு", "எவ்வளவு", "யாரு", "யார்", "எங்கே"}
    | {"எப்போ", "எப்போது"}
)
HEDGE_WORDS = frozenset(
    {"oruvela", "oruvelai", "ஒருவேளை", "maybe", "if", "suppose", "probably", "perhaps"}
    | {"ninaikiren", "nenaikuren", "ninaikkiren", "nenaikiren", "நினைக்கிறேன்", "thonudhu"}
    | {"thonuthu", "தோணுது", "illana", "illanna", "illaatti", "illati"}
)
NEGATION_WORDS = frozenset({"illa", "illai", "illaye", "இல்லை", "இல்ல", "கிடையாது"})
#: Reported speech: "said / told / informed", matched as token starts.
REPORTED_STEMS: tuple[str, ...] = (
    "sonn",
    "solr",
    "solluraa",
    "சொன்ன",
    "சொல்ற",
    "சொல்கிற",
    "கூறின",
    "தெரிவித்த",
)

#: A sentence ends at . ! ? or a new line.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _blocked(sentence: str, toks: list[str]) -> bool:
    """True for a question, a hedge or hypothetical, a negation or reported speech."""
    if "?" in sentence:
        return True
    for tok in toks:
        if tok in QUESTION_WORDS or tok in HEDGE_WORDS or tok in NEGATION_WORDS:
            return True
        if tok.startswith(REPORTED_STEMS):
            return True
    return False


def _decided(toks: list[str]) -> bool:
    """Rules 1-3: a decision word with a first-person "did", "it is decided", or "nu mudivu"."""
    for i, tok in enumerate(toks):
        if tok.startswith(DECIDED_STEMS):
            return True
        if not tok.startswith(DECISION_STEMS):
            continue
        if any(t in DID_VERBS for t in toks[i + 1 : i + 3]):
            return True
        before = toks[i - 1] if i else ""
        quoted = before in QUOTATIVES or before.endswith(QUOTATIVE_ENDINGS)
        if quoted and i == len(toks) - 1:
            return True
    return False


def _not_this_but_that(toks: list[str]) -> bool:
    """Rule 4: "X venaam, Y pogalaam": a "let's" verb at least two tokens after "venaam"."""
    for i, tok in enumerate(toks):
        if tok not in NOT_WANTED:
            continue
        for later in toks[i + 2 :]:
            if later.endswith(LETS_ENDINGS) and len(later) > 4 and later not in NOT_LETS:
                return True
    return False


def detect(text: str) -> list[str]:
    """The sentences of *text* that state a Tamil or Tanglish decision, in order."""
    out: list[str] = []
    for raw in _SENTENCE_END.split(text or ""):
        sentence = raw.strip()
        toks = tokens(sentence)
        if not toks or _blocked(sentence, toks):
            continue
        if _decided(toks) or _not_this_but_that(toks):
            out.append(sentence.rstrip(".,;!? "))
    return out
