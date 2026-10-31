from __future__ import annotations

from typing import TYPE_CHECKING

from fixtures import PR_DRAFT, PR_READY

if TYPE_CHECKING:
    import pytest
    from fixtures import GateHarness


def test_1_1_1_checks_readiness_on_each_event(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_draft_reads(PR_DRAFT, PR_READY)

    assert bot_gate.run() == 0
    assert bot_gate.statuses == []
    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


def test_1_1_2_leaves_no_status_when_the_pr_stays_draft(bot_gate: GateHarness) -> None:
    bot_gate.set_draft_reads(PR_DRAFT)

    assert bot_gate.run() == 0
    assert bot_gate.statuses == []


def test_1_1_3_reports_unreadable_pr_state(bot_gate: GateHarness) -> None:
    bot_gate.set_draft_reads(OSError("network down"))

    assert bot_gate.run() == 1
    assert bot_gate.statuses[-1].state == "error"


def test_1_1_4_stops_when_the_head_changes(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_draft_reads({"draft": False, "head": {"sha": "new-head"}})

    assert bot_gate.run() == 0
    assert all(status.state != "success" for status in bot_gate.statuses)


def test_1_1_5_loads_the_current_head_for_manual_refresh(
    bot_gate: GateHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot_gate.arrange_clean_pass()
    monkeypatch.delenv("SHA")

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"


def test_1_1_6_skips_closed_prs(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_check_run_reads([])
    bot_gate.set_reviews([])
    bot_gate.set_draft_reads({**PR_READY, "state": "closed"})

    assert bot_gate.run() == 0
    assert bot_gate.statuses == []
