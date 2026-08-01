"""Every enqueue_job() name must be a registered ARQ function (full dotted path),
or the worker silently never runs the job."""

import re
from pathlib import Path

from life_graph.workers.settings import WorkerSettings

_ROOT = Path(__file__).resolve().parents[2] / "life_graph"
_CALL = re.compile(r'enqueue_job\(\s*"([^"]+)"')


def _registered_names() -> set[str]:
    return {f if isinstance(f, str) else getattr(f, "__qualname__", str(f))
            for f in WorkerSettings.functions}


def test_all_enqueue_names_are_registered():
    registered = _registered_names()
    offenders = []
    for py in _ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in _CALL.finditer(text):
            name = m.group(1)
            if name not in registered:
                offenders.append(f"{py.relative_to(_ROOT.parent)}: enqueue_job(\"{name}\")")
    assert not offenders, "Unregistered enqueue_job names:\n" + "\n".join(offenders)
