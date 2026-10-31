"""Slots: the owner's facts that have one current value, i.e. the owner's form.

A slot is a short key, ``topic.field`` (``work.employer``, ``home.city``,
``devices.phone``, ``family.anu.school``), put on a memory by extraction. The
form is simply the active memories that carry a slot (services/profile_card.py),
and a new value for a slot replaces the old one (core/memory_manager.py), which
stays as history (superseded). Chosen 2026-10-31 after the memory bake-off:
notes + this form answered 78.6% of the big test against 64.3% for notes alone,
and kept the latest value where notes alone returned stale ones.

Fixed topics, free fields: the connections method's free relation names grew to
129 on the bake-off's big test, so field names are normalised here (aliases and
synonyms) and anything that is not ``topic.field`` is refused. A hobby is always
``hobbies.<activity>.<field>`` with a fixed field (:data:`HOBBY_FIELDS`), so a
changed day or club replaces the old value (2026-10-31: ``hobbies.cricket_day``
and ``hobbies.cricket.day`` both stayed current). A family member's name in a
slot is mapped to the name they are known by in services/entities.py
(``entities.canonical_slot``): "Maha" and "Mahalakshmi" are one person's fields.
"""

from __future__ import annotations

import re

TOPICS = (
    "basics",
    "home",
    "family",
    "work",
    "projects",
    "hobbies",
    "devices",
    "vehicles",
    "money",
    "health",
    "learning",
    "travel",
)

#: Other names models use for a topic.
TOPIC_ALIASES = {
    "personal": "basics",
    "identity": "basics",
    "profile": "basics",
    "self": "basics",
    "residence": "home",
    "location": "home",
    "address": "home",
    "living": "home",
    "family_members": "family",
    "relatives": "family",
    "kids": "family",
    "children": "family",
    "job": "work",
    "career": "work",
    "employment": "work",
    "office": "work",
    "project": "projects",
    "side_project": "projects",
    "hobby": "hobbies",
    "sports": "hobbies",
    "interests": "hobbies",
    "device": "devices",
    "gadgets": "devices",
    "tech": "devices",
    "phone": "devices",
    "vehicle": "vehicles",
    "car": "vehicles",
    "transport": "vehicles",
    "finance": "money",
    "finances": "money",
    "financial": "money",
    "investments": "money",
    "medical": "health",
    "fitness": "health",
    "education": "learning",
    "study": "learning",
    "skills": "learning",
    "trip": "travel",
    "trips": "travel",
    "vacation": "travel",
}

#: Other names models use for the same field (per topic, after the alias above).
FIELD_SYNONYMS = {
    "work": {
        "company": "employer",
        "organisation": "employer",
        "organization": "employer",
        "employer_name": "employer",
        "current_employer": "employer",
        "workplace": "employer",
        "job_title": "title",
        "role": "title",
        "position": "title",
        "designation": "title",
        "boss": "manager",
        "manager_name": "manager",
        "current_manager": "manager",
    },
    "home": {
        "city_name": "city",
        "current_city": "city",
        "residence": "city",
        "location": "city",
        "neighbourhood": "area",
        "neighborhood": "area",
        "locality": "area",
        "suburb": "area",
    },
    "family": {
        "wife": "spouse",
        "husband": "spouse",
        "partner": "spouse",
        "mom": "mother",
        "mum": "mother",
        "amma": "mother",
        "dad": "father",
        "appa": "father",
        "dob": "birthday",
        "date_of_birth": "birthday",
        "bday": "birthday",
        "birth_date": "birthday",
    },
    "devices": {
        "mobile": "phone",
        "smartphone": "phone",
        "mobile_phone": "phone",
        "cellphone": "phone",
        "computer": "laptop",
        "work_laptop": "laptop",
    },
    "money": {
        "monthly_budget": "budget",
        "household_budget": "budget",
        "monthly_household_budget": "budget",
        "sip_amount": "sip",
        "monthly_sip": "sip",
    },
    "health": {"blood_type": "blood_group", "bloodgroup": "blood_group"},
}

_SEGMENT = re.compile(r"[a-z0-9_]+")

#: A hobby's fields: every hobby slot is ``hobbies.<activity>.<field>`` with one of
#: these fields, so a changed day or club replaces the old one instead of landing
#: in a new slot beside it (``hobbies.cricket_day`` then ``hobbies.cricket.day``,
#: ``hobbies.badminton_club`` then ``hobbies.club``: both stayed current).
#: Only spellings of ONE field collapse: a practice day, a match day and a club's
#: day are different facts (review of PR #205: "matches are on Sundays" replaced
#: "practice is on Tuesdays"). A hobby taken as a class has the class as its day.
HOBBY_FIELDS = {
    "day": "day",
    "days": "day",
    "weekday": "day",
    "weekdays": "day",
    "play_day": "day",
    "playing_day": "day",
    "class_day": "day",
    "schedule": "day",
    "when": "day",
    "practice_day": "practice_day",
    "practice_days": "practice_day",
    "training_day": "practice_day",
    "training_days": "practice_day",
    "nets_day": "practice_day",
    "match_day": "match_day",
    "match_days": "match_day",
    "matchday": "match_day",
    "game_day": "match_day",
    "game_days": "match_day",
    "fixture_day": "match_day",
    "time": "time",
    "timing": "time",
    "timings": "time",
    "play_time": "time",
    "session_time": "time",
    "class_time": "time",
    "practice_time": "practice_time",
    "training_time": "practice_time",
    "match_time": "match_time",
    "game_time": "match_time",
    "club": "club",
    "club_name": "club",
    "team": "club",
    "team_name": "club",
    "group": "club",
    "academy": "club",
    "coach": "coach",
    "coach_name": "coach",
    "trainer": "coach",
    "teacher": "coach",
    "instructor": "coach",
    "guru": "coach",
    "master": "coach",
    "place": "place",
    "venue": "place",
    "ground": "place",
    "court": "place",
    "location": "place",
    "pool": "place",
    "role": "role",
    "position": "role",
    "batting_position": "role",
}
#: Activities recognised in a sentence, for a slot that names none (``hobbies.club``).
ACTIVITIES = (
    "cricket",
    "badminton",
    "table_tennis",
    "tennis",
    "football",
    "basketball",
    "volleyball",
    "hockey",
    "kabaddi",
    "chess",
    "swimming",
    "yoga",
    "running",
    "cycling",
    "gym",
    "karate",
    "boxing",
    "golf",
    "squash",
    "pickleball",
    "trekking",
    "hiking",
    "veena",
    "guitar",
    "piano",
    "violin",
    "flute",
    "singing",
    "dance",
    "bharatanatyam",
    "painting",
    "drawing",
    "photography",
    "meditation",
)
ACTIVITY_SYNONYMS = {
    "soccer": "football",
    "shuttle": "badminton",
    "shuttlecock": "badminton",
    "ping_pong": "table_tennis",
    "tt": "table_tennis",
    "swim": "swimming",
    "run": "running",
    "jogging": "running",
    "cycle": "cycling",
    "workout": "gym",
    "dancing": "dance",
}
_ACTIVITY_PREFIX = re.compile(r"^(?:playing|play|plays|learning|weekly|my|owner)_")
#: The fields of a family member: ``family.anu_school`` is ``family.anu.school``.
FAMILY_FIELDS = frozenset(
    {
        "school",
        "class",
        "grade",
        "birthday",
        "age",
        "city",
        "spouse",
        "phone",
        "employer",
        "college",
        "doctor",
        "medicine",
        "blood_group",
        "health",
        "job",
        "title",
    }
)


def _activity(segment: str) -> str:
    segment = _ACTIVITY_PREFIX.sub("", segment)
    return ACTIVITY_SYNONYMS.get(segment, segment)


def _activity_in(content: str) -> str | None:
    """The one activity *content* names, else None (none, or more than one)."""
    text = " " + re.sub(r"[^a-z]+", " ", content.lower()) + " "
    found = []
    for act in ACTIVITIES:
        if f" {act.replace('_', ' ')} " in text and not any(act in f for f in found):
            found.append(act)
    for word, act in ACTIVITY_SYNONYMS.items():
        if f" {word.replace('_', ' ')} " in text and act not in found:
            found.append(act)
    return found[0] if len(found) == 1 else None


def _split_field(segment: str, fields) -> tuple[str, str] | None:
    """``cricket_day`` → (cricket, day), ``day_cricket`` → (cricket, day), else None."""
    bits = segment.split("_")
    for i in range(1, len(bits)):
        head, tail = "_".join(bits[:i]), "_".join(bits[i:])
        if tail in fields and head not in fields:
            return head, tail
    for i in range(len(bits) - 1, 0, -1):
        head, tail = "_".join(bits[:i]), "_".join(bits[i:])
        if head in fields and tail not in fields:
            return tail, head
    return None


#: Words that say which of a hobby's events a field is about ("practice" day,
#: "match" time): kept in the field, never dropped.
_HOBBY_QUALIFIERS = {
    "practice": "practice",
    "training": "practice",
    "nets": "practice",
    "match": "match",
    "matches": "match",
    "game": "match",
    "games": "match",
    "fixture": "match",
    "tournament": "tournament",
    "class": "class",
    "classes": "class",
    "lesson": "class",
    "lessons": "class",
    "session": "session",
    "sessions": "session",
    "coaching": "coaching",
}
#: Words that add nothing to a field: ``club.name`` is the club.
_HOBBY_FILLER = frozenset({"name", "names", "value", "info", "details", "detail"})


def _hobby_field(parts: list[str]) -> str | None:
    """The one field *parts* spell (``["club", "day"]`` → ``club_day``,
    ``["practice", "day"]`` → ``practice_day``, ``["club", "name"]`` → ``club``),
    or None unless every word is a field word, a qualifier or filler and at
    least one is a field word. Nothing that qualifies the field is dropped."""
    whole = "_".join(parts)
    if whole in HOBBY_FIELDS:
        return HOBBY_FIELDS[whole]
    words: list[str] = []
    has_field = False
    for bit in (b for p in parts for b in p.split("_") if b):
        if bit in _HOBBY_FILLER:
            continue
        if bit in HOBBY_FIELDS:
            words.append(HOBBY_FIELDS[bit])
            has_field = True
        elif bit in _HOBBY_QUALIFIERS:
            words.append(_HOBBY_QUALIFIERS[bit])
        else:
            return None
    if not has_field:
        return None
    joined = "_".join(dict.fromkeys(words))
    return HOBBY_FIELDS.get(joined, joined)


def _split_hobby(segment: str) -> tuple[str, str] | None:
    """``cricket_day`` → (cricket, day), ``chess_club_day`` → (chess, club_day),
    ``day_cricket`` → (cricket, day); None when no part of it is a field."""
    bits = segment.split("_")
    for i in range(1, len(bits)):
        head, tail = "_".join(bits[:i]), "_".join(bits[i:])
        if bits[0] in _HOBBY_QUALIFIERS or _hobby_field([head]):
            break
        field = _hobby_field([tail])
        if field:
            return head, field
    for i in range(len(bits) - 1, 0, -1):
        head, tail = "_".join(bits[:i]), "_".join(bits[i:])
        field = _hobby_field([head])
        if field and not _hobby_field([tail]):
            return tail, field
    return None


def _hobby(fields: list[str], content: str) -> list[str] | None:
    """A hobby slot's fields as ``[activity, field]`` (or ``[activity]``); None when
    it names a field but no activity and the sentence does not name exactly one.
    An unknown field is kept as written (``hobbies.cricket.favourite.player``)."""
    field = _hobby_field(fields)
    if field:
        # hobbies.club.name, hobbies.practice_day: a field with no activity
        act = _activity_in(content) if content else None
        return [act, field] if act else None
    if len(fields) > 1 and _hobby_field([fields[0]]) and not _hobby_field([fields[1]]):
        # hobbies.day.cricket
        fields = [fields[1], fields[0], *fields[2:]]
    act, rest = fields[0], fields[1:]
    split = _split_hobby(act)
    if split:
        # hobbies.cricket_day, hobbies.cricket_club.name
        act, rest = split[0], [split[1], *rest]
    if not rest:
        return [_activity(act)]
    field = _hobby_field(rest)
    if field is None and any(_hobby_field([p]) for p in rest):
        # hobbies.chess.blitz.day: a field with an unknown qualifier, kept whole
        field = "_".join(rest)
    return [_activity(act), field] if field else [_activity(act), *rest]


def _clean(segment: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[\s\-/]+", "_", segment.strip().lower())).strip("_")


#: A ``home.*`` slot is where the OWNER lives. Measured 2026-10-31: "my parents
#: live in Madurai" came back as home.city, which would have replaced the
#: owner's own city; the sentence must say the owner lives or moved there.
_OWNER_HOME = re.compile(
    r"\b(?:owner|user)\b(?!'s)[^.]{0,40}\b(?:live[sd]?|living|moved|stay(?:s|ed)?|reside[sd]?|home)\b",
    re.IGNORECASE,
)


#: The words a sentence must contain to fill a field whose wrong value does harm:
#: a value in one of these replaces the old one. Measured 2026-10-31: the local
#: model gave "mediagrab is accessible only through tailscale" the slot
#: work.employer, which would have replaced the owner's real employer.
_PLAUSIBLE = {
    "employer": r"\b(?:work|works|worked|working|job|employ\w*|compan\w+|joined|join|office|firm|startup|organi[sz]ation)\b",
    "title": r"\b(?:title|role|position|engineer|manager|lead|developer|designer|ceo|cto|founder|head|director|analyst|consultant|intern|job)\b",
    "manager": r"\b(?:manager|boss|reports? to|lead|supervisor)\b",
    "city": r"\b(?:live[sd]?|living|moved|city|town|home|stay\w*|reside\w*)\b",
    "area": r"\b(?:live[sd]?|living|moved|area|home|neighbou?rhood|stay\w*)\b",
    "phone": r"\b(?:phone|mobile|pixel|iphone|galaxy|oneplus|realme|redmi|xiaomi|nokia|moto\w*|vivo|oppo|smartphone)\b",
    "laptop": r"\b(?:laptop|thinkpad|macbook|notebook|computer|pc|dell|lenovo|hp|asus|acer)\b",
    "car": r"\b(?:car|drive[sn]?|suv|sedan|hatchback|vehicle|creta|nexon|swift|city|innova)\b",
    "spouse": r"\b(?:wife|husband|spouse|married|partner)\b",
    "budget": r"\b(?:budget|spend\w*|per month|a month|monthly|rupees|rs\.?|₹)",
    "sip": r"\b(?:sip|invest\w*|mutual fund|index fund|per month|a month|monthly)\b",
    "blood_group": r"\bblood\b",
    "school": r"\b(?:school|class|grade|studies|study|kindergarten|college|vidyashram|academy)\b",
    "birthday": r"\b(?:birthday|born|birth)\b",
    # A hobby's day: a changed day replaces the old one, so the sentence must name one.
    "day": r"\b(?:(?:mon|tues|wednes|thurs|fri|satur|sun)days?|weekends?|weekdays?|daily|every)\b",
}


def plausible(key: str, content: str) -> bool:
    """Whether *content* can fill *key*: for the fields in _PLAUSIBLE, the sentence
    must say something of that kind. Other fields are not checked."""
    field = key.rsplit(".", 1)[-1]
    pattern = _PLAUSIBLE.get(field)
    if pattern is None and key.startswith("hobbies.") and field.endswith("_day"):
        pattern = _PLAUSIBLE["day"]  # a practice, match or club day
    return pattern is None or re.search(pattern, content, re.IGNORECASE) is not None


def normalise(raw: str | None, *, subject: str = "owner", content: str = "") -> str | None:
    """The canonical slot key, or None when *raw* is not a usable slot.

    ``topic.field`` with 2-4 segments of ``[a-z0-9_]``, topic one of TOPICS
    (aliases mapped), the field's synonyms mapped. A fact about someone else
    gets a slot only under ``family`` (a child's school, a parent's medicine):
    a colleague's phone is never the owner's ``devices.phone``.
    """
    if not raw or not isinstance(raw, str):
        return None
    parts = [_clean(p) for p in raw.split(".") if p.strip()]
    if not 2 <= len(parts) <= 4 or not all(_SEGMENT.fullmatch(p) for p in parts):
        return None
    topic = TOPIC_ALIASES.get(parts[0], parts[0])
    if topic not in TOPICS:
        return None
    synonyms = FIELD_SYNONYMS.get(topic, {})
    fields = [synonyms.get(p, p) for p in parts[1:]]
    if topic == "hobbies":
        hobby = _hobby(fields, content)
        if not hobby:
            return None
        fields = hobby
    elif topic == "family" and len(fields) == 1 and fields[0] not in FAMILY_FIELDS:
        # family.anu_school: one person's field written as one segment
        split = _split_field(fields[0], FAMILY_FIELDS)
        if split:
            fields = [split[0], split[1]]
    if subject and subject.lower() != "owner":
        # Someone else's fact: only under family, and always under their name, so
        # "Divya is married to Naveen" is family.divya.spouse, never the owner's
        # family.spouse (measured 2026-10-31).
        if topic != "family":
            return None
        who = _clean(subject)
        if not _SEGMENT.fullmatch(who):
            return None
        if fields[0] != who:
            fields = [who, *fields]
        if len(fields) > 3:
            return None
    if topic == "home" and content and not _OWNER_HOME.search(content):
        return None
    key = ".".join([topic, *fields])[:80]
    if content and not plausible(key, content):
        return None
    return key


def topic_of(key: str) -> str:
    return key.split(".", 1)[0]


def label(key: str) -> str:
    """``family.anu.school`` → ``family · anu · school`` for the prompt."""
    return " · ".join(key.split("."))
