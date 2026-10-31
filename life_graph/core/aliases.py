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
    ]
)

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
}
#: Roles one person holds at a time: two entities with one of these are the same
#: person when their names fit (:func:`compatible`). Son, sister, friend… are not.
UNIQUE_ROLES = frozenset({"spouse", "mother", "father", "owner"})

_ROLE = "(?i:" + "|".join(sorted(ROLE_WORDS, key=len, reverse=True)) + ")"
_MY = r"(?i:my|our|the owner's|the owner’s|owner's)"

_ALIAS_PATTERNS = (
    # Anushka (Anu) · Lakshmi (Amma) · Anushka (called Anu)
    re.compile(
        rf"(?P<full>{_NAME})\s*\((?:also |called |nicknamed |aka |a\.k\.a\. )?(?P<alias>{_NAME})\)"
    ),
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
_ALIAS_ROLE = re.compile(rf"(?P<alias>{_NAME}) is {_MY} (?P<role>{_ROLE}),? (?P<full>{_NAME})")
# "… call her Ma": the person is the one other name in the text.
_CALL_PRONOUN = re.compile(rf"\bcalls? (?P<who>her|him|me) (?P<alias>{_NAME})")

_ROLE_PATTERNS = (
    # my wife Priyadharshini · our daughter Anushka · my wife is Mahalakshmi
    re.compile(
        rf"\b{_MY}\s+(?P<role>{_ROLE})(?!['’]s)\s*,?\s+(?:is\s+(?:called\s+)?|named\s+)?(?P<name>{_NAME})",
    ),
    # Lakshmi, the owner's mother · Ramasamy is my father · Priya (the owner's wife)
    re.compile(
        rf"(?P<name>{_NAME})\s*(?:,|\(|\bis\b)\s*{_MY}\s+(?P<role>{_ROLE})\b(?!['’]s)",
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


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def _names_in(text: str) -> list[str]:
    """Distinct names written in *text*, in order (role words excluded)."""
    out: list[str] = []
    for m in re.finditer(_NAME, text):
        name = clean_name(m.group(0))
        if name and name.lower() not in ROLE_WORDS and _key(name) not in map(_key, out):
            out.append(name)
    return out


def parse(text: str) -> tuple[list[AliasClaim], list[RoleClaim]]:
    """The alias and role statements in *text*. Negated text teaches nothing:
    the caller passes only affirmed, firm facts in the owner's own words."""
    if not text:
        return [], []
    aliases: list[AliasClaim] = []
    roles: list[RoleClaim] = []

    def add_alias(full_raw: str, alias_raw: str) -> None:
        full, alias = clean_name(full_raw), clean_name(alias_raw)
        if not full or not alias or _key(full) == _key(alias):
            return
        if alias.lower() in _STOP or full.lower() in ROLE_WORDS:
            return
        claim = AliasClaim(full, alias)
        if claim not in aliases:
            aliases.append(claim)

    def add_role(name_raw: str, role_word: str) -> None:
        name = clean_name(name_raw)
        role = ROLE_WORDS.get(role_word.lower(), role_word.lower())
        if name and name.lower() not in ROLE_WORDS:
            claim = RoleClaim(name, role)
            if claim not in roles:
                roles.append(claim)

    for pattern in _ALIAS_PATTERNS:
        for m in pattern.finditer(text):
            add_alias(m.group("full"), m.group("alias"))
    for m in _ALIAS_ROLE.finditer(text):
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
        if not alias or _key(alias) in claimed:
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
    return len(short) >= 2 and long_.startswith(short)


#: A one-person role named in a question: "my wife", "amma", "அம்மா".
_QUESTION_ROLES = (
    (re.compile(r"\b(?:my|our)\s+(?:wife|husband|spouse)\b|மனைவி|கணவர்", re.I), "spouse"),
    (re.compile(r"\b(?:my|our)\s+(?:mother|mom|mum)\b|\bamma\b|அம்மா", re.I), "mother"),
    (re.compile(r"\b(?:my|our)\s+(?:father|dad)\b|\bappa\b|அப்பா", re.I), "father"),
)


def roles_in_question(text: str) -> set[str]:
    """The one-person roles a question names ("When is my wife's birthday?" → spouse)."""
    return {role for pattern, role in _QUESTION_ROLES if pattern.search(text or "")}
