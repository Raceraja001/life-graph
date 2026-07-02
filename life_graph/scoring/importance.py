"""Signal-based importance scoring for memories.

Uses regex and keyword matching to assign importance scores.
Zero LLM dependency — all detection is rule-based.
"""

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

EMPHASIS_KEYWORDS: set[str] = {
    "important", "critical", "never", "always", "must",
}

FAILURE_KEYWORDS: set[str] = {
    "bug", "error", "crash", "fix", "broke", "issue",
}

ARCHITECTURE_KEYWORDS: set[str] = {
    "architecture", "design", "pattern", "approach", "structure",
}

COST_KEYWORDS: set[str] = {
    "cost", "price", "expensive", "budget", "pay", "save money",
}

HEDGING_KEYWORDS: set[str] = {
    "maybe", "perhaps", "might", "not sure", "possibly",
}

# Compiled regex patterns (compiled once at module load)
_EXPLICIT_SAVE_RE = re.compile(
    r"\b(remember\s+this|save\s+this|note\s+this|keep\s+this)\b",
    re.IGNORECASE,
)
_ALL_CAPS_WORD_RE = re.compile(r"\b[A-Z]{2,}\b")
_QUESTION_RE = re.compile(r"\?\s*$")


@dataclass(frozen=True, slots=True)
class Signal:
    """A single detected scoring signal."""

    name: str
    weight: float
    matched: str


@dataclass
class SignalResult:
    """Aggregated result from signal detection."""

    signals: list[Signal] = field(default_factory=list)
    raw_delta: float = 0.0

    def add(self, signal: Signal) -> None:
        """Add a signal and accumulate its weight."""
        self.signals.append(signal)
        self.raw_delta += signal.weight


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_emphasis(text: str) -> list[Signal]:
    """Detect explicit emphasis via keywords (case-insensitive) and ALL-CAPS words."""
    signals: list[Signal] = []
    text_lower = text.lower()

    for kw in EMPHASIS_KEYWORDS:
        if kw in text_lower:
            signals.append(Signal("emphasis_keyword", 0.3, kw))
            break  # count once

    # ALL-CAPS words (≥2 chars) that aren't common acronyms
    caps_matches = _ALL_CAPS_WORD_RE.findall(text)
    # Filter out single-char and very common short forms
    meaningful_caps = [w for w in caps_matches if w not in EMPHASIS_KEYWORDS and len(w) >= 2]
    if meaningful_caps:
        signals.append(Signal("all_caps", 0.3, meaningful_caps[0]))

    return signals


def _detect_keyword_set(
    text: str,
    keywords: set[str],
    signal_name: str,
    weight: float,
) -> Signal | None:
    """Detect any keyword from a set in the text (case-insensitive)."""
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            return Signal(signal_name, weight, kw)
    return None


def _detect_explicit_save(text: str) -> Signal | None:
    """Detect user-explicit save phrases."""
    match = _EXPLICIT_SAVE_RE.search(text)
    if match:
        return Signal("explicit_save", 0.45, match.group(0))
    return None


def _detect_question(text: str) -> Signal | None:
    """Detect if text ends with a question mark."""
    if _QUESTION_RE.search(text):
        return Signal("question", -0.1, "?")
    return None


def _detect_repeated_mention(context: dict | None) -> Signal | None:
    """Apply bonus for repeated mentions from context dict."""
    if not context:
        return None
    repeated_count = context.get("repeated_count", 0)
    if repeated_count > 0:
        weight = min(repeated_count * 0.05, 0.2)
        return Signal("repeated_mention", weight, f"×{repeated_count}")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _importance_tier(score: float) -> str:
    """Map a numeric importance score to a tier label."""
    if score >= 0.85:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "normal"
    return "low"


class ImportanceTagger:
    """Rule-based importance scorer for text content.

    Applies weighted signals (regex + keyword matching) to produce
    a normalised importance score and tier. Zero LLM calls.

    Usage::

        tagger = ImportanceTagger()
        score, tier = tagger.score("Remember this: always use async drivers")
    """

    _BASE_SCORE: float = 0.5

    def score(self, text: str, context: dict | None = None) -> tuple[float, str]:
        """Score a piece of text for importance.

        Args:
            text: The text content to evaluate.
            context: Optional dict with extra signals. Supported keys:
                - ``repeated_count`` (int): How many times this topic was mentioned.

        Returns:
            A ``(score, tier)`` tuple where score ∈ [0.0, 1.0] and tier is
            one of ``'critical'``, ``'high'``, ``'normal'``, ``'low'``.
        """
        result = SignalResult()

        # --- additive signals ---
        for sig in _detect_emphasis(text):
            result.add(sig)

        failure_sig = _detect_keyword_set(text, FAILURE_KEYWORDS, "failure_context", 0.2)
        if failure_sig:
            result.add(failure_sig)

        arch_sig = _detect_keyword_set(text, ARCHITECTURE_KEYWORDS, "architecture_decision", 0.15)
        if arch_sig:
            result.add(arch_sig)

        cost_sig = _detect_keyword_set(text, COST_KEYWORDS, "cost_financial", 0.15)
        if cost_sig:
            result.add(cost_sig)

        save_sig = _detect_explicit_save(text)
        if save_sig:
            result.add(save_sig)

        # --- subtractive signals ---
        hedge_sig = _detect_keyword_set(text, HEDGING_KEYWORDS, "hedging", -0.2)
        if hedge_sig:
            result.add(hedge_sig)

        question_sig = _detect_question(text)
        if question_sig:
            result.add(question_sig)

        # --- context signals ---
        repeat_sig = _detect_repeated_mention(context)
        if repeat_sig:
            result.add(repeat_sig)

        # --- final computation ---
        raw_score = self._BASE_SCORE + result.raw_delta
        clamped = max(0.0, min(1.0, raw_score))
        tier = _importance_tier(clamped)

        return clamped, tier

    def score_detailed(
        self, text: str, context: dict | None = None,
    ) -> tuple[float, str, list[Signal]]:
        """Score with full signal breakdown for debugging.

        Returns:
            A ``(score, tier, signals)`` tuple.
        """
        result = SignalResult()

        for sig in _detect_emphasis(text):
            result.add(sig)

        for kw_set, name, weight in [
            (FAILURE_KEYWORDS, "failure_context", 0.2),
            (ARCHITECTURE_KEYWORDS, "architecture_decision", 0.15),
            (COST_KEYWORDS, "cost_financial", 0.15),
        ]:
            sig = _detect_keyword_set(text, kw_set, name, weight)
            if sig:
                result.add(sig)

        save_sig = _detect_explicit_save(text)
        if save_sig:
            result.add(save_sig)

        hedge_sig = _detect_keyword_set(text, HEDGING_KEYWORDS, "hedging", -0.2)
        if hedge_sig:
            result.add(hedge_sig)

        question_sig = _detect_question(text)
        if question_sig:
            result.add(question_sig)

        repeat_sig = _detect_repeated_mention(context)
        if repeat_sig:
            result.add(repeat_sig)

        raw_score = self._BASE_SCORE + result.raw_delta
        clamped = max(0.0, min(1.0, raw_score))
        tier = _importance_tier(clamped)

        return clamped, tier, result.signals
