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
synonyms) and anything that is not ``topic.field`` is refused.
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
    "family": {"wife": "spouse", "husband": "spouse", "partner": "spouse"},
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
}


def plausible(key: str, content: str) -> bool:
    """Whether *content* can fill *key*: for the fields in _PLAUSIBLE, the sentence
    must say something of that kind. Other fields are not checked."""
    field = key.rsplit(".", 1)[-1]
    pattern = _PLAUSIBLE.get(field)
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
