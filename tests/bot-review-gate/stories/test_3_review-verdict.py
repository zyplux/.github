from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fixtures import (
    COPILOT_QUOTA_MESSAGE,
    LATER,
    PostedStatus,
    codex_comment,
    codex_quota,
    copilot_review,
    copilot_run,
    review_thread,
    thread_page,
)

if TYPE_CHECKING:
    from fixtures import GateHarness


@pytest.mark.parametrize(
    ("copilot", "codex", "expected"),
    [
        ("clean", "clean", "success"),
        ("quota", "clean", "success"),
        ("clean", "quota", "success"),
        ("quota", "quota", "failure"),
        ("missing", "clean", "success"),
        ("clean", "missing", "success"),
        ("missing", "missing", "pending"),
        ("quota", "missing", "pending"),
        ("missing", "quota", "pending"),
        ("pending", "clean", "pending"),
        ("failed", "clean", "failure"),
        ("quota", "findings", "failure"),
        ("findings", "quota", "failure"),
    ],
)
def test_3_1_1_requires_clean_reviews_from_every_participating_bot(
    bot_gate: GateHarness, copilot: str, codex: str, expected: str
) -> None:
    bot_gate.arrange_clean_pass()
    if copilot == "quota":
        bot_gate.set_check_run_reads([])
        bot_gate.set_reviews([copilot_review(body=COPILOT_QUOTA_MESSAGE)])
    elif copilot == "missing":
        bot_gate.set_check_run_reads([])
        bot_gate.set_reviews([])
    elif copilot == "pending":
        bot_gate.set_check_run_reads([copilot_run("in_progress")])
    elif copilot == "failed":
        bot_gate.set_copilot_run_completed("cancelled")
    elif copilot == "findings":
        bot_gate.set_review_threads(review_thread())
    if codex == "quota":
        bot_gate.set_codex_quota()
    elif codex == "missing":
        bot_gate.set_comments([])
    elif codex == "findings":
        bot_gate.set_review_threads(review_thread("chatgpt-codex-connector"))
        bot_gate.set_comments([codex_comment(has_findings=True, unresolved=True)])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == expected
    assert {status.context for status in bot_gate.statuses} == {"bot-review-complete"}


def test_3_1_2_links_success_to_the_review_evidence(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1] == PostedStatus(
        "success", "Copilot review clean; Codex review clean", "https://github.com/comment/1", "bot-review-complete"
    )


@pytest.mark.parametrize("author", ["copilot-pull-request-reviewer[bot]", "chatgpt-codex-connector[bot]"])
def test_3_1_3_ignores_earlier_reviews_when_the_other_bot_passes(bot_gate: GateHarness, author: str) -> None:
    bot_gate.arrange_clean_pass()
    older_review = {**copilot_review("older-head"), "user": {"login": author}}
    if author == "copilot-pull-request-reviewer[bot]":
        bot_gate.set_check_run_reads([])
        bot_gate.set_reviews([older_review])
    else:
        bot_gate.set_reviews([copilot_review(), older_review])
        bot_gate.set_comments([])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


@pytest.mark.parametrize(
    "author",
    ["Copilot", "copilot-pull-request-reviewer[bot]", "chatgpt-codex-connector", "chatgpt-codex-connector[bot]"],
)
def test_3_2_1_blocks_unresolved_findings_from_either_bot(bot_gate: GateHarness, author: str) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_review_threads(review_thread(author))

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "failure"
    assert "1 unresolved" in bot_gate.statuses[-1].description


def test_3_2_2_counts_only_unresolved_bot_threads(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_review_threads(
        review_thread(resolved=True), review_thread("maintainer"), review_thread(None), review_thread("copilot-helper")
    )

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


@pytest.mark.parametrize("stale_summary", [False, True])
def test_3_2_3_observes_thread_resolution_while_watching(bot_gate: GateHarness, *, stale_summary: bool) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_comments([codex_comment(has_findings=stale_summary, unresolved=stale_summary)])
    bot_gate.github.on("POST", "graphql", thread_page(review_thread("chatgpt-codex-connector")), thread_page())

    assert bot_gate.run() == 0
    assert [status.state for status in bot_gate.statuses] == ["pending", "failure", "success"]


def test_3_2_4_paginates_review_threads_before_passing(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    first = thread_page(cursor="next")
    second = thread_page(review_thread("chatgpt-codex-connector"))
    bot_gate.github.on("POST", "graphql", *[page for _ in range(4) for page in (first, second)])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "failure"
    assert any(body and '"cursor": "next"' in body for _, url, body in bot_gate.github.requests if url == "/graphql")


@pytest.mark.parametrize("unresolved_summary", [False, True])
def test_3_2_5_accepts_resolved_findings_in_the_codex_summary(
    bot_gate: GateHarness, *, unresolved_summary: bool
) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_comments([codex_comment(has_findings=True, unresolved=unresolved_summary)])
    bot_gate.set_review_threads(review_thread("chatgpt-codex-connector", resolved=True))

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


@pytest.mark.parametrize("commit_sha", ["headsha", "older-head"])
def test_3_2_6_quota_denial_does_not_erase_known_codex_findings(bot_gate: GateHarness, commit_sha: str) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_review_threads(review_thread("chatgpt-codex-connector"))
    quota = {**codex_quota(), "created_at": LATER}
    bot_gate.set_comments([codex_comment(commit_sha, status="failed", has_findings=True, unresolved=True), quota])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "failure"


def test_3_2_7_accepts_a_clean_current_head_review_after_resolving_older_findings(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_comments([codex_comment("older-head", has_findings=True, unresolved=True)])
    bot_gate.set_review_threads(review_thread("chatgpt-codex-connector", resolved=True))

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


@pytest.mark.parametrize("state", ["failed", "cancelled", "error"])
def test_3_3_1_codex_failures_do_not_count_as_unavailability(bot_gate: GateHarness, state: str) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_comments([codex_comment(status=state)])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "failure"
