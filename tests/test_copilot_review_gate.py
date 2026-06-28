import urllib.error

import copilot_review_gate as gate


def test_find_copilot_run_picks_matching_name():
    runs = [{"name": "ci"}, {"name": gate.COPILOT_CHECK_NAME, "status": "completed"}]
    assert gate.find_copilot_run(runs)["status"] == "completed"


def test_find_copilot_run_returns_none_when_absent():
    assert gate.find_copilot_run([{"name": "ci"}, {"name": "lint"}]) is None


def test_mirror_state_success():
    assert gate.mirror_state("success") == ("success", "Copilot review success")


def test_mirror_state_non_success_reports_conclusion():
    state, description = gate.mirror_state("cancelled")
    assert state == "failure"
    assert "cancelled" in description


def test_wait_for_ready_returns_ready_once_draft_clears(monkeypatch):
    answers = iter([True, True, False])
    monkeypatch.setattr(gate, "read_is_draft", lambda repo, pr: next(answers))
    monkeypatch.setattr(gate.time, "sleep", lambda _seconds: None)
    assert gate.wait_for_ready("owner/repo", "1") == "ready"


def test_wait_for_ready_reports_draft_when_never_ready(monkeypatch):
    monkeypatch.setattr(gate, "read_is_draft", lambda repo, pr: True)
    monkeypatch.setattr(gate.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 3)
    assert gate.wait_for_ready("owner/repo", "1") == "draft"


def test_wait_for_ready_reports_unreadable_when_every_read_fails(monkeypatch):
    def fail(repo, pr):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(gate, "read_is_draft", fail)
    monkeypatch.setattr(gate.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 3)
    assert gate.wait_for_ready("owner/repo", "1") == "unreadable"


def test_wait_for_ready_reads_draft_then_ready_is_not_unreadable(monkeypatch):
    answers = iter([True, urllib.error.URLError("blip")])

    def read(repo, pr):
        value = next(answers)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(gate, "read_is_draft", read)
    monkeypatch.setattr(gate.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 2)
    assert gate.wait_for_ready("owner/repo", "1") == "draft"
