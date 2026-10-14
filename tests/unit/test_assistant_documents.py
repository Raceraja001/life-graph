"""Phase B: documents vault — field extraction, reminders, brief line."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from life_graph.models.assistant import Document
from life_graph.services import documents

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)

PASSPORT_OCR = """REPUBLIC OF INDIA
PASSPORT
Type P  Country Code IND  Passport No. Z1234567
Surname KUMAR  Given Names RAJA
Date of Issue 12/03/2017
Date of Expiry 11/03/2027
Place of Issue CHENNAI"""


def test_dates_come_from_the_text_when_the_model_gives_none():
    fields = documents.fields_from(PASSPORT_OCR, None, NOW)
    assert fields["kind"] == "passport"
    assert fields["expires_on"] == date(2027, 3, 11)
    assert fields["issued_on"] == date(2017, 3, 12)
    assert fields["number_last4"] is None  # nothing model-read, nothing stored


def test_model_fields_are_merged_and_the_number_is_cut_to_four():
    model = {
        "kind": "passport",
        "title": "Indian passport",
        "issuer": "Government of India",
        "holder": "Raja Kumar",
        "number": "Z1234567",
        "issued": "12/03/2017",
        "expires": "11/03/2027",
    }
    fields = documents.fields_from(PASSPORT_OCR, model, NOW)
    assert fields["title"] == "Indian passport"
    assert fields["number_last4"] == "4567"
    assert "Z1234567" not in json.dumps(fields, default=str)


def test_swapped_dates_are_put_right():
    fields = documents.fields_from(
        "", {"kind": "warranty", "issued": "2028-01-01", "expires": "2026-01-01"}, NOW
    )
    assert fields["issued_on"] < fields["expires_on"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Car insurance policy\nPolicy expiry: 12 Mar 2027", date(2027, 3, 12)),
        ("Warranty valid till 2028-06-30", date(2028, 6, 30)),
        ("Renewal due 05-11-2026", date(2026, 11, 5)),
    ],
)
def test_expiry_keyword_forms(text, expected):
    assert documents.fields_from(text, None, NOW)["expires_on"] == expected


@pytest.mark.parametrize(
    ("number", "expected"), [("Z1234567", "4567"), ("ab-12 34", "1234"), ("12", None), (None, None)]
)
def test_last4(number, expected):
    assert documents.last4(number) == expected


def _doc(expires: date | None, sent: list | None = None) -> Document:
    return Document(
        tenant_id="t",
        kind="passport",
        title="Passport",
        expires_on=expires,
        reminders_sent=sent or [],
    )


def test_one_reminder_per_threshold_and_the_nearest_one_wins():
    today = date(2026, 10, 14)
    assert documents.due_reminder(_doc(date(2027, 3, 1)), today) is None  # > 60 days
    assert documents.due_reminder(_doc(date(2026, 12, 1)), today) == "60"
    assert documents.due_reminder(_doc(date(2026, 12, 1), ["60"]), today) is None
    # Filed 5 days before expiry: one "7" reminder, not 60 + 30 + 7.
    assert documents.due_reminder(_doc(date(2026, 10, 19)), today) == "7"
    assert documents.due_reminder(_doc(date(2026, 10, 10)), today) == "expired"
    assert documents.due_reminder(_doc(date(2026, 10, 10), ["expired"]), today) is None
    assert documents.due_reminder(_doc(None), today) is None


def test_brief_line_names_kinds_and_days_only():
    today = date(2026, 10, 14)
    docs = [_doc(date(2026, 10, 30)), _doc(date(2026, 10, 1)), _doc(date(2027, 1, 1))]
    docs[0].number_last4 = "4567"
    line = documents.brief_line(docs, today)
    assert line == "Documents: passport in 16d, passport expired"
    assert documents.brief_line([_doc(date(2027, 6, 1))], today) is None


class _FakeLM:
    def __init__(self, reply):
        self.reply = reply

    async def chat_local_only(self, **_kw):
        return self.reply


@pytest.mark.asyncio
async def test_extract_survives_a_broken_model():
    fields = await documents.extract(PASSPORT_OCR, client=_FakeLM("not json"), now=NOW)
    assert fields["kind"] == "passport" and fields["expires_on"] == date(2027, 3, 11)
