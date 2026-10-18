from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fixtures import PR, REPO, FakeHttpResponse, codex_comment

if TYPE_CHECKING:
    from fixtures import GateHarness


def test_4_1_1_continues_when_the_pending_status_post_fails(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.github.status_post_failures.append(OSError("network down"))

    assert bot_gate.run() == 0
    assert [status.state for status in bot_gate.statuses] == ["success"]


@pytest.mark.parametrize("endpoint", ["reviews", "comments", "check-runs", "threads"])
def test_4_2_1_blocks_when_review_state_cannot_be_read(bot_gate: GateHarness, endpoint: str) -> None:
    bot_gate.arrange_clean_pass()
    error = OSError("network down")
    if endpoint == "reviews":
        bot_gate.set_reviews(error)
    elif endpoint == "comments":
        bot_gate.set_comments(error)
    elif endpoint == "check-runs":
        bot_gate.set_check_run_reads(error)
    else:
        bot_gate.github.on("POST", "graphql", error)

    assert bot_gate.run() == 1
    assert bot_gate.statuses[-1].state == "error"


def test_4_2_2_blocks_when_graphql_returns_errors(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.github.on("POST", "graphql", {"errors": [{"message": "query failed"}]})

    assert bot_gate.run() == 1
    assert bot_gate.statuses[-1].state == "error"


def test_4_2_3_blocks_when_github_denies_api_access(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    bot_gate.set_comments(FakeHttpResponse(b"{}", 403))

    assert bot_gate.run() == 1
    assert bot_gate.statuses[-1].state == "error"


def test_4_2_4_paginates_issue_comments_for_codex_evidence(bot_gate: GateHarness) -> None:
    bot_gate.arrange_clean_pass()
    path = f"repos/{REPO}/issues/{PR}/comments"
    bot_gate.github.on("GET", f"{path}?per_page=100&page=1", [{}] * 100)
    bot_gate.github.on("GET", f"{path}?per_page=100&page=2", [codex_comment()])

    assert bot_gate.run() == 0
    assert bot_gate.statuses[-1].state == "success"
