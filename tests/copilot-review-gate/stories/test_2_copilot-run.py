from __future__ import annotations

import urllib.error
from typing import TYPE_CHECKING

from fixtures import PR_READY, SHA, copilot_review, copilot_run

if TYPE_CHECKING:
    from fixtures import GateHarness


def test_2_1_1_blocks_the_merge_when_the_copilot_review_was_never_requested(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_READY)
    copilot_gate.set_check_run_reads([{"name": "ci"}])

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "failure"
    assert "was not requested" in copilot_gate.statuses[-1].description


def test_2_1_2_fails_the_job_when_the_check_runs_are_never_queryable(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_READY)
    copilot_gate.set_check_run_reads(urllib.error.URLError("network down"))

    exit_code = copilot_gate.run()

    assert exit_code == 1
    assert copilot_gate.statuses[-1].state == "error"
    assert "Could not query" in copilot_gate.statuses[-1].description


def test_2_2_1_keeps_polling_an_in_progress_run_until_it_completes(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_check_run_reads(
        [copilot_run("in_progress")],
        [copilot_run("in_progress")],
        [copilot_run("completed", "success")],
    )
    copilot_gate.set_reviews([copilot_review(SHA)])

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "success"


def test_2_2_2_blocks_the_merge_when_the_run_never_completes_in_time(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_READY)
    copilot_gate.set_check_run_reads([copilot_run("in_progress")])

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[-1].state == "error"
    assert "did not complete" in copilot_gate.statuses[-1].description
