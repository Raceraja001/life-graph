"""Every enqueue_job() name in the chat-distillation worker must be a
registered ARQ function (full dotted path), or the worker silently never
runs the job.

Scope note: this only scans ``life_graph/workers/distill.py`` (the file
this task owns), not the whole ``life_graph/`` tree. A handful of
*pre-existing* enqueue_job() calls elsewhere in the codebase (e.g.
``life_graph/workers/tasks.py``, ``life_graph/api/admin.py``,
``life_graph/integrations/webhook.py``) use bare function names instead of
their full dotted path and would fail a repo-wide version of this check —
that's tracked/fixed on a separate branch (``fix/reliability-debt``) and is
out of scope for chat distillation. If that fix lands on this branch too,
widen ``_TARGETS`` back to a full ``life_graph/`` rglob.
"""

import re
from pathlib import Path

from life_graph.workers.settings import WorkerSettings

_ROOT = Path(__file__).resolve().parents[2] / "life_graph"
_TARGETS = [_ROOT / "workers" / "distill.py"]
_CALL = re.compile(r'enqueue_job\(\s*"([^"]+)"')


def _registered_names() -> set[str]:
    return {
        f if isinstance(f, str) else getattr(f, "__qualname__", str(f))
        for f in WorkerSettings.functions
    }


def test_distill_enqueue_names_are_registered():
    registered = _registered_names()
    offenders = []
    for py in _TARGETS:
        text = py.read_text(encoding="utf-8")
        for m in _CALL.finditer(text):
            name = m.group(1)
            if name not in registered:
                offenders.append(f'{py.relative_to(_ROOT.parent)}: enqueue_job("{name}")')
    assert not offenders, "Unregistered enqueue_job names:\n" + "\n".join(offenders)
