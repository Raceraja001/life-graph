"""Money: transactions from statements and bank alerts, categories, budgets.

Phase C of docs/specs/assistant-capabilities.md. Nothing here moves money;
it reads what the user hands it.

- **Statement CSVs**: the header row is found (banks put several lines of
  preamble above it), then the date, description, debit, credit, amount and
  Dr/Cr columns are matched by name. Dates are day-first, as Indian banks
  write them.
- **Bank alerts** (SMS or app notification text pasted or forwarded): plain
  regular expressions for the amount, the direction, the merchant and the
  last four digits of the account. No model reads them.
- **Categories**: the user's own rules first (learned from corrections), then
  built-in merchant keywords, then, for what is left, the local model chooses
  from the fixed category list. Each transaction records which of the three
  decided.
- **Budgets**: a monthly limit per category; the daily sweep alerts once at
  80% and once at 100% of it in a month.

Re-importing an overlapping statement is harmless: a hash of date, amount,
direction, description and account is unique per tenant.

Amounts never leave the machine through the brief or a cloud model's tool
output: those see categories and percentages only.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from life_graph.config import settings
from life_graph.connectors.bills import parse_due
from life_graph.models.assistant import MoneyBudget, MoneyCategoryRule, MoneyTransaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CATEGORIES = (
    "food",
    "groceries",
    "transport",
    "fuel",
    "shopping",
    "utilities",
    "rent",
    "loans",
    "insurance",
    "health",
    "education",
    "entertainment",
    "subscriptions",
    "travel",
    "cash",
    "transfers",
    "fees",
    "investments",
    "income",
    "uncategorised",
)
ALERT_LEVELS = (80, 100)
MAX_MODEL_CATEGORISE = 40

_BUILTIN_RULES: tuple[tuple[str, str], ...] = (
    ("swiggy", "food"),
    ("zomato", "food"),
    ("restaurant", "food"),
    ("cafe", "food"),
    ("bigbasket", "groceries"),
    ("blinkit", "groceries"),
    ("zepto", "groceries"),
    ("dmart", "groceries"),
    ("supermarket", "groceries"),
    ("uber", "transport"),
    ("ola", "transport"),
    ("rapido", "transport"),
    ("metro", "transport"),
    ("irctc", "travel"),
    ("makemytrip", "travel"),
    ("indigo", "travel"),
    ("petrol", "fuel"),
    ("fuel", "fuel"),
    ("hpcl", "fuel"),
    ("bpcl", "fuel"),
    ("indian oil", "fuel"),
    ("amazon", "shopping"),
    ("flipkart", "shopping"),
    ("myntra", "shopping"),
    ("electricity", "utilities"),
    ("bescom", "utilities"),
    ("tneb", "utilities"),
    ("tangedco", "utilities"),
    ("airtel", "utilities"),
    ("jio", "utilities"),
    ("broadband", "utilities"),
    ("water", "utilities"),
    ("gas", "utilities"),
    ("rent", "rent"),
    ("emi", "loans"),
    ("loan", "loans"),
    ("insurance", "insurance"),
    ("lic", "insurance"),
    ("premium", "insurance"),
    ("pharmacy", "health"),
    ("apollo", "health"),
    ("hospital", "health"),
    ("clinic", "health"),
    ("school", "education"),
    ("tuition", "education"),
    ("udemy", "education"),
    ("netflix", "subscriptions"),
    ("spotify", "subscriptions"),
    ("prime", "subscriptions"),
    ("hotstar", "subscriptions"),
    ("youtube", "subscriptions"),
    ("bookmyshow", "entertainment"),
    ("pvr", "entertainment"),
    ("atm", "cash"),
    ("cash withdrawal", "cash"),
    ("salary", "income"),
    ("interest", "income"),
    ("refund", "income"),
    ("mutual fund", "investments"),
    ("zerodha", "investments"),
    ("groww", "investments"),
    ("sip", "investments"),
    ("charges", "fees"),
    ("gst on", "fees"),
    ("neft", "transfers"),
    ("imps", "transfers"),
)


@dataclass
class Txn:
    occurred_on: date
    amount: Decimal
    direction: str  # debit | credit
    description: str
    merchant: str | None = None
    account_last4: str | None = None
    currency: str = "INR"

    def dedup_hash(self, tenant_id: str) -> str:
        key = "|".join(
            [
                tenant_id,
                self.occurred_on.isoformat(),
                f"{self.amount:.2f}",
                self.direction,
                re.sub(r"\s+", " ", self.description.lower()).strip()[:80],
                self.account_last4 or "",
            ]
        )
        return hashlib.sha256(key.encode()).hexdigest()


# ── Parsing ─────────────────────────────────────────────────────────────────


def parse_amount(raw: str | None) -> Decimal | None:
    text = re.sub(r"[^\d.\-]", "", (raw or "").replace(",", ""))
    if text in ("", "-", ".", "-."):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value


def parse_day(raw: str | None, now: datetime | None = None) -> date | None:
    """A statement or alert date (day first: 05/10/2026 is 5 October)."""
    text = (raw or "").strip()
    if not text:
        return None
    # "12Oct26" / "12-OCT-2026" — split letters from digits for the month parser.
    text = re.sub(r"(\d)([A-Za-z])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)
    try:
        return parse_due(text, now or datetime.now(UTC))
    except Exception:  # noqa: BLE001
        return None


_HEADERS = {
    "date": ("txn date", "transaction date", "value date", "date", "posting date", "tran date"),
    "description": (
        "description",
        "narration",
        "particulars",
        "details",
        "remarks",
        "transaction details",
    ),
    "debit": ("withdrawal amt", "withdrawal", "debit amount", "debit", "dr", "withdrawals"),
    "credit": ("deposit amt", "deposit", "credit amount", "credit", "cr", "deposits"),
    "amount": ("amount", "transaction amount", "amount (inr)", "amt"),
    "type": ("dr/cr", "cr/dr", "type", "debit/credit", "transaction type"),
}


def _match_columns(header: list[str]) -> dict[str, int]:
    cells = [re.sub(r"[^a-z/() ]", "", h.strip().lower()).strip() for h in header]
    found: dict[str, int] = {}
    for field, names in _HEADERS.items():
        for name in names:  # names are in preference order
            if name in cells and cells.index(name) not in found.values():
                found[field] = cells.index(name)
                break
    return found


def parse_csv(text: str, now: datetime | None = None) -> tuple[list[Txn], list[str]]:
    """Transactions in a bank statement CSV, and the problems met on the way."""
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    header_at = None
    cols: dict[str, int] = {}
    for i, row in enumerate(rows[:40]):
        cols = _match_columns(row)
        if (
            "date" in cols
            and "description" in cols
            and ("amount" in cols or "debit" in cols or "credit" in cols)
        ):
            header_at = i
            break
    if header_at is None:
        return [], ["No header row with a date, a description and an amount column was found."]

    out: list[Txn] = []
    problems: list[str] = []
    for n, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(field: str, row: list[str] = row) -> str:
            i = cols.get(field)
            return row[i].strip() if i is not None and i < len(row) else ""

        day = parse_day(cell("date"), now)
        if day is None:
            continue  # footers, totals, "opening balance" rows
        debit, credit = parse_amount(cell("debit")), parse_amount(cell("credit"))
        if debit or credit:
            amount = debit if debit else credit
            direction = "debit" if debit else "credit"
        else:
            amount = parse_amount(cell("amount"))
            if amount is None or amount == 0:
                problems.append(f"line {n}: no amount")
                continue
            kind = cell("type").lower()
            if kind.startswith("cr") or "credit" in kind:
                direction = "credit"
            elif kind.startswith("dr") or "debit" in kind:
                direction = "debit"
            else:
                direction = "debit" if amount < 0 else "credit"
        amount = abs(amount)
        description = re.sub(r"\s+", " ", cell("description"))[:500]
        out.append(Txn(day, amount, direction, description, merchant=merchant_from(description)))
    return out, problems


_SMS_AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
_SMS_DEBIT = re.compile(r"\b(debited|spent|withdrawn|paid|sent|debit|purchase|dr)\b", re.I)
_SMS_CREDIT = re.compile(r"\b(credited|received|deposited|credit|refund(?:ed)?|cr)\b", re.I)
_SMS_ACCOUNT = re.compile(
    r"(?:a/c|acct|account|ac|card)\s*(?:no\.?)?\s*(?:ending(?:\s+with)?|[x*]+)?\s*[x*]*(\d{3,4})\b",
    re.I,
)
_SMS_MERCHANT = re.compile(
    r"\b(?:at|to|towards|info[:\s])\s*([A-Za-z0-9@._&' \-]{2,60}?)(?=\s+(?:on|ref|upi|avl|avbl|bal|via|dated|txn)\b|[.;,]|$)",
    re.I,
)
_SMS_DATE = re.compile(
    r"\bon\s+(\d{4}-\d{2}-\d{2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}[-\s]?[A-Za-z]{3}[-\s]?\d{2,4})",
    re.I,
)


def parse_alert(text: str, now: datetime | None = None) -> Txn | None:
    """A transaction from one bank alert text, or None if it is not one."""
    now = now or datetime.now(UTC)
    body = (text or "").strip()
    amount_m = _SMS_AMOUNT.search(body)
    if not amount_m:
        return None
    if re.search(r"\b(otp|one time password)\b", body, re.I):
        return None
    debit, credit = _SMS_DEBIT.search(body), _SMS_CREDIT.search(body)
    if debit and credit:
        direction = "debit" if debit.start() < credit.start() else "credit"
    elif debit or credit:
        direction = "debit" if debit else "credit"
    else:
        return None
    amount = parse_amount(amount_m.group(1))
    if not amount:
        return None
    acct = _SMS_ACCOUNT.search(body)
    when = _SMS_DATE.search(body)
    merchant = None
    for m in _SMS_MERCHANT.finditer(body):
        candidate = re.sub(r"^vpa\s+", "", m.group(1).strip(" -."), flags=re.I)
        if candidate and not re.match(r"^(your|a/c|ac|account|card|rs|inr)\b", candidate, re.I):
            merchant = candidate[:120]
            break
    return Txn(
        occurred_on=(parse_day(when.group(1), now) if when else None) or now.date(),
        amount=abs(amount),
        direction=direction,
        description=re.sub(r"\s+", " ", body)[:500],
        merchant=merchant,
        account_last4=acct.group(1)[-4:] if acct else None,
    )


def merchant_from(description: str) -> str | None:
    """A readable merchant out of a statement narration ("UPI/123/SWIGGY/..." → "SWIGGY")."""
    text = description.strip()
    if not text:
        return None
    # "POS 1234XXXX AMAZON PAY" -> "AMAZON PAY": drop the terminal or card code.
    text = re.sub(r"^(POS|ECOM|ATM)\s+\S*\d\S*\s+", "", text, flags=re.I)
    # Payment-rail narrations separate fields with dashes as well as slashes.
    rail = re.match(r"^(UPI|NEFT|IMPS|RTGS|ACH)[-/]", text, re.I)
    parts = [p.strip() for p in re.split(r"[/|*-]" if rail else r"[/|*]", text) if p.strip()]
    words = [
        p
        for p in parts
        if re.search(r"[A-Za-z]{3,}", p)
        and p.upper() not in {"UPI", "NEFT", "IMPS", "RTGS", "POS", "ACH"}
    ]
    return (words[0] if words else text)[:120]


# ── Categories ──────────────────────────────────────────────────────────────


def categorise(txn: Txn, rules: list[tuple[str, str]]) -> tuple[str, str]:
    """(category, source): the user's rules, then the built-in keywords."""
    hay = f"{txn.merchant or ''} {txn.description}".lower()
    for pattern, category in rules:
        if pattern and pattern in hay:
            return category, "user"
    if txn.direction == "credit" and re.search(r"\b(salary|sal)\b", hay):
        return "income", "rule"
    for pattern, category in _BUILTIN_RULES:
        if re.search(rf"\b{re.escape(pattern)}\b", hay):
            return category, "rule"
    return "uncategorised", "rule"


_MODEL_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "categories",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(CATEGORIES)},
                }
            },
            "required": ["categories"],
            "additionalProperties": False,
        },
    },
}


async def categorise_with_model(descriptions: list[str], client=None) -> list[str | None]:
    """The local model's category for each description, in order (None on failure)."""
    if not descriptions:
        return []
    if client is None:
        from life_graph.api.dependencies import get_lm_client

        client = get_lm_client()
    numbered = "\n".join(f"{i + 1}. {d[:160]}" for i, d in enumerate(descriptions))
    try:
        raw = await client.chat_local_only(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Assign each bank transaction a spending category. Answer with one"
                        f" category per line item, in order, from: {', '.join(CATEGORIES)}."
                        " Use uncategorised when unsure."
                    ),
                },
                {"role": "user", "content": numbered},
            ],
            model=settings.lm_extraction_model or None,
            temperature=0.0,
            max_tokens=20 + 12 * len(descriptions),
            response_format=_MODEL_SCHEMA,
        )
        cats = json.loads(raw).get("categories") if raw else None
    except Exception:
        logger.warning("Local transaction categorisation failed", exc_info=True)
        cats = None
    if not isinstance(cats, list) or len(cats) != len(descriptions):
        return [None] * len(descriptions)
    return [c if c in CATEGORIES else None for c in cats]


async def _rules(session: AsyncSession, tenant_id: str) -> list[tuple[str, str]]:
    rows = (
        await session.execute(
            select(MoneyCategoryRule.pattern, MoneyCategoryRule.category).where(
                MoneyCategoryRule.tenant_id == tenant_id
            )
        )
    ).all()
    # Longer patterns are more specific: "amazon prime" before "amazon".
    return sorted(((p, c) for p, c in rows), key=lambda r: -len(r[0]))


# ── Storage ─────────────────────────────────────────────────────────────────


async def store(
    session: AsyncSession,
    tenant_id: str,
    txns: list[Txn],
    *,
    source: str,
    use_model: bool = True,
    client=None,
) -> dict[str, int]:
    """Categorise and insert; duplicates are skipped. Returns counts."""
    rules = await _rules(session, tenant_id)
    decided = [categorise(t, rules) for t in txns]
    if use_model:
        todo = [i for i, (cat, _src) in enumerate(decided) if cat == "uncategorised"]
        todo = todo[:MAX_MODEL_CATEGORISE]
        if todo:
            guesses = await categorise_with_model(
                [f"{txns[i].merchant or ''} — {txns[i].description}" for i in todo], client=client
            )
            for i, guess in zip(todo, guesses, strict=True):
                if guess and guess != "uncategorised":
                    decided[i] = (guess, "model")
    added = 0
    for txn, (category, cat_source) in zip(txns, decided, strict=True):
        result = await session.execute(
            insert(MoneyTransaction)
            .values(
                tenant_id=tenant_id,
                occurred_on=txn.occurred_on,
                amount=txn.amount,
                direction=txn.direction,
                currency=txn.currency,
                description=txn.description,
                merchant=txn.merchant,
                category=category,
                category_source=cat_source,
                account_last4=txn.account_last4,
                source=source,
                dedup_hash=txn.dedup_hash(tenant_id),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "dedup_hash"])
        )
        added += result.rowcount or 0
    return {"parsed": len(txns), "added": added, "duplicates": len(txns) - added}


async def recategorise(
    session: AsyncSession, tenant_id: str, txn_id, category: str, *, remember: bool
) -> MoneyTransaction | None:
    """Correct one transaction; with ``remember``, the merchant gets a rule
    and every other uncategorised or rule-filed transaction from it follows."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    txn = (
        await session.execute(
            select(MoneyTransaction).where(
                MoneyTransaction.tenant_id == tenant_id, MoneyTransaction.id == txn_id
            )
        )
    ).scalar_one_or_none()
    if txn is None:
        return None
    txn.category, txn.category_source = category, "user"
    pattern = (txn.merchant or "").strip().lower()[:120]
    if remember and len(pattern) >= 3:
        await session.execute(
            insert(MoneyCategoryRule)
            .values(tenant_id=tenant_id, pattern=pattern, category=category)
            .on_conflict_do_update(
                index_elements=["tenant_id", "pattern"], set_={"category": category}
            )
        )
        others = (
            (
                await session.execute(
                    select(MoneyTransaction).where(
                        MoneyTransaction.tenant_id == tenant_id,
                        MoneyTransaction.category_source != "user",
                        func.lower(MoneyTransaction.merchant) == pattern,
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in others:
            other.category, other.category_source = category, "user"
    await session.flush()
    return txn


def month_bounds(month: str | None, today: date) -> tuple[date, date, str]:
    """(first day, first day of next month, "YYYY-MM")."""
    if month:
        year, mon = (int(x) for x in month.split("-", 1))
    else:
        year, mon = today.year, today.month
    start = date(year, mon, 1)
    end = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return start, end, f"{year:04d}-{mon:02d}"


async def list_transactions(
    session: AsyncSession, tenant_id: str, start: date, end: date, category: str | None = None
) -> list[MoneyTransaction]:
    stmt = select(MoneyTransaction).where(
        MoneyTransaction.tenant_id == tenant_id,
        MoneyTransaction.occurred_on >= start,
        MoneyTransaction.occurred_on < end,
    )
    if category:
        stmt = stmt.where(MoneyTransaction.category == category)
    return list(
        (await session.execute(stmt.order_by(MoneyTransaction.occurred_on.desc()))).scalars().all()
    )


async def summary(
    session: AsyncSession, tenant_id: str, month: str | None, today: date
) -> dict[str, Any]:
    """Spending per category for a month, against any budgets."""
    start, end, label = month_bounds(month, today)
    rows = (
        await session.execute(
            select(MoneyTransaction.category, func.sum(MoneyTransaction.amount))
            .where(
                MoneyTransaction.tenant_id == tenant_id,
                MoneyTransaction.occurred_on >= start,
                MoneyTransaction.occurred_on < end,
                MoneyTransaction.direction == "debit",
                MoneyTransaction.category.not_in(("transfers", "investments")),
            )
            .group_by(MoneyTransaction.category)
        )
    ).all()
    income = (
        await session.execute(
            select(func.coalesce(func.sum(MoneyTransaction.amount), 0)).where(
                MoneyTransaction.tenant_id == tenant_id,
                MoneyTransaction.occurred_on >= start,
                MoneyTransaction.occurred_on < end,
                MoneyTransaction.direction == "credit",
                MoneyTransaction.category == "income",
            )
        )
    ).scalar_one()
    budgets = {
        b.category: b
        for b in (
            await session.execute(select(MoneyBudget).where(MoneyBudget.tenant_id == tenant_id))
        )
        .scalars()
        .all()
    }
    spent = {cat: Decimal(total or 0) for cat, total in rows}
    categories = []
    for cat in sorted(set(spent) | set(budgets), key=lambda c: -spent.get(c, Decimal(0))):
        budget = budgets.get(cat)
        amount = spent.get(cat, Decimal(0))
        pct = int(amount * 100 / budget.monthly_limit) if budget and budget.monthly_limit else None
        categories.append(
            {
                "category": cat,
                "spent": float(amount),
                "budget": float(budget.monthly_limit) if budget else None,
                "percent_of_budget": pct,
            }
        )
    return {
        "month": label,
        "total_spent": float(sum(spent.values(), Decimal(0))),
        "income": float(income or 0),
        "categories": categories,
    }


def cloud_view(summary_: dict[str, Any]) -> dict[str, Any]:
    """What a cloud model or the brief may see: categories and percentages."""
    return {
        "month": summary_["month"],
        "categories": [
            {"category": c["category"], "percent_of_budget": c["percent_of_budget"]}
            for c in summary_["categories"]
        ],
        "note": "Amounts are kept on the user's device.",
    }


async def set_budget(
    session: AsyncSession, tenant_id: str, category: str, limit: Decimal, currency: str = "INR"
) -> MoneyBudget:
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    await session.execute(
        insert(MoneyBudget)
        .values(tenant_id=tenant_id, category=category, monthly_limit=limit, currency=currency)
        .on_conflict_do_update(
            index_elements=["tenant_id", "category"],
            set_={"monthly_limit": limit, "currency": currency},
        )
    )
    return (
        await session.execute(
            select(MoneyBudget).where(
                MoneyBudget.tenant_id == tenant_id, MoneyBudget.category == category
            )
        )
    ).scalar_one()


def due_alert(pct: int | None, already: list[int]) -> int | None:
    """The highest alert level crossed and not yet sent this month."""
    if pct is None:
        return None
    crossed = [lvl for lvl in ALERT_LEVELS if pct >= lvl and lvl not in already]
    return max(crossed) if crossed else None


async def sweep_budgets(session_factory, tenant_id: str, today: date, notifications) -> int:
    sent = 0
    async with session_factory() as session:
        s = await summary(session, tenant_id, None, today)
        budgets = {
            b.category: b
            for b in (
                await session.execute(select(MoneyBudget).where(MoneyBudget.tenant_id == tenant_id))
            )
            .scalars()
            .all()
        }
        for cat in s["categories"]:
            budget = budgets.get(cat["category"])
            if budget is None:
                continue
            already = [int(x) for x in (budget.alerts_sent or {}).get(s["month"], [])]
            level = due_alert(cat["percent_of_budget"], already)
            if level is None:
                continue
            over = level >= 100
            await notifications.create(
                tenant_id,
                f"{cat['category'].title()} spending at {cat['percent_of_budget']}% of budget",
                body=(
                    f"{s['month']}: spent {cat['spent']:,.0f} of {cat['budget']:,.0f} {budget.currency}."
                ),
                priority="important" if over else "info",
                source_type="budget",
                source_id=str(budget.id),
                metadata={"kind": "budget_alert", "category": cat["category"], "level": level},
                deliver_at_brief=not over,
            )
            # Every level at or below this one counts as sent.
            done = sorted({*already, *[lvl for lvl in ALERT_LEVELS if lvl <= level]})
            budget.alerts_sent = {**(budget.alerts_sent or {}), s["month"]: done}
            sent += 1
        await session.commit()
    return sent


def brief_line(summary_: dict[str, Any]) -> str | None:
    hot = [
        c
        for c in summary_["categories"]
        if c["percent_of_budget"] is not None and c["percent_of_budget"] >= 75
    ]
    if not hot:
        return None
    parts = ", ".join(f"{c['category']} {c['percent_of_budget']}%" for c in hot[:4])
    return f"Budgets this month: {parts}"


def txn_dict(t: MoneyTransaction) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "occurred_on": t.occurred_on.isoformat(),
        "amount": float(t.amount),
        "direction": t.direction,
        "currency": t.currency,
        "description": t.description,
        "merchant": t.merchant,
        "category": t.category,
        "category_source": t.category_source,
        "account_last4": t.account_last4,
        "source": t.source,
    }
