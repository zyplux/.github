from __future__ import annotations

import urllib.error
from typing import TYPE_CHECKING

from fixtures import PR_READY, SHA, PostedStatus, copilot_review, review_thread

if TYPE_CHECKING:
    from fixtures import GateHarness


def test_3_1_1_posts_the_success_status_when_the_review_is_clean(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1] == PostedStatus("success", "Copilot review success", "")


def test_3_1_2_links_the_success_status_to_the_copilot_run_details(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_copilot_run_completed(details_url="https://github.com/zyplux/demo/runs/1")

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].target_url == "https://github.com/zyplux/demo/runs/1"


def test_3_2_1_blocks_with_the_conclusion_without_counting_threads(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_READY)
    copilot_gate.set_copilot_run_completed("cancelled")

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "failure"
    assert "cancelled" in copilot_gate.statuses[-1].description


def test_3_3_1_blocks_the_merge_while_copilot_comments_stay_unresolved(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_review_threads(review_thread(), review_thread())

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "failure"
    assert "2 unresolved comments" in copilot_gate.statuses[-1].description


def test_3_3_2_counts_only_unresolved_threads_authored_by_copilot(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_review_threads(
        review_thread(resolved=True),
        review_thread("realSergiy"),
        review_thread(None),
        review_thread("copilot-pull-request-reviewer[bot]"),
    )

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert "1 unresolved comment" in copilot_gate.statuses[-1].description


def test_3_3_3_fails_the_job_when_the_threads_cannot_be_queried(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.fail_thread_query(urllib.error.URLError("network down"))

    exit_code = copilot_gate.run()

    assert exit_code == 1
    assert copilot_gate.statuses[-1].state == "error"
    assert "review comments" in copilot_gate.statuses[-1].description


def test_3_3_4_posts_the_verdict_even_when_no_review_matches_the_head_sha(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_reviews([
        copilot_review("some-other-sha"),
        {"commit_id": SHA, "user": {"login": "realSergiy"}},
    ])

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "success"


def test_3_3_5_posts_the_verdict_even_when_the_review_reads_keep_erroring(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.fail_review_reads(urllib.error.URLError("network down"))

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "success"
