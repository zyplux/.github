from __future__ import annotations

import http.client

import bot_review_gate.bot_review_complete as gate
import pytest
from fixtures import MAX_POLL_ATTEMPTS, PR, REPO, SHA, FakeGitHub, GateHarness


@pytest.fixture
def poll_sleeps() -> list[float]:
    return []


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch, poll_sleeps: list[float]) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(http.client, "HTTPSConnection", fake.connect)
    monkeypatch.setattr(gate.time, "sleep", poll_sleeps.append)
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("REPO", REPO)
    monkeypatch.setenv("PR", PR)
    monkeypatch.setenv("SHA", SHA)
    monkeypatch.setattr(gate, "READY_POLL_ATTEMPTS", MAX_POLL_ATTEMPTS)
    monkeypatch.setattr(gate, "REVIEW_POLL_ATTEMPTS", MAX_POLL_ATTEMPTS)
    return fake


@pytest.fixture
def bot_gate(github: FakeGitHub) -> GateHarness:
    return GateHarness(github)


@pytest.fixture
def full_watch_gate(bot_gate: GateHarness, monkeypatch: pytest.MonkeyPatch) -> GateHarness:
    monkeypatch.setattr(gate, "REVIEW_POLL_ATTEMPTS", 120)
    return bot_gate
