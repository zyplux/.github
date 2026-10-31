from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fixtures import (
    COPILOT_QUOTA_MESSAGE,
    LATER,
    SHA,
    TIMESTAMP,
    codex_comment,
    codex_quota,
    copilot_review,
    copilot_run,
)

if TYPE_CHECKING:
    from fixtures import GateHarness


@pytest.mark.parametrize("check_status", [None, "queued"])
def test_2_1_1_accepts_codex_when_copilot_has_not_started(bot_gate: GateHarness, check_status: str | None) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([] if check_status is None else [copilot_run(check_status)])
    bot_gate.set_reviews([])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
    assert bot_gate.statuses[-1].description == "Codex review clean"


def test_2_1_2_waits_for_both_current_head_reviews(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_reviews([copilot_review("old-sha")], [copilot_review()])
    bot_gate.set_comments([codex_comment("old-sha")], [codex_comment()])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


@pytest.mark.parametrize("minutes", [17, 30])
def test_2_1_3_accepts_reviews_within_thirty_minutes(
    full_watch_gate: GateHarness, poll_sleeps: list[float], minutes: int
) -> None:
    full_watch_gate.arrange_clean_pass()
    full_watch_gate.set_check_run_reads(*[[copilot_run("in_progress")]] * (minutes * 60 // 15), [copilot_run()])

    assert full_watch_gate.run() == 0
    assert full_watch_gate.statuses[-1].state == "success"
    assert sum(poll_sleeps) == minutes * 60


def test_2_1_4_keeps_timed_out_reviews_pending(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([copilot_run("in_progress")])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<!-- codex-review-state:v1 invalid -->",
        "<!-- codex-review-state:v1 null -->",
        "<!-- codex-review-state:v1 {} -->",
    ],
)
def test_2_2_1_rejects_missing_or_malformed_codex_evidence(bot_gate: GateHarness, body: str) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([])
    bot_gate.set_comments([{**codex_comment(), "body": body}])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state != "success"


def test_2_2_2_rejects_a_spoofed_bot_summary(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([])
    bot_gate.set_comments([{**codex_comment(), "user": {"login": "codex-helper"}}])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_3_requires_code_review_instead_of_security_review(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    comment = codex_comment()
    comment["body"] = str(comment["body"]).replace("code_review", "security_review")
    bot_gate.set_comments([comment])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_4_rechecks_a_new_codex_review_request_after_quota_denial(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_codex_quota({"user": {"login": "maintainer"}, "body": "@codex review", "created_at": LATER})

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_5_uses_newer_review_state_after_a_codex_quota_denial(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_codex_quota({**codex_comment(status="in_progress"), "updated_at": LATER})

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_6_ignores_a_copilot_quota_denial_for_an_older_head(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([copilot_review("old-sha", COPILOT_QUOTA_MESSAGE)])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
    assert bot_gate.statuses[-1].description == "Codex review clean"


def test_2_2_7_waits_for_a_copilot_retry_after_quota_denial(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_reviews([copilot_review(SHA, COPILOT_QUOTA_MESSAGE)])
    bot_gate.set_check_run_reads([{**copilot_run("in_progress"), "started_at": LATER}])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_8_observes_newer_codex_summary_edits(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    newer = {**codex_comment(), "updated_at": LATER}
    older = {**codex_quota(), "created_at": TIMESTAMP}
    bot_gate.set_comments([newer, older])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


def test_2_2_13_accepts_completed_codex_summary_without_unresolved_finding_flag(
    bot_gate: GateHarness,
) -> None:
    bot_gate.arrange_clean_pass()
    comment = codex_comment(has_findings=True)
    body = str(comment["body"]).replace('"has_unresolved_findings": false', '"has_unresolved_findings": null')
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([])
    bot_gate.set_comments([{**comment, "body": body}])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
    assert bot_gate.statuses[-1].description == "Codex review clean"


@pytest.mark.parametrize("state", ["DISMISSED", "PENDING", "UNKNOWN"])
def test_2_2_9_rejects_invalid_copilot_review_states(bot_gate: GateHarness, state: str) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_reviews([copilot_review(state=state)])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


def test_2_2_10_rejects_a_dismissed_quota_response(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_reviews([copilot_review(body=COPILOT_QUOTA_MESSAGE, state="DISMISSED")])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "pending"


@pytest.mark.parametrize("has_summary", [False, True])
def test_2_2_11_ignores_codex_quota_denial_without_current_head_context(
    bot_gate: GateHarness, *, has_summary: bool
) -> None:
    bot_gate.arrange_clean_pass()
    comments = [codex_quota()]
    if has_summary:
        comments.insert(0, {**codex_comment("older-head", status="failed"), "updated_at": "2026-10-19T00:59:00Z"})
    bot_gate.set_comments(comments)

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
    assert bot_gate.statuses[-1].description == "Copilot review clean"


def test_2_2_12_recognizes_insufficient_remaining_copilot_quota(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([
        copilot_review(
            body=(
                "Copilot was unable to review this pull request because the user who requested the review "
                "has insufficient remaining quota."
            )
        )
    ])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
    assert bot_gate.statuses[-1].description == "Codex review clean"
