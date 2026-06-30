import urllib.error
from typing import NoReturn

import copilot_review_gate.cli as gate
import pytest

COPILOT_REVIEW_ID = 7
EXPECTED_UNRESOLVED = 2


def _raise_url_error(*_: object) -> NoReturn:
    msg = "network down"
    raise urllib.error.URLError(msg)


def test_find_copilot_run_picks_matching_name() -> None:
    runs: list[gate.JsonObject] = [
        {"name": "ci"},
        {"name": gate.COPILOT_CHECK_NAME, "status": "completed"},
    ]
    run = gate.find_copilot_run(runs)
    assert run is not None
    assert run["status"] == "completed"


def test_find_copilot_run_returns_none_when_absent() -> None:
    runs: list[gate.JsonObject] = [{"name": "ci"}, {"name": "lint"}]
    assert gate.find_copilot_run(runs) is None


def test_build_status_success() -> None:
    assert gate.build_status("success") == ("success", "Copilot review success")


def test_build_status_non_success_reports_conclusion() -> None:
    state, description = gate.build_status("cancelled")
    assert state == "failure"
    assert "cancelled" in description


def test_wait_for_ready_returns_ready_once_draft_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([True, True, False])
    monkeypatch.setattr(gate, "read_is_draft", lambda *_: next(answers))
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    assert gate.wait_for_ready("owner/repo", "1") == "ready"


def test_wait_for_ready_reports_draft_when_never_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "read_is_draft", lambda *_: True)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 3)
    assert gate.wait_for_ready("owner/repo", "1") == "draft"


def test_wait_for_ready_reports_unreadable_when_every_read_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "read_is_draft", _raise_url_error)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 3)
    assert gate.wait_for_ready("owner/repo", "1") == "unreadable"


def test_wait_for_ready_reads_draft_then_ready_is_not_unreadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = iter([True, urllib.error.URLError("blip")])

    def read(*_: object) -> bool:
        value = next(answers)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(gate, "read_is_draft", read)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", 2)
    assert gate.wait_for_ready("owner/repo", "1") == "draft"


def test_await_copilot_run_completed_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    run = {
        "name": gate.COPILOT_CHECK_NAME,
        "status": "completed",
        "conclusion": "success",
    }
    monkeypatch.setattr(gate, "fetch_copilot_run", lambda *_: run)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    assert gate.await_copilot_run("owner/repo", "sha") == ("completed", run)


def test_await_copilot_run_not_requested_when_run_never_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "fetch_copilot_run", lambda *_: None)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "APPEAR_POLL_ATTEMPTS", 3)
    assert gate.await_copilot_run("owner/repo", "sha") == ("not_requested", None)


def test_await_copilot_run_unqueryable_when_every_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "fetch_copilot_run", _raise_url_error)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "APPEAR_POLL_ATTEMPTS", 3)
    assert gate.await_copilot_run("owner/repo", "sha") == ("unqueryable", None)


def test_await_copilot_run_waits_for_in_progress_to_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_progress = {"name": gate.COPILOT_CHECK_NAME, "status": "in_progress"}
    completed = {
        "name": gate.COPILOT_CHECK_NAME,
        "status": "completed",
        "conclusion": "success",
    }
    runs = iter([in_progress, in_progress, completed])
    monkeypatch.setattr(gate, "fetch_copilot_run", lambda *_: next(runs))
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    assert gate.await_copilot_run("owner/repo", "sha") == ("completed", completed)


def test_await_copilot_run_incomplete_when_never_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_progress = {"name": gate.COPILOT_CHECK_NAME, "status": "in_progress"}
    monkeypatch.setattr(gate, "fetch_copilot_run", lambda *_: in_progress)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "COMPLETE_POLL_ATTEMPTS", 3)
    assert gate.await_copilot_run("owner/repo", "sha") == ("incomplete", in_progress)


def _record_posted_statuses(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    posted: list[tuple[str, str]] = []

    def record(_repo: str, _sha: str, state: str, description: str, _target_url: str = "") -> None:
        posted.append((state, description))

    monkeypatch.setattr(gate, "post_status", record)
    return posted


def _set_pr_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO", "owner/repo")
    monkeypatch.setenv("PR", "1")
    monkeypatch.setenv("SHA", "deadbeef")


def test_main_clean_review_posts_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    run = {"status": "completed", "conclusion": "success", "details_url": "http://run"}
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("completed", run))
    monkeypatch.setattr(gate, "await_copilot_review", lambda *_: {"id": 1})
    monkeypatch.setattr(gate, "count_unresolved_copilot_threads", lambda *_: 0)
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted[-1] == ("success", "Copilot review success")


def test_main_unresolved_comments_block_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    run = {"status": "completed", "conclusion": "success"}
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("completed", run))
    monkeypatch.setattr(gate, "await_copilot_review", lambda *_: {"id": 1})
    monkeypatch.setattr(gate, "count_unresolved_copilot_threads", lambda *_: 2)
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted[-1][0] == "failure"
    assert "2 unresolved comments" in posted[-1][1]


def test_main_failed_conclusion_blocks_without_counting_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    run = {"status": "completed", "conclusion": "cancelled"}
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("completed", run))

    def must_not_count(*_: object) -> int:
        pytest.fail("must not count threads on a non-success conclusion")

    monkeypatch.setattr(gate, "count_unresolved_copilot_threads", must_not_count)
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted[-1][0] == "failure"
    assert "cancelled" in posted[-1][1]


def test_main_unreadable_threads_fails_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    run = {"status": "completed", "conclusion": "success"}
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("completed", run))
    monkeypatch.setattr(gate, "await_copilot_review", lambda *_: None)
    monkeypatch.setattr(gate, "count_unresolved_copilot_threads", _raise_url_error)
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 1
    assert posted[-1][0] == "error"


def test_main_not_requested_blocks_but_job_stays_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("not_requested", None))
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted[-1][0] == "failure"
    assert "was not requested" in posted[-1][1]


def test_main_incomplete_blocks_but_job_stays_green(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("incomplete", None))
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted[-1][0] == "error"


def test_main_unqueryable_fails_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "ready")
    monkeypatch.setattr(gate, "await_copilot_run", lambda *_: ("unqueryable", None))
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 1
    assert posted[-1][0] == "error"


def test_main_unreadable_draft_state_fails_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "unreadable")
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 1
    assert posted[-1][0] == "error"


def test_main_draft_leaves_no_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_pr_env(monkeypatch)
    monkeypatch.setattr(gate, "wait_for_ready", lambda *_: "draft")
    posted = _record_posted_statuses(monkeypatch)
    assert gate.main() == 0
    assert posted == []


def test_is_copilot_author_matches_bot_login_case_insensitively() -> None:
    assert gate.is_copilot_author("copilot-pull-request-reviewer[bot]")
    assert gate.is_copilot_author("Copilot")
    assert not gate.is_copilot_author("realSergiy")


def test_fetch_copilot_review_matches_sha_and_author(monkeypatch: pytest.MonkeyPatch) -> None:
    reviews = [
        {"commit_id": "other", "user": {"login": "copilot-pull-request-reviewer[bot]"}},
        {"commit_id": "deadbeef", "user": {"login": "realSergiy"}},
        {
            "commit_id": "deadbeef",
            "user": {"login": "copilot-pull-request-reviewer[bot]"},
            "id": COPILOT_REVIEW_ID,
        },
    ]
    monkeypatch.setattr(gate, "_request", lambda *_: reviews)
    review = gate.fetch_copilot_review("owner/repo", "1", "deadbeef")
    assert review is not None
    assert review["id"] == COPILOT_REVIEW_ID


def test_fetch_copilot_review_returns_none_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "_request", lambda *_: [])
    assert gate.fetch_copilot_review("owner/repo", "1", "deadbeef") is None


def test_await_copilot_review_returns_when_review_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews = iter([None, None, {"id": 9}])
    monkeypatch.setattr(gate, "fetch_copilot_review", lambda *_: next(reviews))
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    assert gate.await_copilot_review("owner/repo", "1", "sha") == {"id": 9}


def test_await_copilot_review_returns_none_when_never_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "fetch_copilot_review", lambda *_: None)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setattr(gate, "REVIEW_POLL_ATTEMPTS", 3)
    assert gate.await_copilot_review("owner/repo", "1", "sha") is None


def test_count_unresolved_copilot_threads_counts_only_unresolved_copilot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data: gate.JsonObject = {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "nodes": [
                        {
                            "isResolved": False,
                            "comments": {"nodes": [{"author": {"login": "Copilot"}}]},
                        },
                        {
                            "isResolved": True,
                            "comments": {"nodes": [{"author": {"login": "Copilot"}}]},
                        },
                        {
                            "isResolved": False,
                            "comments": {"nodes": [{"author": {"login": "realSergiy"}}]},
                        },
                        {
                            "isResolved": False,
                            "comments": {"nodes": [{"author": {"login": "copilot-pull-request-reviewer"}}]},
                        },
                        {"isResolved": False, "comments": {"nodes": []}},
                    ]
                }
            }
        }
    }
    monkeypatch.setattr(gate, "_graphql", lambda *_: data)
    assert gate.count_unresolved_copilot_threads("owner/repo", "1") == EXPECTED_UNRESOLVED
