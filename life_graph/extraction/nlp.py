"""Tier 2: spaCy-based NLP extraction.

Uses named-entity recognition, dependency parsing, and a curated
tech vocabulary to extract structured facts from text.  Runs on
every input alongside Tier 1 but yields lower confidence scores.

Model loading is lazy — the spaCy model is loaded on first call to
``extract()``, not at import time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from life_graph.extraction.rules import ExtractedFact

if TYPE_CHECKING:
    import spacy
    from spacy.tokens import Doc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curated technology vocabulary
# ---------------------------------------------------------------------------

TECH_TERMS: set[str] = {
    # Languages
    "python", "javascript", "typescript", "rust", "go", "java", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "elixir", "haskell", "lua", "zig",
    # Frameworks / Libraries
    "fastapi", "django", "flask", "express", "nestjs", "spring", "rails",
    "react", "nextjs", "next.js", "vue", "svelte", "angular", "htmx",
    "sqlalchemy", "pydantic", "celery", "pytest", "numpy", "pandas",
    "pytorch", "tensorflow", "scikit-learn", "spacy", "transformers",
    "sentence-transformers", "litellm", "crewai", "langchain", "llamaindex",
    # Databases
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "chromadb", "pinecone", "weaviate", "qdrant",
    "pgvector", "apache age",
    # Infrastructure
    "docker", "kubernetes", "k8s", "nginx", "caddy", "traefik",
    "terraform", "ansible", "github actions", "gitlab ci",
    "aws", "gcp", "azure", "vercel", "cloudflare", "minio",
    # Tools
    "git", "vim", "neovim", "vscode", "vs code", "cursor",
    "pycharm", "jetbrains", "obsidian", "notion", "linux", "windows",
    "wireguard", "tailscale", "restic",
}

# Build a lookup keyed by lowercase first word for fast pre-filtering
_TECH_FIRST_WORDS: set[str] = {term.split()[0] for term in TECH_TERMS}

# ---------------------------------------------------------------------------
# Negation cues (dependency-parse based)
# ---------------------------------------------------------------------------

_NEGATION_LEMMAS: set[str] = {
    "not", "never", "no", "neither", "nor", "n't", "stop", "stopped",
    "quit", "drop", "dropped", "remove", "removed", "avoid", "avoided",
}

# ---------------------------------------------------------------------------
# Relation verb lemmas we care about
# ---------------------------------------------------------------------------

_TRANSITION_VERBS: set[str] = {
    "switch", "replace", "migrate", "move", "transition", "upgrade",
    "downgrade", "convert", "change",
}


class SpacyExtractor:
    """Tier 2 extractor using spaCy NLP.

    Performs NER, tech-term detection, negation detection, and
    dependency-based relation extraction.

    Args:
        model_name: spaCy model to load (default ``en_core_web_sm``).
    """

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._model_name = model_name
        self._nlp: spacy.Language | None = None

    # -- lazy loader --------------------------------------------------------

    def _load_model(self) -> spacy.Language:
        """Load the spaCy model on first use."""
        if self._nlp is None:
            import spacy as _spacy

            try:
                self._nlp = _spacy.load(self._model_name)
            except OSError:
                logger.warning(
                    "spaCy model '%s' not found — falling back to blank 'en'.",
                    self._model_name,
                )
                self._nlp = _spacy.blank("en")
        return self._nlp

    # -- public API ---------------------------------------------------------

    def extract(self, text: str) -> list[ExtractedFact]:
        """Run spaCy NLP pipeline and return extracted facts.

        Args:
            text: Raw input text.

        Returns:
            List of extracted facts with moderate confidence.
        """
        nlp = self._load_model()
        doc = nlp(text)

        facts: list[ExtractedFact] = []
        facts.extend(self._extract_entities(doc))
        facts.extend(self._extract_tech_mentions(doc))
        facts.extend(self._extract_relations(doc))

        facts.sort(key=lambda f: f.confidence, reverse=True)
        return facts

    # -- entity extraction --------------------------------------------------

    @staticmethod
    def _extract_entities(doc: Doc) -> list[ExtractedFact]:
        """Extract named entities of interest from the spaCy doc."""
        relevant_labels = {"PRODUCT", "ORG", "PERSON", "GPE", "WORK_OF_ART", "FAC"}
        facts: list[ExtractedFact] = []
        seen: set[str] = set()

        for ent in doc.ents:
            if ent.label_ not in relevant_labels:
                continue
            key = ent.text.lower().strip()
            if key in seen or len(key) < 2:
                continue
            seen.add(key)

            # Check for negation in the surrounding context
            is_negated = _is_negated(ent.root)
            fact_type = "anti_preference" if is_negated else "fact"
            confidence = 0.55 if is_negated else 0.60

            facts.append(
                ExtractedFact(
                    content=f"Entity ({ent.label_}): {ent.text}",
                    fact_type=fact_type,
                    confidence=confidence,
                    entities=[ent.text],
                    source_text=ent.sent.text.strip() if ent.sent else ent.text,
                )
            )

        return facts

    # -- tech mentions ------------------------------------------------------

    @staticmethod
    def _extract_tech_mentions(doc: Doc) -> list[ExtractedFact]:
        """Detect known technology terms in the document."""
        text_lower = doc.text.lower()
        facts: list[ExtractedFact] = []
        found: set[str] = set()

        for term in TECH_TERMS:
            if term in found:
                continue
            # Quick check: first word must appear in text
            if term.split()[0] not in text_lower:
                continue
            # Full substring check
            idx = text_lower.find(term)
            if idx == -1:
                continue

            # Verify word boundaries
            before = text_lower[idx - 1] if idx > 0 else " "
            after_idx = idx + len(term)
            after = text_lower[after_idx] if after_idx < len(text_lower) else " "
            if before.isalnum() or after.isalnum():
                continue

            found.add(term)

            # Determine context around mention for negation
            is_negated = _negation_in_window(text_lower, idx)
            fact_type = "anti_preference" if is_negated else "fact"
            confidence = 0.60 if is_negated else 0.65

            facts.append(
                ExtractedFact(
                    content=f"Tech mention: {term}",
                    fact_type=fact_type,
                    confidence=confidence,
                    entities=[term],
                    source_text=_snippet(doc.text, idx, len(term)),
                )
            )

        return facts

    # -- relation extraction ------------------------------------------------

    @staticmethod
    def _extract_relations(doc: Doc) -> list[ExtractedFact]:
        """Parse dependency trees for transition relations.

        Detects patterns like 'switched from X to Y', 'replaced X with Y'.
        """
        facts: list[ExtractedFact] = []

        for token in doc:
            if token.lemma_.lower() not in _TRANSITION_VERBS:
                continue

            from_entity: str | None = None
            to_entity: str | None = None

            for child in token.children:
                if child.dep_ == "prep":
                    prep_text = child.text.lower()
                    pobj = _first_pobj(child)
                    if pobj is None:
                        continue
                    if prep_text == "from":
                        from_entity = pobj
                    elif prep_text in {"to", "with"}:
                        to_entity = pobj
                elif child.dep_ in {"dobj", "attr"}:
                    subtree_text = " ".join(t.text for t in child.subtree)
                    to_entity = subtree_text.strip()

            if from_entity and to_entity:
                facts.append(
                    ExtractedFact(
                        content=f"Switched from {from_entity} to {to_entity}",
                        fact_type="decision",
                        confidence=0.70,
                        entities=[from_entity, to_entity],
                        source_text=token.sent.text.strip(),
                    )
                )
            elif to_entity:
                facts.append(
                    ExtractedFact(
                        content=f"Transitioned to {to_entity}",
                        fact_type="decision",
                        confidence=0.60,
                        entities=[to_entity],
                        source_text=token.sent.text.strip(),
                    )
                )

        return facts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_negated(token: spacy.tokens.Token) -> bool:  # type: ignore[name-defined]
    """Check whether a token is under a negation scope."""
    for child in token.children:
        if child.dep_ == "neg" or child.lemma_.lower() in _NEGATION_LEMMAS:
            return True
    if token.head and token.head.lemma_.lower() in _NEGATION_LEMMAS:
        return True
    return False


def _negation_in_window(text_lower: str, idx: int, window: int = 40) -> bool:
    """Heuristic: check for negation words within *window* chars before idx."""
    start = max(0, idx - window)
    window_text = text_lower[start:idx]
    return any(neg in window_text for neg in ("not ", "never ", "no ", "don't ", "avoid ", "stopped "))


def _snippet(text: str, idx: int, length: int, context: int = 60) -> str:
    """Return a snippet of *text* around a match for source_text."""
    start = max(0, idx - context)
    end = min(len(text), idx + length + context)
    return text[start:end].strip()


def _first_pobj(prep_token: spacy.tokens.Token) -> str | None:  # type: ignore[name-defined]
    """Get the text of the first prepositional object under *prep_token*."""
    for child in prep_token.children:
        if child.dep_ == "pobj":
            subtree_text = " ".join(t.text for t in child.subtree)
            return subtree_text.strip()
    return None
