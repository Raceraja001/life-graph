"""A small vCard (2.1, 3.0, 4.0) reader for contact exports.

Enough of RFC 6350 / RFC 2426 / vCard 2.1 for what address books export:
folded lines, ``group.`` prefixes, parameters, backslash escapes,
quoted-printable values (2.1), and the properties Life Graph keeps. Photos and
everything else are skipped. Nothing here opens files or the network: it turns
text into ``Item``s.
"""

from __future__ import annotations

import hashlib
import quopri
import re
from datetime import UTC, datetime

from life_graph.connectors.base import ConnectorError, Item
from plugins.contacts.common import Person, to_item

MAX_CONTACTS = 20_000
_KEEP = frozenset(
    {"FN", "N", "EMAIL", "TEL", "ORG", "TITLE", "BDAY", "ADR", "NOTE", "UID", "REV"}
    | {"CATEGORIES", "X-ABRELATEDNAMES", "RELATED"}
)


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in re.split(r"\r\n|\r|\n", text):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _split_unescaped(value: str, sep: str) -> list[str]:
    parts, cur, i = [], [], 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            cur.append(value[i : i + 2])
            i += 2
            continue
        if ch == sep:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value).strip()


def _parse_line(line: str) -> tuple[str, dict[str, list[str]], str] | None:
    """``[group.]NAME;P=V;FLAG:value`` → (NAME, params, raw value)."""
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            head, value = line[:i], line[i + 1 :]
            break
    else:
        return None
    pieces = head.split(";")
    name = pieces[0].rsplit(".", 1)[-1].upper()
    params: dict[str, list[str]] = {}
    for p in pieces[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params.setdefault(k.upper(), []).extend(x.strip('"') for x in v.split(","))
        else:  # vCard 2.1 bare type: TEL;CELL;PREF
            params.setdefault("TYPE", []).append(p)
    return name, params, value


def _decode(params: dict[str, list[str]], value: str) -> str:
    encoding = [e.upper() for e in params.get("ENCODING", [])]
    if "QUOTED-PRINTABLE" in encoding:
        charset = (params.get("CHARSET") or ["utf-8"])[0]
        try:
            return quopri.decodestring(value.encode("latin-1", "replace")).decode(
                charset, "replace"
            )
        except LookupError:
            return quopri.decodestring(value.encode("latin-1", "replace")).decode(
                "utf-8", "replace"
            )
    return value


def _types(params: dict[str, list[str]]) -> str:
    kinds = [
        t.lower()
        for t in params.get("TYPE", [])
        if t.upper() not in ("PREF", "INTERNET", "VOICE", "X400")
    ]
    return kinds[0] if kinds else ""


def _birthday(value: str) -> tuple[int | None, int | None, int | None]:
    """1990-03-14, 19900314, --0314, --03-14, 1990-03-14T00:00:00Z → (y, m, d)."""
    digits = value.strip().split("T", 1)[0]
    m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", digits)
    if m:
        year = int(m.group(1))
        # Apple and Google write year 1604 / 0000 for "no year".
        return (year if year > 1800 else None), int(m.group(2)), int(m.group(3))
    m = re.fullmatch(r"--(\d{2})-?(\d{2})", digits)
    if m:
        return None, int(m.group(1)), int(m.group(2))
    return None, None, None


def _updated(value: str) -> datetime | None:
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _person(props: list[tuple[str, dict[str, list[str]], str]]) -> Person:
    p = Person(external_id="")
    uid = ""
    n_name = ""
    for name, params, raw in props:
        value = _decode(params, raw)
        if name == "FN":
            p.name = _unescape(value)
        elif name == "N":
            parts = [_unescape(x) for x in _split_unescaped(value, ";")] + [""] * 5
            family, given, middle, prefix, suffix = parts[:5]
            n_name = " ".join(x for x in (prefix, given, middle, family, suffix) if x)
        elif name == "EMAIL":
            p.emails.append(_unescape(value))
        elif name == "TEL":
            kind = _types(params)
            number = _unescape(value).removeprefix("tel:")
            p.phones.append(f"{number} ({kind})" if kind else number)
        elif name == "ORG":
            parts = [_unescape(x) for x in _split_unescaped(value, ";") if x.strip()]
            p.org = ", ".join(parts) or None
        elif name == "TITLE":
            p.job_title = _unescape(value) or None
        elif name == "BDAY":
            p.birth_year, p.birth_month, p.birth_day = _birthday(value)
        elif name == "ADR":
            parts = [_unescape(x) for x in _split_unescaped(value, ";")]
            text = ", ".join(x for x in parts if x)
            if text:
                kind = _types(params)
                p.addresses.append(f"{text} ({kind})" if kind else text)
        elif name == "NOTE":
            p.notes = _unescape(value)
        elif name == "UID":
            uid = _unescape(value)
        elif name == "REV":
            p.updated = _updated(value)
        elif name == "CATEGORIES":
            cats = [_unescape(x) for x in _split_unescaped(value, ",")]
            p.groups.extend(c for c in cats if c and c.lower() not in ("mycontacts", "starred"))
            p.starred = p.starred or any(c.lower() == "starred" for c in cats)
        elif name in ("RELATED", "X-ABRELATEDNAMES"):
            rel = _unescape(value)
            kind = _types(params)
            if rel:
                p.relations.append(f"{rel} ({kind})" if kind else rel)
    p.name = p.name or n_name
    if uid:
        p.external_id = f"vcard:{uid}"[:512]
    else:
        basis = "|".join([p.name.lower(), *sorted(e.lower() for e in p.emails), *p.phones])
        p.external_id = "vcard:h:" + hashlib.sha256(basis.encode()).hexdigest()[:32]
    return p


def parse_vcards(text: str) -> list[Item]:
    """Every contact in a .vcf export. Raises ConnectorError for a non-vCard file."""
    if "BEGIN:VCARD" not in text.upper():
        raise ConnectorError("this is not a vCard (.vcf) file")
    items: list[Item] = []
    seen: set[str] = set()
    current: list[tuple[str, dict[str, list[str]], str]] | None = None
    lines = _unfold(text)
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        upper = line.strip().upper()
        if upper == "BEGIN:VCARD":
            current = []
            continue
        if upper == "END:VCARD":
            if current is not None:
                item = to_item(_person(current))
                if item and item.external_id not in seen:
                    seen.add(item.external_id)
                    items.append(item)
                    if len(items) >= MAX_CONTACTS:
                        break
            current = None
            continue
        if current is None or not line.strip():
            continue
        parsed = _parse_line(line)
        if parsed is None:
            continue
        name, params, value = parsed
        if "QUOTED-PRINTABLE" in [e.upper() for e in params.get("ENCODING", [])]:
            # 2.1 soft line breaks: a trailing '=' continues on the next line.
            while value.endswith("=") and i < len(lines):
                value = value[:-1] + lines[i]
                i += 1
        if name in _KEEP:
            current.append((name, params, value))
    return items
