from __future__ import annotations

import urllib.error
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fixtures import GateHarness


def test_4_1_1_continues_the_gate_when_the_pending_status_cannot_be_posted(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.github.fail_next_status_post(urllib.error.URLError("network down"))

    exit_code = copilot_gate.run()

    assert exit_code == 0
    assert [status.state for status in copilot_gate.statuses] == ["success"]


def test_4_2_1_fails_the_job_when_the_thread_query_returns_graphql_errors(copilot_gate: GateHarness) -> None:
    copilot_gate.arrange_clean_pass()
    copilot_gate.answer_thread_query_with_errors()

    exit_code = copilot_gate.run()

    assert exit_code == 1
    assert copilot_gate.statuses[-1].state == "error"
