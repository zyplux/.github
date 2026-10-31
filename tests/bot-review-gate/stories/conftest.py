from __future__ import annotations

import http.client

import pytest
from fixtures import PR, REPO, SHA, FakeGitHub, GateHarness


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(http.client, "HTTPSConnection", fake.connect)
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("REPO", REPO)
    monkeypatch.setenv("PR", PR)
    monkeypatch.setenv("SHA", SHA)
    return fake


@pytest.fixture
def bot_gate(github: FakeGitHub) -> GateHarness:
    return GateHarness(github)
