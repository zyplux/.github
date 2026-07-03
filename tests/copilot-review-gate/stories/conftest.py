from __future__ import annotations

import urllib.request

import copilot_review_gate.cli as gate
import pytest
from fixtures import MAX_POLL_ATTEMPTS, PR, REPO, SHA, FakeGitHub, GateHarness

POLL_ATTEMPT_SETTINGS = (
    "READY_POLL_ATTEMPTS",
    "APPEAR_POLL_ATTEMPTS",
    "COMPLETE_POLL_ATTEMPTS",
    "REVIEW_POLL_ATTEMPTS",
)


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(urllib.request, "urlopen", fake.urlopen)
    monkeypatch.setattr(gate.time, "sleep", lambda *_: None)
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("REPO", REPO)
    monkeypatch.setenv("PR", PR)
    monkeypatch.setenv("SHA", SHA)
    for setting in POLL_ATTEMPT_SETTINGS:
        monkeypatch.setattr(gate, setting, MAX_POLL_ATTEMPTS)
    return fake


@pytest.fixture
def copilot_gate(github: FakeGitHub) -> GateHarness:
    return GateHarness(github)
