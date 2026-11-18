"""Load the built-in persona definitions from kernel/builtin_personas/.

Each persona is one Markdown file, ``NN-<name>.md``: a YAML header between
``---`` lines holds its fields (tools, driver, verifier chain, ...) and the
body is its system prompt. The number sets the seeding order. In the body,
the lines of a paragraph are joined with single spaces and paragraphs are
separated by one blank line, so a prompt can be wrapped freely without
changing the text the model sees. ``<<name>>`` puts in a shared passage: a
file in ``fragments/`` or a contract from ``kernel/propose_contract.py``.

Prompts live here, not in Python, so tuning one is a data change. The
format is checked strictly on load (unknown keys, a name that does not match
its file, an unknown ``<<marker>>`` all raise): a typo must fail at startup
and in CI, not quietly seed a broken persona. See the README in that folder.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from life_graph.kernel.propose_contract import (
    AGENT_TASK_PROPOSE_CONTRACT,
    COMMAND_PROPOSE_CONTRACT,
)

PERSONA_DIR = Path(__file__).resolve().parent / "builtin_personas"

REQUIRED_KEYS = (
    "name",
    "display_name",
    "icon",
    "description",
    "intent_tags",
    "temperature",
    "allowed_tools",
)
OPTIONAL_KEYS = ("driver", "task_types", "verifier_chain", "context_profile")

_FILE = re.compile(r"^(\d\d)-([a-z0-9-]+)\.md$")
_MARKER = re.compile(r"<<([a-z_]+)>>")


class PersonaFileError(ValueError):
    """A persona or fragment file is malformed."""


def _split(path: Path) -> tuple[Any, str]:
    """The YAML header (parsed) and the body of one file."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise PersonaFileError(f"{path.name}: must start with a '---' header line")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise PersonaFileError(f"{path.name}: the header has no closing '---' line")
    try:
        header = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        raise PersonaFileError(f"{path.name}: bad YAML header: {exc}") from exc
    return header, text[end + 5 :]


def _prose(body: str) -> str:
    """Unwrap a body: a paragraph's lines joined by spaces, paragraphs by a blank line."""
    paras = re.split(r"\n[ \t]*\n", body.strip())
    return "\n\n".join(" ".join(line.strip() for line in p.splitlines()) for p in paras)


def load_fragments(directory: Path = PERSONA_DIR) -> dict[str, str]:
    """Shared passages a prompt puts in with ``<<name>>``."""
    fragments = {
        "agent_task_propose_contract": AGENT_TASK_PROPOSE_CONTRACT.strip(),
        "command_propose_contract": COMMAND_PROPOSE_CONTRACT.strip(),
    }
    for path in sorted((directory / "fragments").glob("*.md")):
        header, body = _split(path)
        if header is not None:  # comments only
            raise PersonaFileError(f"{path.name}: a fragment's header holds comments only")
        if path.stem in fragments:
            raise PersonaFileError(f"{path.name}: fragment {path.stem!r} already exists")
        fragments[path.stem] = _prose(body)
    return fragments


def load_builtin_personas(directory: Path = PERSONA_DIR) -> list[dict[str, Any]]:
    """Every built-in persona definition, in file-number order."""
    fragments = load_fragments(directory)
    personas: list[dict[str, Any]] = []
    numbers: set[str] = set()
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        m = _FILE.match(path.name)
        if not m:
            raise PersonaFileError(f"{path.name}: name it NN-<persona name>.md")
        number, stem = m.groups()
        if number in numbers:
            raise PersonaFileError(f"{path.name}: number {number} is used twice")
        numbers.add(number)
        header, body = _split(path)
        if not isinstance(header, dict):
            raise PersonaFileError(f"{path.name}: the header must be a mapping")
        missing = [k for k in REQUIRED_KEYS if k not in header]
        unknown = set(header) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
        if missing or unknown:
            raise PersonaFileError(
                f"{path.name}: missing {missing or 'nothing'}, unknown {sorted(unknown) or 'nothing'}"
            )
        if header["name"] != stem:
            raise PersonaFileError(f"{path.name}: name {header['name']!r} must match the file")

        def put_in(marker: re.Match[str], where: str = path.name) -> str:
            if marker.group(1) not in fragments:
                raise PersonaFileError(f"{where}: unknown fragment <<{marker.group(1)}>>")
            return fragments[marker.group(1)]

        prompt = _MARKER.sub(put_in, _prose(body))
        if not prompt:
            raise PersonaFileError(f"{path.name}: the system prompt is empty")
        defn: dict[str, Any] = {}
        for key in REQUIRED_KEYS + OPTIONAL_KEYS:
            if key in header:
                defn[key] = header[key]
            if key == "description":
                defn["system_prompt"] = prompt
        personas.append(defn)
    names = [p["name"] for p in personas]
    if len(set(names)) != len(names):
        raise PersonaFileError(f"a persona name is used twice: {names}")
    return personas
