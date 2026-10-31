"""Other names for the same person, learned from what the owner says. No model call.

The owner calls one person "Mahalakshmi", "Maha", "Ma" and "my wife"; the entity
index (services/entities.py) used to keep each name as a separate entity, so
"When is Maha's birthday?" missed "Mahalakshmi's birthday is 4 March", and the
form split ``family.maha.*`` from ``family.mahalakshmi.*``. Two different people
can share a first name too (Priya the wife, Priya the colleague), so a name is
only linked to another on evidence:

* an explicit statement: "Anushka (Anu)", "Priyadharshini, called Priya",
  "I call her Priya", "Maha is short for Mahalakshmi", "Maha is my wife
  Mahalakshmi" (:class:`AliasClaim`);
* the same one-person role: "my wife Ma" and "my wife Mahalakshmi" are the same
  person when one name starts with the other (:class:`RoleClaim`,
  :data:`UNIQUE_ROLES`, :func:`compatible`).

This module only reads text; services/entities.py stores the links (migration 057).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: A person's name as written: 1-3 capitalised words ("Mahalakshmi", "Priya Venkat").
_NAME = r"[A-Z][a-zA-Z'’\-]+(?: [A-Z][a-zA-Z'’\-]+){0,2}"

#: Words that start with a capital but name nobody.
_STOP = frozenset(
    [
        "the",
        "i",
        "my",
        "we",
        "he",
        "she",
        "her",
        "his",
        "him",
        "they",
        "them",
        "their",
        "our",
        "owner",
        "owner's",
        "everyone",
        "everybody",
        "people",
        "family",
        "it",
        "this",
        "that",
        "but",
        "and",
        "also",
        "mr",
        "mrs",
        "ms",
        "dr",
        "so",
        "then",
        "when",
        "if",
        "actually",
        "sorry",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "today",
        "tomorrow",
        "yesterday",
        "jarvis",
        # Sentence starters and filler: "Remember I call her Ammu" says nothing
        # of Ammu's full name (review of PR #205, 2026-10-31).
        "remember",
        "note",
        "please",
        "kindly",
        "okay",
        "ok",
        "yes",
        "no",
        "hey",
        "hi",
        "hello",
        "well",
        "oh",
        "just",
        "now",
        "here",
        "there",
        "maybe",
        "perhaps",
        "sometimes",
        "usually",
        "always",
        "often",
        "btw",
        "fyi",
        "thanks",
        "tell",
        "ask",
        "save",
        "keep",
        "add",
        "update",
        "forget",
        "call",
        "you",
        "your",
        "me",
        "us",
        "a",
        "an",
        "what",
        "who",
        "why",
        "how",
        "where",
        "which",
        "these",
        "those",
        "after",
        "before",
        "because",
        "though",
        "although",
        "while",
        "or",
        "one",
        "all",
        "some",
        "any",
        # Negations and nobody-words: "Nobody calls her Lakshmi" names no one.
        "nobody",
        "noone",
        "nothing",
        "none",
        "never",
        "not",
        "don't",
        "don’t",
        "doesn't",
        "doesn’t",
        "someone",
        "somebody",
        "anyone",
        "anybody",
        # Common romanised Tamil words, capitalised at a sentence start.
        "naan",
        "nan",
        "en",
        "enga",
        "ennoda",
        "avan",
        "aval",
        "avanga",
        "ivan",
        "ival",
        "inga",
        "anga",
        "illa",
        "illai",
        "seri",
        "sari",
        "romba",
        "ippo",
        "appo",
        "inniki",
        "innaiku",
        "nalla",
        "enna",
        "yaar",
        "aama",
    ]
)

#: A clause that denies what it says: "nobody calls her Maha", "don't call me Karthi".
_NEGATION = re.compile(
    r"\b(?:no\s*(?:body|one)|nothing|none|never|not|no longer|stop(?:ped)?)\b|n['’]t\b",
    re.IGNORECASE,
)
_CLAUSE_END = re.compile(r"[.!?;\n]")


def _negated(text: str, start: int, end: int) -> bool:
    """Whether the clause holding ``text[start:end]`` denies it (up to *end*)."""
    begin = max((m.end() for m in _CLAUSE_END.finditer(text, 0, start)), default=0)
    return _NEGATION.search(text, begin, end) is not None


#: Relationship words, as the owner says them, to the role kept on the entity.
ROLE_WORDS = {
    "wife": "spouse",
    "husband": "spouse",
    "spouse": "spouse",
    "mother": "mother",
    "mom": "mother",
    "mum": "mother",
    "amma": "mother",
    "father": "father",
    "dad": "father",
    "appa": "father",
    "son": "son",
    "daughter": "daughter",
    "sister": "sister",
    "brother": "brother",
    "friend": "friend",
    "colleague": "colleague",
    # An in-law is never the parent or sibling (review of PR #205: "Meenakshi is
    # my mother-in-law" became the owner's mother and was merged with "Meena").
    # Written with hyphens here; "mother in law" and "motherinlaw" match too.
    "mother-in-law": "mother_in_law",
    "mil": "mother_in_law",
    "mamiyar": "mother_in_law",
    "maamiyar": "mother_in_law",
    "father-in-law": "father_in_law",
    "fil": "father_in_law",
    "mamanar": "father_in_law",
    "maamanar": "father_in_law",
    "sister-in-law": "sister_in_law",
    "brother-in-law": "brother_in_law",
    "son-in-law": "son_in_law",
    "daughter-in-law": "daughter_in_law",
}
#: Roles one person holds at a time: two entities with one of these are the same
#: person when their names fit (:func:`compatible`). Son, sister, friend… are not.
#: Only the same role links: a mother-in-law never to a mother.
UNIQUE_ROLES = frozenset({"spouse", "mother", "father", "owner", "mother_in_law", "father_in_law"})


def _role_key(word: str) -> str:
    return re.sub(r"[\s\-]+", "", word.lower())


_ROLE_KEYS = {_role_key(w): role for w, role in ROLE_WORDS.items()}
_ROLE = (
    "(?i:"
    + "|".join(
        re.escape(w).replace(r"\-", r"[\s\-]*") for w in sorted(ROLE_WORDS, key=len, reverse=True)
    )
    + ")"
)
#: After a role word: not the start of an in-law ("mother" in "mother-in-law").
_NOT_IN_LAW = r"\b(?![\s\-]*(?i:in)[\s\-]*(?i:laws?)\b)"
_MY = r"(?i:my|our|the owner's|the owner’s|owner's)"

#: Tamil case endings on a name, romanised and in Tamil script: "Priyavukku" is
#: "to Priya", "Anuvoda" is "Anu's", never another name (bake-off 2026-10-31:
#: "Priyavukku" was learned as Priya's nickname). Longest first.
_CASE_ROMAN = (
    "vukkum",
    "ukkum",
    "kkum",
    "vukku",
    "ukku",
    "kku",
    "ku",
    "kum",
    "kitte",
    "kitta",
    "voda",
    "vodu",
    "vode",
    "yoda",
    "yodu",
    "oda",
    "odu",
    "ode",
    "vai",
    "yai",
    "ai",
    "vin",
    "yin",
    "in",
    "vum",
    "yum",
    "um",
)
_CASE_TAMIL = (
    "வுக்கும்",
    "வுக்கு",
    "க்கும்",
    "க்கு",
    "கிட்ட",
    "விடம்",
    "வோட",
    "வோடு",
    "வுடைய",
    "வின்",
    "வும்",
    "வை",
)
#: After a name ending in a consonant (குமார்): the pulli gives way to a vowel sign.
_CASE_TAMIL_SIGN = ("ுக்கும்", "ுக்கு", "ிடம்", "ோட", "ோடு", "ுடைய", "ின்", "ும்", "ை")
_PULLI = "்"


def stems(word: str) -> list[str]:
    """*word* without a Tamil case ending, for each ending it could have (longest
    first); the stem keeps at least three letters, four before a two-letter
    ending ("Robin" is not "Rob" + -in). Empty when it has none."""
    low = word.lower()
    out: list[str] = []
    for suf in _CASE_ROMAN + _CASE_TAMIL:
        if low.endswith(suf) and len(word) - len(suf) >= (4 if len(suf) <= 2 else 3):
            out.append(word[: -len(suf)])
    for suf in _CASE_TAMIL_SIGN:
        if word.endswith(suf) and len(word) - len(suf) >= 2:
            out.append(word[: -len(suf)] + _PULLI)
    return out


def base_name(word: str, known) -> str | None:
    """The name in *known* that *word* is a Tamil case form of ("Priyavukku" →
    "Priya"), else None. Same case first, then any case."""
    known = list(known)
    if not word or " " in word.strip():
        return None
    lower = {k.lower(): k for k in reversed(known)}
    candidates = stems(word.strip())
    for stem in candidates:
        if stem in known:
            return stem
    for stem in candidates:
        if stem.lower() in lower:
            return lower[stem.lower()]
    return None


def case_form(a: str, b: str) -> bool:
    """Whether one of two names is the other with a Tamil case ending."""
    return base_name(a, [b]) is not None or base_name(b, [a]) is not None


#: Words that introduce another name inside brackets: "(the owner's wife, called Priya)".
_CALLED = r"(?:also\s+)?(?:called|known as|nicknamed|aka|a\.k\.a\.|who goes by|goes by)"

_ALIAS_PATTERNS = (
    # Anushka (Anu) · Lakshmi (Amma) · Anushka (called Anu)
    re.compile(
        rf"(?P<full>{_NAME})\s*\((?:also |called |nicknamed |aka |a\.k\.a\. )?(?P<alias>{_NAME})\)"
    ),
    # Priyadharshini (the owner's wife, called Priya) · Vikram (our son, aka Vicky)
    re.compile(rf"(?P<full>{_NAME})\s*\([^()]*?[,;]\s*{_CALLED}\s+(?P<alias>{_NAME})\s*\)"),
    # Priyadharshini, called Priya · Vikram, also known as Vicky
    re.compile(
        rf"(?P<full>{_NAME}),?\s+(?:also\s+)?(?:called|known as|nicknamed|aka|a\.k\.a\.|"
        rf"who goes by|goes by)\s+(?P<alias>{_NAME})"
    ),
    # Priyadharshini — I call her Priya · Karthik Rajan, but everyone calls me Karthi
    re.compile(
        rf"(?P<full>{_NAME})\s*(?:[,;—–-]+\s*)?(?:but\s+|and\s+)?(?:I|we|everyone|everybody|"
        rf"people|the family|the owner|friends)\s+(?:all\s+)?(?:usually\s+)?calls?\s+"
        rf"(?:her|him|me|them)\s+(?P<alias>{_NAME})"
    ),
    # Maha is short for Mahalakshmi
    re.compile(rf"(?P<alias>{_NAME}) is short for (?P<full>{_NAME})"),
)
# Maha is my wife Mahalakshmi
_ALIAS_ROLE = re.compile(
    rf"(?P<alias>{_NAME}) is {_MY} (?P<role>{_ROLE}){_NOT_IN_LAW},? (?P<full>{_NAME})"
)
# "… call her Ma": the person is the one other name in the text.
_CALL_PRONOUN = re.compile(rf"\bcalls? (?P<who>her|him|me) (?P<alias>{_NAME})")

_ROLE_PATTERNS = (
    # my wife Priyadharshini · our daughter Anushka · my wife is Mahalakshmi
    re.compile(
        rf"\b{_MY}\s+(?P<role>{_ROLE}){_NOT_IN_LAW}(?!['’]s)\s*,?\s+"
        rf"(?:is\s+(?:called\s+)?|named\s+)?(?P<name>{_NAME})",
    ),
    # Lakshmi, the owner's mother · Ramasamy is my father · Priya (the owner's wife)
    re.compile(
        rf"(?P<name>{_NAME})\s*(?:,|\(|\bis\b)\s*{_MY}\s+(?P<role>{_ROLE}){_NOT_IN_LAW}(?!['’]s)",
    ),
)
_OWNER_NAME = re.compile(rf"\b(?i:my|the owner's|the owner’s) (?:full )?name is (?P<name>{_NAME})")


@dataclass(frozen=True)
class AliasClaim:
    """*alias* is another name for *full* (the name kept as the person's own)."""

    full: str
    alias: str


@dataclass(frozen=True)
class RoleClaim:
    """*name* is the owner's *role* (spouse, mother, owner, …)."""

    name: str
    role: str


def clean_name(raw: str) -> str | None:
    """*raw* without a possessive or leading stop words; None when nothing is left."""
    words = re.sub(r"['’]s$", "", raw.strip()).split()
    while words and words[0].lower() in _STOP:
        words.pop(0)
    while words and words[-1].lower() in _STOP:
        words.pop()
    if not words or len(words[0]) < 2:
        return None
    return " ".join(words)


def _is_role_word(name: str) -> bool:
    return _role_key(name) in _ROLE_KEYS


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def _names_in(text: str) -> list[str]:
    """Distinct names written in *text*, in order (role words excluded)."""
    out: list[str] = []
    for m in re.finditer(_NAME, text):
        name = clean_name(m.group(0))
        if name and not _is_role_word(name) and _key(name) not in map(_key, out):
            out.append(name)
    return out


def parse(text: str) -> tuple[list[AliasClaim], list[RoleClaim]]:
    """The alias and role statements in *text*. Negated text teaches nothing:
    the caller passes only affirmed, firm facts in the owner's own words, and a
    denied alias in the clause ("nobody calls her Maha", "don't call me
    Karthi") is skipped here too."""
    if not text:
        return [], []
    aliases: list[AliasClaim] = []
    roles: list[RoleClaim] = []

    def add_alias(full_raw: str, alias_raw: str) -> None:
        full, alias = clean_name(full_raw), clean_name(alias_raw)
        if not full or not alias or _key(full) == _key(alias):
            return
        if alias.lower() in _STOP or _is_role_word(full) or case_form(full, alias):
            return
        claim = AliasClaim(full, alias)
        if claim not in aliases:
            aliases.append(claim)

    def add_role(name_raw: str, role_word: str) -> None:
        name = clean_name(name_raw)
        role = _ROLE_KEYS.get(_role_key(role_word), role_word.lower())
        if name and not _is_role_word(name):
            claim = RoleClaim(name, role)
            if claim not in roles:
                roles.append(claim)

    for pattern in _ALIAS_PATTERNS:
        for m in pattern.finditer(text):
            if not _negated(text, m.start(), m.end()):
                add_alias(m.group("full"), m.group("alias"))
    for m in _ALIAS_ROLE.finditer(text):
        if not _negated(text, m.start(), m.end()):
            add_alias(m.group("full"), m.group("alias"))
            add_role(m.group("full"), m.group("role"))
    for pattern in _ROLE_PATTERNS:
        for m in pattern.finditer(text):
            add_role(m.group("name"), m.group("role"))
    owner = _OWNER_NAME.search(text)
    if owner:
        add_role(owner.group("name"), "owner")

    claimed = {_key(c.alias) for c in aliases}
    for m in _CALL_PRONOUN.finditer(text):
        alias = clean_name(m.group("alias"))
        if not alias or _key(alias) in claimed or _negated(text, m.start(), m.end()):
            continue
        if m.group("who") == "me":
            if owner:
                add_alias(owner.group("name"), alias)
            continue
        # "her"/"him": only when exactly one other person is named, else ambiguous.
        others = [n for n in _names_in(text[: m.start()]) if _key(n) != _key(alias)]
        if len(others) == 1:
            add_alias(others[0], alias)
    return aliases, roles


def compatible(a: str, b: str) -> bool:
    """Whether two names can be one person's: one first name starts with the other
    ("Ma", "Maha", "Mahalakshmi"). Used only together with a shared one-person role."""
    x, y = a.lower().split()[0], b.lower().split()[0]
    short, long_ = sorted((x, y), key=len)
    # "Priyavukku" is "to Priya", not a longer name of hers.
    return len(short) >= 2 and long_.startswith(short) and not case_form(x, y)


#: A one-person role named in a question: "my wife", "amma", "அம்மா".
_IN_LAW = r"[\s\-]*in[\s\-]*law"
_QUESTION_ROLES = (
    (re.compile(r"\b(?:my|our)\s+(?:wife|husband|spouse)\b|மனைவி|கணவர்", re.I), "spouse"),
    (
        re.compile(rf"\b(?:my|our)\s+(?:mother{_IN_LAW}|mil)\b|\bma+miyar\b|மாமியார்", re.I),
        "mother_in_law",
    ),
    (
        re.compile(rf"\b(?:my|our)\s+(?:father{_IN_LAW}|fil)\b|\bma+manar\b|மாமனார்", re.I),
        "father_in_law",
    ),
    (
        re.compile(rf"\b(?:my|our)\s+(?:mother|mom|mum)\b(?!{_IN_LAW})|\bamma\b|அம்மா", re.I),
        "mother",
    ),
    (
        re.compile(rf"\b(?:my|our)\s+(?:father|dad)\b(?!{_IN_LAW})|\bappa\b|அப்பா", re.I),
        "father",
    ),
)


def roles_in_question(text: str) -> set[str]:
    """The one-person roles a question names ("When is my wife's birthday?" → spouse)."""
    return {role for pattern, role in _QUESTION_ROLES if pattern.search(text or "")}
