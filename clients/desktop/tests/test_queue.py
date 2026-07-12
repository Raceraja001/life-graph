from clients.desktop.client import SendResult, SendStatus
from clients.desktop.queue import CaptureQueue


def _payload(cid, content="x"):
    return {"surface": "desktop", "content": content,
            "properties": {"client_capture_id": cid}}


def test_enqueue_and_count(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    assert q.pending_count() == 2


def test_enqueue_dedupes_by_capture_id(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("a"))
    assert q.pending_count() == 1


def test_replay_sends_all_on_success(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    sent = q.replay(lambda p: SendResult(SendStatus.SENT))
    assert sent == 2
    assert q.pending_count() == 0


def test_replay_stops_on_transient_and_keeps_rest(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    calls = []

    def send_fn(p):
        calls.append(p["properties"]["client_capture_id"])
        return SendResult(SendStatus.TRANSIENT)

    sent = q.replay(send_fn)
    assert sent == 0
    assert calls == ["a"]           # stopped after first failure
    assert q.pending_count() == 2   # nothing removed


def test_replay_drops_bad_items(tmp_path):
    q = CaptureQueue(tmp_path / "q.db")
    q.enqueue(_payload("a"))
    q.enqueue(_payload("b"))
    sent = q.replay(lambda p: SendResult(SendStatus.BAD))
    assert sent == 0
    assert q.pending_count() == 0   # both dropped, not retried forever
