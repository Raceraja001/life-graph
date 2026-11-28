"""When a fact started being true in the world, from its own words (ADR m8-ingestion §5.1).

Pure rules, no I/O and no model. Given a text and the moment it was said (the
*anchor*: ``said_at`` for a late capture, else now, in the owner's time zone),
:func:`find` returns the start of the period the text names, with its
precision, or ``None`` for unknown.

What gives a start:

* a date: "on 3 May", "May 3, 2025", "2024-05-03", "3/5/2025" (day first, the
  Indian order, unless the day is clearly second as in "5/23/2024");
* a month: "in March", "since March 2024", "from January", "March 2024". A
  month with no year is the most recent one that has begun: "in March" said
  in February means last year's March;
* a year: "in 2019", "since 2019", "back in 2019";
* a relative day or period: "yesterday", "day before yesterday", "last
  night", "3 days ago", "a month ago", "last week / month / year", "this week /
  month / year", "today", "this morning";
* the same in Tamil and Tanglish (:data:`TAMIL` and the sets below): நேற்று,
  முந்தாநாள், இன்னைக்கு, போன வாரம், கடந்த மாதம், போன வருஷம், "3 நாள் முன்",
  "2019 முதல்", "nethu", "pona maasam", "2019 la irundhu", "March la".

What never gives a start (the result is ``None``):

* a future phrase: "tomorrow", "next week", "by Friday", "in 3 days", a date
  or year after the anchor, நாளைக்கு, அடுத்த மாதம், "adutha vaaram". A plan has
  a due time (services/commitments.py), not a world time;
* an intention, a hedge or a negation anywhere in the text: "I will", "going
  to", "maybe", "I think", "not", போறேன், இருக்கலாம், இல்லை, "poren", "illa";
* an end, not a start: "until", "till", வரை, "varaikum";
* a phrase the rules see but cannot place: a weekday ("on Friday"), "last
  March", "recently", "for 3 years", "now", "currently", a festival. These
  still count in :func:`phrase_count`, so a message with one of them is not
  read for a start (§5.1 point 2) and a model's date can be checked against
  it (point 3, :func:`from_model`);
* two different starts in one text: which fact is which is not known.

"Now" and "currently" are deliberately unknown: they say a state holds now,
not that it began today. The ADR table lists them with "the said day"; that
start would only restate the recorded time as a claimed world time.

Words are matched as tokens, never with ``\\w``: a token is a run of letters,
marks and digits of any script after NFKC and lower-casing, the same rule as
the snapshot's keyword match (snapshot._words, sufficiency._tokens, audit
D10), so Tamil vowel signs stay inside their word. Digits and letters are
also split ("2019ல்" is "2019" and "ல்"), so a Tamil case ending glued to a
year is still seen. The Tamil and Tanglish lists are data, for the owner to
review and extend; a word that is missing gives "unknown", which is today's
state.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

# ── Result ────────────────────────────────────────────────────

DAY = "day"
WEEK = "week"
MONTH = "month"
YEAR = "year"

#: Where a start was read (``properties.world_time.source``).
CONTENT = "content"
SOURCE_TEXT = "source_text"
MODEL = "model"


@dataclass(frozen=True)
class WorldTime:
    """The start of a fact in the world: the first instant of the named period."""

    start: datetime
    precision: str
    rule: str
    source: str = CONTENT


# ── Word lists (data) ─────────────────────────────────────────

MONTHS: dict[str, int] = {
    **{name.lower(): i for i, name in enumerate(calendar.month_name) if name},
    **{
        a: i
        for a, i in (
            ("jan", 1),
            ("feb", 2),
            ("mar", 3),
            ("apr", 4),
            ("jun", 6),
            ("jul", 7),
            ("aug", 8),
            ("sep", 9),
            ("sept", 9),
            ("oct", 10),
            ("nov", 11),
            ("dec", 12),
        )
    },
    # Month names as Tamil writes them.
    "ஜனவரி": 1,
    "பிப்ரவரி": 2,
    "மார்ச்": 3,
    "ஏப்ரல்": 4,
    "மே": 5,
    "ஜூன்": 6,
    "ஜூலை": 7,
    "ஆகஸ்ட்": 8,
    "ஆகஸ்டு": 8,
    "செப்டம்பர்": 9,
    "அக்டோபர்": 10,
    "நவம்பர்": 11,
    "டிசம்பர்": 12,
}
#: "may" is also a verb: a month only with a day, a year or a preposition.
WEEKDAYS = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    | {"திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"}
    | {"thingal", "sevvai", "budhan", "vyazhan", "velli", "sani", "nyayiru"}
)
NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "ஒரு": 1,
    "ரெண்டு": 2,
    "இரண்டு": 2,
    "மூணு": 3,
    "மூன்று": 3,
    "நாலு": 4,
    "நான்கு": 4,
    "அஞ்சு": 5,
    "ஐந்து": 5,
    "oru": 1,
    "rendu": 2,
    "moonu": 3,
    "naalu": 4,
    "anju": 5,
}
ORDINAL = frozenset({"st", "nd", "rd", "th"})

#: English period words, singular and plural.
UNITS: dict[str, str] = {
    "day": DAY,
    "days": DAY,
    "week": WEEK,
    "weeks": WEEK,
    "month": MONTH,
    "months": MONTH,
    "year": YEAR,
    "years": YEAR,
}

#: Tamil and Tanglish words, by meaning. Owner-reviewed data (ADR §5.1).
TAMIL: dict[str, frozenset[str]] = {
    "yesterday": frozenset(
        {"நேற்று", "நேத்து", "நேற்றைக்கு", "நேத்திக்கு", "நேத்தைக்கு"}
        | {"nethu", "netthu", "nethiku", "nethikku", "nethaiku", "netru", "nettru"}
    ),
    "day_before": frozenset(
        {"முந்தாநாள்", "முந்தாநேத்து", "munthanaal", "mundhanaal"}
        | {"munthanethu", "mundhanethu", "muntanethu"}
    ),
    #: "முந்தா நாள்" written as two words: the first word.
    "day_before_1": frozenset({"முந்தா", "muntha", "mundha"}),
    "today": frozenset(
        {"இன்று", "இன்னைக்கு", "இன்னிக்கு", "இன்றைக்கு"}
        | {"innaiku", "innaikku", "inniku", "innikku", "indru", "inru"}
    ),
    "tomorrow": frozenset(
        {"நாளை", "நாளைக்கு", "naalai", "naalaiku", "naalaikku", "nalaiku", "naaliku", "naliku"}
    ),
    "last": frozenset({"போன", "கடந்த", "pona", "ponna", "kadantha", "kadandha", "kadanta"}),
    "this": frozenset({"இந்த", "indha", "intha", "inda"}),
    "next": frozenset({"அடுத்த", "வரும்", "வர்ற", "adutha", "aduththa", "varum", "varra"}),
    "week": frozenset({"வாரம்", "வாரத்தில்", "வாரத்துல", "vaaram", "varam", "vaarathula", "varathula"}),
    "month": frozenset(
        {"மாதம்", "மாசம்", "மாதத்தில்", "மாதத்துல", "மாசத்துல", "மாசத்தில்"}
        | {"maasam", "masam", "maatham", "madham", "maasathula", "masathula", "maasathil"}
    ),
    "year": frozenset(
        {"வருஷம்", "வருடம்", "ஆண்டு", "வருஷத்துல", "வருடத்தில்", "ஆண்டில்", "ஆண்டின்"}
        | {"varusham", "varusam", "varudam", "varushathula", "varushathil", "aandu"}
    ),
    "day": frozenset(
        {"நாள்", "நாளைக்கு", "நாட்களுக்கு", "நாட்கள்", "நாளுக்கு"} | {"naal", "naalaiku", "naalukku", "naatkal"}
    ),
    "ago": frozenset(
        {"முன்", "முன்பு", "முன்னாடி", "முன்னால்", "முன்னர்"}
        | {"mun", "munbu", "munnadi", "munadi", "munnaadi", "munnaal", "munnaala"}
    ),
    #: After a year or a month: since / from / in ("2019 முதல்", "2019-ல", "2019 la irundhu").
    "since": frozenset(
        {"முதல்", "இருந்து", "லிருந்து", "லேர்ந்து", "ல", "ல்", "இல்", "லே", "ஆம்"}
        | {"irundhu", "irunthu", "lerndhu", "lendhu", "la", "le", "il", "mudhal", "muthal"}
    ),
}
_TA_UNIT = {"week": WEEK, "month": MONTH, "year": YEAR, "day": DAY}

#: Seen as a time but not placeable: counted, never resolved.
VAGUE = frozenset(
    {"recently", "lately", "nowadays", "currently", "now", "tonight", "earlier", "ago"}
    | {"சமீபத்தில்", "இப்போ", "இப்போது", "இப்ப", "ippo", "ippa", "ipo", "samipathula"}
    | {"pongal", "diwali", "deepavali", "onam", "ugadi", "பொங்கல்", "தீபாவளி"}
)

#: Intention, hedge, negation or an end, as whole tokens: the text gives no start.
TAMIL_BLOCK = frozenset(
    # hedge
    {"ஒருவேளை", "இருக்கலாம்", "தெரியல", "தெரியலை", "தெரியவில்லை", "நினைக்கிறேன்", "போல"}
    | {"oruvela", "oruvelai", "irukalam", "irukkalam", "theriyala", "therila", "theriyalai"}
    | {"ninaikiren", "nenaikuren", "ninaikkiren", "nenaikiren", "pola"}
    # negation
    | {"இல்லை", "இல்ல", "கிடையாது", "மாட்டேன்", "மாட்டோம்"}
    | {"illa", "illai", "illaye", "kidaiyathu", "kidayathu", "maaten", "matten", "maatom"}
    | {"pogala", "pannala", "varala", "seiyala", "pannale", "pogale"}
    # intention / must
    | {"வேண்டும்", "வேணும்", "போறேன்", "போகிறேன்", "போறோம்", "போகிறோம்"}
    | {"venum", "vendum", "poren", "porom", "poraen", "pogiren", "pogirom"}
    | {"pannuven", "seiven", "varuven", "poven", "vanguven", "pannanum", "seiyanum"}
    | {"poganum", "vanganum", "pannuvom"}
    # until
    | {"வரை", "வரைக்கும்", "varai", "varaikum", "varaikkum", "varaiku"}
)
#: Tamil verb endings: may / let's (-லாம்), must (-ணும்), I will (-ப்பேன், -வேன்),
#: going to (-போறேன்), did not (-வில்லை, -ல்லை).
TAMIL_BLOCK_ENDINGS = ("லாம்", "ணும்", "ப்பேன்", "வேன்", "போறேன்", "போகிறேன்", "வில்லை", "ல்லை")
#: Words with those endings that are not verbs: எல்லாம் is "all", எல்லை "a border".
TAMIL_NOT_BLOCK = frozenset({"எல்லாம்", "எல்லை"})

_EN_BLOCK = re.compile(
    r"\b(?:\w+(?:'|’)ll|\w+n(?:'|’)t|won(?:'|’)t|can(?:'|’)t)\b"  # I'll, didn't
    r"|\b(?:will|shall|gonna|wanna|planning|intend(?:s|ed)?\s+to|hope\s+to|hoping\s+to)\b"
    r"|\b(?:am|is|are|i'?m|we'?re|they'?re|he'?s|she'?s|im)\s+going\s+to\b"
    r"|\b(?:plans?|wants?|needs?|have|has)\s+to\b|\bwould\s+like\b|\bremind\s+me\b"
    r"|\b(?:must|should|might|maybe|perhaps|probably|possibly|unsure|apparently)\b"
    r"|\bsupposedly\b|\bnot\s+sure\b|\bi\s+(?:think|guess|believe|suppose)\b"
    r"|\b(?:may|might|could)\s+(?:have|be)\b"
    r"|\b(?:not|never|no\s+longer|no\s+more|nor)\b"
    r"|\b(?:dont|didnt|doesnt|isnt|wasnt|arent|werent|havent|hasnt|hadnt|wont|cant)\b"
    r"|\b(?:until|till|untill|upto|up\s+to)\b",
    re.IGNORECASE,
)

#: A sentence's full stop may follow a date; another digit group may not.
_ISO = re.compile(r"(?<![\d/.-])(\d{4})-(\d{1,2})-(\d{1,2})(?![\d/-]|\.\d)")
_DMY = re.compile(r"(?<![\d/.-])(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?![\d/-]|\.\d)")


# ── Tokens ────────────────────────────────────────────────────


def _is_word_char(ch: str) -> bool:
    """A letter, a mark or a digit of any script (the snapshot's D10 rule)."""
    return unicodedata.category(ch)[0] in "LMN"


def tokens(text: str) -> list[str]:
    """*text* as lower-cased word tokens; digits and letters split apart."""
    folded = unicodedata.normalize("NFKC", text or "").lower()
    folded = folded.replace("'", "").replace("’", "")
    out: list[str] = []
    word: list[str] = []
    digit = False
    for ch in folded + " ":
        if _is_word_char(ch):
            is_digit = ch.isdigit()
            if word and is_digit != digit:
                out.append("".join(word))
                word = []
            word.append(ch)
            digit = is_digit
            continue
        if word:
            out.append("".join(word))
            word = []
    return out


def blocked(text: str) -> bool:
    """True when *text* is a plan, an intention, hedged, negated or an end ("until")."""
    if _EN_BLOCK.search(text or ""):
        return True
    for tok in tokens(text):
        if tok in TAMIL_BLOCK:
            return True
        if len(tok) > 4 and tok.endswith(TAMIL_BLOCK_ENDINGS) and tok not in TAMIL_NOT_BLOCK:
            return True
    return False


# ── Hits ──────────────────────────────────────────────────────

#: A hit's kind: a start, a future phrase, or a time the rules cannot place.
START = "start"
FUTURE = "future"
SEEN = "seen"


@dataclass(frozen=True)
class _Hit:
    kind: str
    rule: str
    day: date | None = None
    precision: str | None = None


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _months_back(d: date, n: int) -> date:
    index = d.year * 12 + (d.month - 1) - n
    return date(index // 12, index % 12 + 1, 1)


def _period_start(today: date, unit: str, back: int) -> date:
    """The first day of the *unit* period *back* periods before the one holding *today*."""
    if unit == DAY:
        return today - timedelta(days=back)
    if unit == WEEK:
        return _week_start(today) - timedelta(weeks=back)
    if unit == MONTH:
        return _months_back(today, back)
    return date(today.year - back, 1, 1)


def _ago(today: date, unit: str, n: int) -> date:
    """The period *n* units before *today* ("3 weeks ago" is the week of today - 21 days)."""
    if unit == DAY:
        return today - timedelta(days=n)
    if unit == WEEK:
        return _week_start(today - timedelta(weeks=n))
    return _period_start(today, unit, n)


def _dated(rule: str, day: date, precision: str, today: date) -> _Hit:
    """A start, or a future hit when *day* has not begun by *today*."""
    if day > today:
        return _Hit(FUTURE, rule)
    return _Hit(START, rule, day, precision)


def _number(tok: str) -> int | None:
    if tok.isdigit() and len(tok) <= 3:
        return int(tok)
    return NUMBER_WORDS.get(tok)


def _year(tok: str) -> int | None:
    if tok.isdigit() and len(tok) == 4 and 1900 <= int(tok) <= 2199:
        return int(tok)
    return None


def _day_of_month(tok: str) -> int | None:
    if tok.isdigit() and len(tok) <= 2 and 1 <= int(tok) <= 31:
        return int(tok)
    return None


def _past_month(today: date, month: int) -> date:
    """The first of the most recent *month* that has begun by *today*."""
    year = today.year if month <= today.month else today.year - 1
    return date(year, month, 1)


def _make_day(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _with_day(today: date, month: int, day: int, year: int | None) -> date | None:
    """The date; with no year, the most recent one on or before *today*."""
    if year is not None:
        return _make_day(year, month, day)
    found = _make_day(today.year, month, day)
    if found is None or found > today:
        found = _make_day(today.year - 1, month, day)
    return found


# A matcher looks at tokens from position i: (tokens consumed, hit) or None.
_Match = tuple[int, _Hit] | None
_Matcher = Callable[[list[str], int, date], _Match]


def _at(toks: list[str], i: int) -> str:
    return toks[i] if 0 <= i < len(toks) else ""


def _skip_ordinal(toks: list[str], i: int) -> int:
    return i + 1 if _at(toks, i) in ORDINAL else i


def _en_relative(toks: list[str], i: int, today: date) -> _Match:
    """yesterday, day before yesterday, last night, today, this morning, tomorrow."""
    t = toks[i]
    nxt = _at(toks, i + 1)
    if t == "day" and nxt == "before" and _at(toks, i + 2) == "yesterday":
        return 3, _Hit(START, "en.day_before_yesterday", today - timedelta(days=2), DAY)
    if t == "day" and nxt == "after" and _at(toks, i + 2) == "tomorrow":
        return 3, _Hit(FUTURE, "en.day_after_tomorrow")
    if t in ("yesterday", "yesterdays"):
        return 1, _Hit(START, "en.yesterday", today - timedelta(days=1), DAY)
    if t == "last" and nxt == "night":
        return 2, _Hit(START, "en.last_night", today - timedelta(days=1), DAY)
    if t in ("today", "todays") or (t == "this" and nxt in ("morning", "afternoon", "evening")):
        return (1 if t != "this" else 2), _Hit(START, "en.today", today, DAY)
    if t in ("tomorrow", "tomorrows", "soon", "upcoming", "later"):
        return 1, _Hit(FUTURE, f"en.{t}")
    return None


def _en_period(toks: list[str], i: int, today: date) -> _Match:
    """last / this / next / coming / past + week, month, year, weekday or month name."""
    t, nxt = toks[i], _at(toks, i + 1)
    if t not in ("last", "this", "next", "coming", "past", "previous"):
        return None
    unit = UNITS.get(nxt) if nxt in ("week", "month", "year") else None
    if t in ("next", "coming") and (unit or nxt in WEEKDAYS or nxt in MONTHS):
        return 2, _Hit(FUTURE, f"en.{t}")
    if unit and t in ("last", "previous"):
        return 2, _Hit(START, f"en.last_{nxt}", _period_start(today, unit, 1), unit)
    if unit and t == "this":
        return 2, _Hit(START, f"en.this_{nxt}", _period_start(today, unit, 0), unit)
    if unit or nxt in WEEKDAYS or nxt in MONTHS or nxt in ("weekend", "few", "couple"):
        # "past week" is a rolling window; "last Friday", "last March" are ambiguous.
        return 2, _Hit(SEEN, f"en.{t}_{nxt}")
    return None


def _en_ago(toks: list[str], i: int, today: date) -> _Match:
    """N days / weeks / months / years ago; "in N days" is the future."""
    n = _number(toks[i])
    unit = UNITS.get(_at(toks, i + 1))
    if n is None or unit is None:
        return None
    if _at(toks, i + 2) == "ago":
        return 3, _Hit(START, f"en.{unit}s_ago", _ago(today, unit, n), unit)
    if _at(toks, i - 1) in ("in", "within"):
        return 2, _Hit(FUTURE, "en.in_n")
    # "for 3 years", "3 days back": a time, not a start the rules can place.
    return 2, _Hit(SEEN, f"en.{unit}s")


def _date_tail(toks: list[str], j: int) -> tuple[int | None, int]:
    """An optional year at *j* (after an optional comma, already dropped): (year, next j)."""
    year = _year(_at(toks, j))
    return (year, j + 1) if year is not None else (None, j)


def _en_date(toks: list[str], i: int, today: date) -> _Match:
    """3 May [2025], 3rd of May, May 3[, 2025], March 2024."""
    day = _day_of_month(toks[i])
    if day is not None:
        j = _skip_ordinal(toks, i + 1)
        j = j + 1 if _at(toks, j) == "of" else j
        month = MONTHS.get(_at(toks, j))
        if month is not None:
            year, end = _date_tail(toks, j + 1)
            found = _with_day(today, month, day, year)
            if found is not None:
                return end - i, _dated("date", found, DAY, today)
        return None
    month = MONTHS.get(toks[i])
    if month is None:
        return None
    day = _day_of_month(_at(toks, i + 1))
    if day is not None:
        year, end = _date_tail(toks, _skip_ordinal(toks, i + 2))
        found = _with_day(today, month, day, year)
        if found is not None:
            return end - i, _dated("date", found, DAY, today)
    year = _year(_at(toks, i + 1))
    if year is not None:
        return 2, _dated("month_year", date(year, month, 1), MONTH, today)
    return None


_EN_PREP = frozenset({"in", "since", "from", "during", "back", "of"})
_QUALIFIER = frozenset({"early", "mid", "late", "the", "in"})


def _en_prep(toks: list[str], i: int, today: date) -> _Match:
    """in / since / from / during / back in + [early|mid|late] month or year."""
    if toks[i] not in _EN_PREP:
        return None
    j = i + 1
    while _at(toks, j) in _QUALIFIER and j < i + 3:
        j += 1
    year = _year(_at(toks, j))
    if year is not None:
        return j + 1 - i, _dated("year", date(year, 1, 1), YEAR, today)
    month = MONTHS.get(_at(toks, j))
    if month is not None and toks[i] != "of":
        if _year(_at(toks, j + 1)) is not None or _day_of_month(_at(toks, j + 1)) is not None:
            return None  # the date and month-year matchers take it from the month
        return j + 1 - i, _Hit(START, "month", _past_month(today, month), MONTH)
    return None


def _ta_word(toks: list[str], i: int, today: date) -> _Match:
    """நேற்று / nethu, முந்தாநாள், இன்னைக்கு / innaiku, நாளைக்கு / naalaiku."""
    t = toks[i]
    if t in TAMIL["yesterday"]:
        return 1, _Hit(START, "ta.yesterday", today - timedelta(days=1), DAY)
    if t in TAMIL["day_before"]:
        return 1, _Hit(START, "ta.day_before", today - timedelta(days=2), DAY)
    if t in TAMIL["day_before_1"] and _at(toks, i + 1) in ("நாள்", "naal", "nethu", "நேத்து"):
        return 2, _Hit(START, "ta.day_before", today - timedelta(days=2), DAY)
    if t in TAMIL["today"]:
        return 1, _Hit(START, "ta.today", today, DAY)
    if t in TAMIL["tomorrow"]:
        return 1, _Hit(FUTURE, "ta.tomorrow")
    return None


def _ta_unit(tok: str) -> str | None:
    for key, unit in _TA_UNIT.items():
        if tok in TAMIL[key]:
            return unit
    return None


def _ta_period(toks: list[str], i: int, today: date) -> _Match:
    """போன / கடந்த / இந்த / அடுத்த + வாரம், மாதம், வருஷம் (and Tanglish)."""
    t = toks[i]
    unit = _ta_unit(_at(toks, i + 1))
    if unit is None or unit == DAY:
        return None
    name = {WEEK: "week", MONTH: "month", YEAR: "year"}[unit]
    if t in TAMIL["last"]:
        return 2, _Hit(START, f"ta.last_{name}", _period_start(today, unit, 1), unit)
    if t in TAMIL["this"]:
        return 2, _Hit(START, f"ta.this_{name}", _period_start(today, unit, 0), unit)
    if t in TAMIL["next"]:
        return 2, _Hit(FUTURE, f"ta.next_{name}")
    return None


def _ta_ago(toks: list[str], i: int, today: date) -> _Match:
    """N நாள் / வாரம் / மாசம் / வருஷம் முன் ("3 naal munnadi")."""
    n = _number(toks[i])
    unit = _ta_unit(_at(toks, i + 1))
    if n is None or unit is None or _at(toks, i + 2) not in TAMIL["ago"]:
        return None
    return 3, _Hit(START, f"ta.{unit}s_ago", _ago(today, unit, n), unit)


def _ta_since(toks: list[str], i: int, today: date) -> _Match:
    """2019 முதல் / 2019-ல / 2019 la irundhu; March la / மார்ச் மாதம் முதல்."""
    year = _year(toks[i])
    if year is not None and _at(toks, i + 1) in TAMIL["since"]:
        end = i + 2
        while _at(toks, end) in TAMIL["since"] or _at(toks, end) in TAMIL["year"]:
            end += 1
        return end - i, _dated("ta.year", date(year, 1, 1), YEAR, today)
    month = MONTHS.get(toks[i])
    if month is None:
        return None
    j = i + 1
    if _at(toks, j) in TAMIL["month"]:
        j += 1
    if _at(toks, j) in TAMIL["since"] or j > i + 1:
        return j + 1 - i, _Hit(START, "ta.month", _past_month(today, month), MONTH)
    return None


def _seen(toks: list[str], i: int, today: date) -> _Match:
    """A time the rules cannot place: a weekday, "recently", a festival, "by …"."""
    t = toks[i]
    if t == "by" and (_at(toks, i + 1) in WEEKDAYS or _at(toks, i + 1) in ("end", "next")):
        return 2, _Hit(FUTURE, "en.by")
    if t in WEEKDAYS:
        return 1, _Hit(SEEN, "weekday")
    if t in VAGUE:
        return 1, _Hit(SEEN, "vague")
    if t in ("these", "the") and _at(toks, i + 1) in ("days", "other"):
        return 2, _Hit(SEEN, "vague")
    return None


#: Longest phrases first, so "day before yesterday" is not read as "yesterday".
_MATCHERS: tuple[_Matcher, ...] = (
    _en_relative,
    _en_period,
    _en_ago,
    _en_date,
    _en_prep,
    _ta_word,
    _ta_period,
    _ta_ago,
    _ta_since,
    _seen,
)


def _numeric_dates(text: str, today: date) -> tuple[list[_Hit], str]:
    """ISO and d/m/yyyy dates in *text*, and *text* with them blanked out."""
    hits: list[_Hit] = []

    def iso(m: re.Match[str]) -> str:
        found = _make_day(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        hits.append(_dated("date", found, DAY, today) if found else _Hit(SEEN, "date"))
        return " "

    def dmy(m: re.Match[str]) -> str:
        a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        day, month = (b, a) if b > 12 >= a else (a, b)  # day first unless clearly second
        found = _make_day(year, month, day)
        hits.append(_dated("date", found, DAY, today) if found else _Hit(SEEN, "date"))
        return " "

    rest = _DMY.sub(dmy, _ISO.sub(iso, text or ""))
    return hits, rest


def _hits(text: str, today: date) -> list[_Hit]:
    """Every time phrase in *text*, left to right, longest first."""
    hits, rest = _numeric_dates(text, today)
    toks = tokens(rest)
    i = 0
    while i < len(toks):
        for matcher in _MATCHERS:
            found = matcher(toks, i, today)
            if found is not None:
                i += found[0]
                hits.append(found[1])
                break
        else:
            i += 1
    return hits


# ── Public API ────────────────────────────────────────────────


def _local_day(anchor: datetime, tz: tzinfo) -> date:
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    return anchor.astimezone(tz).date()


def _result(hit: _Hit, tz: tzinfo, source: str) -> WorldTime:
    assert hit.day is not None and hit.precision is not None
    return WorldTime(
        datetime.combine(hit.day, time(0, 0), tzinfo=tz), hit.precision, hit.rule, source
    )


def phrase_count(text: str, anchor: datetime | None = None, tz: tzinfo = UTC) -> int:
    """How many time phrases *text* holds, placeable or not (future ones included)."""
    today = _local_day(anchor or datetime.now(UTC), tz)
    return len(_hits(text, today))


def find(
    text: str, anchor: datetime, tz: tzinfo = UTC, *, source: str = CONTENT
) -> WorldTime | None:
    """The start *text* gives a fact said at *anchor*, or None for unknown.

    None when the text is blocked (:func:`blocked`), holds a future phrase, or
    names two different starts.
    """
    if not text or blocked(text):
        return None
    hits = _hits(text, _local_day(anchor, tz))
    if any(h.kind == FUTURE for h in hits):
        return None
    starts = {(h.day, h.precision): h for h in hits if h.kind == START}
    if len(starts) != 1:
        return None
    return _result(next(iter(starts.values())), tz, source)


def world_time_of(
    content: str, source_text: str | None, anchor: datetime, tz: tzinfo = UTC
) -> WorldTime | None:
    """The start of one extracted fact (ADR §5.1, steps 1 and 2).

    1. The fact's content, the model's English sentence.
    2. The owner's own words (*source_text*, which may be Tamil or Tanglish),
       only when they hold exactly one time phrase, so a date is never pinned
       on the wrong fact of a multi-fact message.

    A content that is blocked (a plan, hedged, negated) stops here: the
    owner's words are not read to overrule it.
    """
    if content and blocked(content):
        return None
    found = find(content, anchor, tz, source=CONTENT)
    if found is not None or not source_text:
        return found
    if any(h.kind in (START, FUTURE) for h in _hits(content, _local_day(anchor, tz))):
        return None  # the content names a plan or two starts: the owner's words cannot settle it
    if phrase_count(source_text, anchor, tz) != 1:
        return None
    return find(source_text, anchor, tz, source=SOURCE_TEXT)


def from_model(value: object, text: str, anchor: datetime, tz: tzinfo = UTC) -> WorldTime | None:
    """A start date the local model proposed, checked (ADR §5.1, step 3).

    Kept only when it is a YYYY-MM-DD date (as ``llm._validity`` checks
    ``valid_until``), not after the day it was said, and *text* has a time
    phrase the rules can see, even one they cannot place ("last Pongal").
    A blocked text, or a bare date with no phrase, gives None. Call it only
    when :func:`world_time_of` found nothing.
    """
    if not isinstance(value, str) or not text or blocked(text):
        return None
    try:
        day = date.fromisoformat(value.strip())
    except ValueError:
        return None
    today = _local_day(anchor, tz)
    hits = _hits(text, today)
    if day > today or not hits or any(h.kind == FUTURE for h in hits):
        return None
    return WorldTime(datetime.combine(day, time(0, 0), tzinfo=tz), DAY, "model", MODEL)
