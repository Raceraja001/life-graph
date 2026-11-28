"""services/tamil_decisions.py: Tamil and Tanglish decision candidates, by rule.

Candidates only (the owner confirms, #436), and only for the owner's own words:
the capture spine asks ``_detect_decisions`` behind ``_is_self`` (#430).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.services import tamil_decisions
from life_graph.services.capture_processors import CaptureProcessors

DECIDED = [
    # Tamil script, first-person "did / took", with case endings on the nouns
    "Kafka-வுக்குப் பதிலாக Postgres வரிசையைப் பயன்படுத்த முடிவு செய்தோம்.",
    "பழைய ஸ்கூட்டரை விற்க முடிவு பண்ணிட்டேன்.",
    "அடுத்த மாசம் சென்னைக்கு வீடு மாற முடிவு எடுத்தோம்.",
    "வேலையை விட முடிவை எடுத்துட்டேன்.",
    # Tanglish
    "Postgres queue use pannalaam nu decide panniten.",
    "Firebase-ku pathila Supabase use pannalaam nu decide panninom.",
    "Pudhu car vaangura mudiva eduthen.",
    "Gym membership cancel panna decision eduthom.",
    "Vendor-a finalize pannitom.",
    # it is decided; "X venaam nu mudivu"; "X venaam, Y -laam"
    "School fees-a quarterly-a kattalaam, mudivaachu.",
    "Netflix subscription venaam nu mudivu.",
    "Swiggy-la order வேண்டாம்னு முடிவு.",
    "Kafka venaam, Postgres queue-ve pogalaam.",
]

NOT_DECIDED = [
    # questions, with and without a question mark
    "enna decide pannalam?",
    "எந்த bank-ல loan எடுக்கலாம்னு என்ன முடிவு பண்ணோம்",
    "Kafka venaam, Postgres pogalaamaa?",
    "Ethu use panna decide panninom",
    # hypotheticals and hedges
    "Oruvela Kafka venaam nu decide pannina, Postgres pogalaam.",
    "Maybe Postgres use panna decide panniten.",
    "முடிவு செய்தேன் என்று நினைக்கிறேன்.",
    # reported speech about others
    "Ravi avanga team Postgres use panna decide pannitaanga nu sonnaan.",
    "அவங்க ஆபீஸை மாத்த முடிவு செய்ததா மேனேஜர் சொன்னார்.",
    "Manager office maatha decide panninom nu sonnaar.",
    # let's decide, will decide, did not decide, they decided
    "Naalaiku meeting-la decide pannalaam.",
    "அடுத்த வாரம் முடிவு செய்வோம்.",
    "Innum car pathi decide pannala.",
    "முடிவு பண்ணல இன்னும் இல்லை.",
    "Avanga Postgres use panna decide pannitaanga.",
    # முடிவு is also "the end"; "ellaam" is "all"
    "படத்தோட முடிவு எனக்கு பிடிக்கல.",
    "Kafka venaam, ellaam.",
    # plain text, English
    "Indha weekend Ooty pogalaam.",
    "The weather is nice today.",
]


@pytest.mark.parametrize("text", DECIDED)
def test_a_decision_in_tamil_or_tanglish_is_a_candidate(text):
    assert tamil_decisions.detect(text) == [text.rstrip(".")]


@pytest.mark.parametrize("text", NOT_DECIDED)
def test_questions_hypotheticals_reports_and_others_are_not(text):
    assert tamil_decisions.detect(text) == []


def test_each_sentence_is_judged_on_its_own():
    text = "enna decide pannalam? Postgres use panna decide panninom. Ravi sonnaan."
    assert tamil_decisions.detect(text) == ["Postgres use panna decide panninom"]


def test_the_capture_spine_adds_them_to_the_english_candidates():
    text = "We decided to use FastAPI for the backend.\nPostgres use panna decide panninom."
    assert CaptureProcessors._detect_decisions(text) == [
        "use FastAPI for the backend",
        "Postgres use panna decide panninom",
    ]


def test_english_text_gives_the_same_candidates_as_before():
    # "decide" without a Tanglish "did" verb never fires the Tamil rules.
    assert tamil_decisions.detect("We decided to use FastAPI. I decided to go home.") == []


@pytest.mark.parametrize(
    ("surface", "tier", "is_self"),
    [("chat", None, True), ("voice", None, True), ("email", None, False)]
    + [("whatsapp", None, False), ("mcp", None, False), ("telegram", "external", False)],
)
def test_only_the_owners_own_words_reach_detection(surface, tier, is_self):
    """The SELF gate (#430) the capture spine puts before ``_detect_decisions``."""
    evt = SimpleNamespace(surface=surface, trust_tier=tier)
    assert CaptureProcessors._is_self(evt) is is_self
