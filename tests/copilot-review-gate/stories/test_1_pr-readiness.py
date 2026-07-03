from __future__ import annotations

import urllib.error
from typing import TYPE_CHECKING

from fixtures import PR_DRAFT, PR_READY

if TYPE_CHECKING:
    from fixtures import GateHarness


def test_1_1_1_proceeds_to_the_copilot_gate_once_the_pr_leaves_draft(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.set_draft_reads(PR_DRAFT, PR_READY)

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses[0].state == "pending"


def test_1_1_2_leaves_no_status_when_the_pr_never_leaves_draft(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_DRAFT)

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses == []


def test_1_1_3_fails_the_job_when_the_draft_state_is_never_readable(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(urllib.error.URLError("network down"))

    exit_code = copilot_gate.run()

    assert exit_code == 1
    assert copilot_gate.statuses[-1].state == "error"
    assert "draft state" in copilot_gate.statuses[-1].description


def test_1_1_4_treats_a_pr_read_as_draft_even_when_later_reads_error(copilot_gate: GateHarness) -> None:
    copilot_gate.set_draft_reads(PR_DRAFT, urllib.error.URLError("blip"))

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert copilot_gate.statuses == []
