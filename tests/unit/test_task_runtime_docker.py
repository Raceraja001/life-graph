"""The per-task runtime against real docker.

Skipped unless docker answers and the egress image exists
(``docker build -t life-graph-sandbox-egress:dev -f Dockerfile.egress .``).
The egress image doubles as the "driver" image here: it has python3 and
coreutils ``timeout``, which is all these checks need. The full probe set
(and the recorded results) is scripts/runtime_security_probe.py.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from life_graph.config import settings
from life_graph.services.dev import sandbox, task_runtime

IMAGE = settings.driver_runtime_egress_image


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    res = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    return res.returncode == 0


pytestmark = pytest.mark.skipif(not _docker_ready(), reason=f"needs docker and {IMAGE}")

PROBE = (
    "import socket,os,json\n"
    "def tcp(h,p):\n"
    "    try:\n"
    "        socket.create_connection((h,p),timeout=3).close(); return 'open'\n"
    "    except OSError as e: return type(e).__name__\n"
    "def via(t):\n"
    "    h,p=os.environ['HTTPS_PROXY'].split('//')[1].rsplit(':',1)\n"
    "    s=socket.create_connection((h,int(p)),timeout=10)\n"
    "    s.sendall(('CONNECT %s HTTP/1.1\\r\\nHost: %s\\r\\n\\r\\n'%(t,t)).encode())\n"
    "    return s.recv(100).split(b'\\r\\n')[0].decode()\n"
    "open('/work/written','w').write('x')\n"
    "print(json.dumps({'direct':tcp('1.1.1.1',443),'gw':tcp('172.17.0.1',55432),"
    "'blocked':via('example.com:443'),'uid':os.getuid(),"
    "'app_env':[k for k in os.environ if k.startswith('LIFE_GRAPH_')]}))\n"
)


@pytest.fixture
def worktree():
    from life_graph.drivers.dispatcher import tenant_scratch_root

    root = Path(tenant_scratch_root("it-runtime")) / f"lg_dispatch_{uuid.uuid4().hex[:6]}"
    wt = root / "wt_1"
    wt.mkdir(parents=True)
    yield wt
    shutil.rmtree(root, ignore_errors=True)


def _labelled(task_id: str) -> list[str]:
    out = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", f"label=life-graph.runtime.task={task_id}"],
        capture_output=True,
        text=True,
    )
    return out.stdout.split()


async def test_a_real_runtime_contains_the_command(worktree):
    import json

    task_id = str(uuid.uuid4())
    req = task_runtime.RuntimeRequest(
        task_id=task_id,
        tenant_id="it",
        driver="probe",
        image=IMAGE,
        command=("python3", "-c", PROBE),
        workspace=worktree,
        egress_allowlist=("api.anthropic.com",),
        memory="256m",
        cpus="0.5",
        pids_limit=64,
        timeout=60,
    )
    out = await task_runtime.DockerTaskRuntime().run(req)
    seen = json.loads(out.stdout.strip().splitlines()[-1])

    assert out.returncode == 0, out.stderr
    assert (worktree / "written").exists()  # the one writable host path works
    assert seen["direct"] != "open"  # no route out except the proxy
    assert seen["gw"] != "open"  # host-published ports unreachable
    assert seen["blocked"].endswith("403 Forbidden")  # proxy refuses the unlisted
    assert seen["uid"] != 0
    assert seen["app_env"] == []
    assert out.metadata["teardown"]["ok"] is True
    assert _labelled(task_id) == []  # nothing left behind


async def test_the_deadline_stops_a_real_container(worktree):
    task_id = str(uuid.uuid4())
    req = task_runtime.RuntimeRequest(
        task_id=task_id,
        tenant_id="it",
        driver="probe",
        image=IMAGE,
        command=("sleep", "120"),
        workspace=worktree,
        memory="64m",
        cpus="0.25",
        pids_limit=16,
        timeout=2,
    )
    with pytest.raises(sandbox.SandboxUnavailableError, match="timed out"):
        await task_runtime.DockerTaskRuntime().run(req)
    assert _labelled(task_id) == []


async def test_a_missing_image_never_starts_anything(worktree):
    req = task_runtime.RuntimeRequest(
        task_id=str(uuid.uuid4()),
        tenant_id="it",
        driver="probe",
        image="life-graph-missing:none",
        command=("true",),
        workspace=worktree,
        timeout=10,
    )
    with pytest.raises(sandbox.SandboxUnavailableError, match="not found"):
        await task_runtime.DockerTaskRuntime().run(req)
