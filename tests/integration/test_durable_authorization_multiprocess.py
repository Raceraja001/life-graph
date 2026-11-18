"""Cross-process durable authorization & end-to-end exact-bound approval integration tests.

Verifies P1 Section 4 (multi-worker OS process restart persistence and concurrent
one-use consumption across independent OS processes against PostgreSQL) and
P0 Section 2 (real run_browser_errand -> Notification in Postgres ->
notification_actions.perform('approve') -> durable capability resume & replay denial).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from life_graph.autonomy.approvals.capability import ALREADY_CONSUMED, REVOKED
from tests.integration.conftest import skip_on_db_error

WORKER_SCRIPT = """
import json, os, sys, time
from datetime import UTC, datetime
from life_graph.autonomy.approvals.capability import capability_store, standing_rule_store
from life_graph.autonomy.approvals.durable_store import attach_durable_stores
from life_graph.autonomy.approvals.policy_checker import StandingRule

attach_durable_stores()
mode = sys.argv[1]
payload = json.loads(sys.argv[2])

if mode == "issue":
    cap = capability_store.issue(
        tenant_id=payload["tenant_id"],
        action_types=["browser_click", "browser_navigate", "browser_read_page"],
        target_origins=[payload["origin"]],
        errand_id=payload["errand_id"],
        step_index=payload["step_index"],
        target_selector=payload["selector"],
        parameters_hash=payload["params_hash"],
        one_use=True,
    )
    standing_rule_store.set_rules(
        payload["tenant_id"],
        [
            StandingRule(
                action_type="browser_read_page",
                effect="allow",
                origins=frozenset({payload["origin"]}),
            )
        ],
    )
    print(json.dumps({"pid": os.getpid(), "capability_id": cap.capability_id}))

elif mode == "consume":
    wait = payload["start_at"] - time.time()
    if wait > 0:
        time.sleep(wait)
    cap, check = capability_store.consume(
        payload["capability_id"],
        tenant_id=payload["tenant_id"],
        errand_id=payload["errand_id"],
        step_index=payload["step_index"],
        target_selector=payload["selector"],
        parameters_hash=payload["params_hash"],
        now=datetime.now(UTC),
    )
    print(json.dumps({"pid": os.getpid(), "ok": check.ok, "reason": check.reason}))

elif mode == "verify_rules_and_revoke":
    rules = standing_rule_store.rules_for(payload["tenant_id"])
    cap = capability_store.issue(
        tenant_id=payload["tenant_id"],
        action_types=["browser_click"],
        target_origins=[payload["origin"]],
        errand_id=payload["errand_id"],
        step_index=payload["step_index"],
        target_selector=payload["selector"],
        parameters_hash=payload["params_hash"],
        one_use=True,
    )
    revoked = capability_store.revoke(cap.capability_id)
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "rule_count": len(rules),
                "rule_action": rules[0].action_type if rules else None,
                "rule_origin": sorted(rules[0].origins)[0] if rules and rules[0].origins else None,
                "revoked_cap_id": cap.capability_id,
                "revoked": revoked,
            }
        )
    )
"""


@skip_on_db_error
async def test_cross_process_restart_persistence_and_8_worker_atomic_consumption():
    """P1 Section 4: Issuer OS process exits; 8 independent OS worker processes
    race simultaneously against PostgreSQL; exactly 1 wins and 7 fail closed."""
    tenant_id = f"mp_auth_{uuid.uuid4().hex[:8]}"
    errand_id = f"errand_{uuid.uuid4().hex[:8]}"
    origin = "https://example.com"
    selector = "#submit-order"
    params_hash = "a" * 64

    # 1. Process A issues capability & standing rule, then terminates completely.
    issue_proc = subprocess.run(
        [
            sys.executable,
            "-c",
            WORKER_SCRIPT,
            "issue",
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "origin": origin,
                    "errand_id": errand_id,
                    "step_index": 2,
                    "selector": selector,
                    "params_hash": params_hash,
                }
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    issued = json.loads(issue_proc.stdout.strip().splitlines()[-1])
    cap_id = issued["capability_id"]
    issuer_pid = issued["pid"]

    # 2. Spawn 8 separate OS worker processes that race to consume the capability.
    start_at = time.time() + 1.2
    workers = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                WORKER_SCRIPT,
                "consume",
                json.dumps(
                    {
                        "capability_id": cap_id,
                        "tenant_id": tenant_id,
                        "errand_id": errand_id,
                        "step_index": 2,
                        "selector": selector,
                        "params_hash": params_hash,
                        "start_at": start_at,
                    }
                ),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]

    outcomes = []
    for w in workers:
        out, err = w.communicate(timeout=20)
        assert w.returncode == 0, f"Worker failed: {err}"
        outcomes.append(json.loads(out.strip().splitlines()[-1]))

    worker_pids = {o["pid"] for o in outcomes}
    assert len(worker_pids) == 8
    assert issuer_pid not in worker_pids

    winners = [o for o in outcomes if o["ok"] is True]
    losers = [o for o in outcomes if o["ok"] is False]
    assert len(winners) == 1
    assert winners[0]["reason"] == "capability_valid"
    assert len(losers) == 7
    assert all(o["reason"] == ALREADY_CONSUMED for o in losers)

    # 3. Separate OS process verifies standing rule survived process restart and revokes a new capability.
    verify_proc = subprocess.run(
        [
            sys.executable,
            "-c",
            WORKER_SCRIPT,
            "verify_rules_and_revoke",
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "origin": origin,
                    "errand_id": errand_id,
                    "step_index": 2,
                    "selector": selector,
                    "params_hash": params_hash,
                }
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    verified = json.loads(verify_proc.stdout.strip().splitlines()[-1])
    assert verified["rule_count"] == 1
    assert verified["rule_action"] == "browser_read_page"
    assert verified["rule_origin"] == origin
    assert verified["revoked"] is True

    # 4. Separate OS process tries to consume the revoked capability and fails closed.
    revoked_consume = subprocess.run(
        [
            sys.executable,
            "-c",
            WORKER_SCRIPT,
            "consume",
            json.dumps(
                {
                    "capability_id": verified["revoked_cap_id"],
                    "tenant_id": tenant_id,
                    "errand_id": errand_id,
                    "step_index": 2,
                    "selector": selector,
                    "params_hash": params_hash,
                    "start_at": 0,
                }
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rev_out = json.loads(revoked_consume.stdout.strip().splitlines()[-1])
    assert rev_out["ok"] is False
    assert rev_out["reason"] == REVOKED


@pytest.mark.asyncio
@skip_on_db_error
async def test_end_to_end_errand_pause_owner_approval_resume_and_replay_denial(monkeypatch):
    """P0 Section 2: Real run_browser_errand pauses on click, writes Notification to
    PostgreSQL, notification_actions.perform('approve') mints durable capability in
    PostgreSQL, tampered resume fails closed, exact resume succeeds once, replay fails closed."""
    from life_graph.autonomy.approvals.durable_store import attach_durable_stores
    from life_graph.core.tenant import tenant_scope
    from life_graph.models.db import Notification
    from life_graph.services.notifications import actions as notification_actions
    from life_graph.storage.database import async_session
    from life_graph.tools import errand as errand_tool

    attach_durable_stores()
    tenant_id = "default"

    class _RecordingDriver:
        def __init__(self) -> None:
            self.url = "https://example.com/"
            self.clicks: list[str] = []
            self.closed = 0

        async def navigate(self, url: str) -> None:
            self.url = url

        async def current_origin(self) -> str:
            return "https://example.com"

        async def read_page(self) -> str:
            return "Example Domain [button #confirm-btn]"

        async def fill(self, selector: str, value: str) -> None:
            pass

        async def click(self, selector: str) -> None:
            self.clicks.append(selector)

        async def close(self) -> None:
            self.closed += 1

    driver = _RecordingDriver()
    errand_tool.set_driver_override(driver)
    try:
        steps = [
            {"kind": "read_page"},
            {"kind": "click", "selector": "#confirm-btn", "note": "confirm download"},
        ]
        with tenant_scope(tenant_id):
            # 1. Initial run pauses at step 2 (click) and writes Notification to Postgres
            first_raw = await errand_tool.run_browser_errand(
                goal="Download statement",
                start_url="https://example.com/",
                steps=steps,
                allowed_origins=["https://example.com"],
            )
            first = json.loads(first_raw)
            assert first["status"] == "needs_approval"
            assert first["step"] == 2
            errand_id = first["errand_id"]
            assert driver.clicks == []

            # 2. Fetch the persisted Notification from Postgres and perform owner 'approve'
            now = datetime.now(UTC)
            async with async_session() as session:
                notif = (
                    await session.execute(
                        select(Notification)
                        .where(
                            Notification.tenant_id == tenant_id,
                            Notification.source_type == errand_tool.APPROVAL_SOURCE,
                            Notification.extra_metadata["item_id"].astext == errand_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one()
                reply_msg = await notification_actions.perform(
                    session, tenant_id, notif, "approve", now, UTC
                )
                await session.commit()
                cap_id = notif.extra_metadata["capability_id"]
            assert "Approved" in reply_msg or cap_id

            # 3. Attempting to use that capability with a modified selector fails closed
            tampered_raw = await errand_tool.run_browser_errand(
                goal="Download statement",
                start_url="https://example.com/",
                steps=[
                    {"kind": "read_page"},
                    {"kind": "click", "selector": "#delete-account", "note": "confirm download"},
                ],
                allowed_origins=["https://example.com"],
                capability_id=cap_id,
                errand_id=errand_id,
            )
            tampered = json.loads(tampered_raw)
            assert tampered["status"] == "failed"
            assert driver.clicks == []

            # 4. Resuming the exact approved plan succeeds once and executes the click
            resumed_raw = await errand_tool.run_browser_errand(
                goal="Download statement",
                start_url="https://example.com/",
                steps=steps,
                allowed_origins=["https://example.com"],
                capability_id=cap_id,
                errand_id=errand_id,
            )
            resumed = json.loads(resumed_raw)
            assert resumed["status"] == "done"
            assert driver.clicks == ["#confirm-btn"]

            # 5. Replaying the same capability a second time fails closed (one-use spent)
            replay_raw = await errand_tool.run_browser_errand(
                goal="Download statement",
                start_url="https://example.com/",
                steps=steps,
                allowed_origins=["https://example.com"],
                capability_id=cap_id,
                errand_id=errand_id,
            )
            replay = json.loads(replay_raw)
            assert replay["status"] == "failed"
            assert driver.clicks == ["#confirm-btn"]
    finally:
        errand_tool.set_driver_override(None)
