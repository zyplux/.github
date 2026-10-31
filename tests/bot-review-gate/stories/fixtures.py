from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from typing import cast

import bot_review_gate.bot_review_complete as gate

REPO = "zyplux/demo"
PR = "1"
SHA = "headsha"
TIMESTAMP = "2026-10-19T01:00:00Z"
LATER = "2026-10-19T01:01:00Z"
COPILOT_QUOTA_MESSAGE = (
    "Copilot was unable to review this pull request because the user who requested the review "
    "has reached their quota limit."
)

type Reply = Exception | object

PR_DRAFT: gate.JsonObject = {"draft": True, "head": {"sha": SHA}}
PR_READY: gate.JsonObject = {"draft": False, "head": {"sha": SHA}}


def copilot_run(status: str = "completed", conclusion: str = "success") -> gate.JsonObject:
    return {
        "name": gate.COPILOT_CHECK_NAME,
        "status": status,
        "conclusion": conclusion,
        "details_url": "https://github.com/run/1",
    }


def copilot_review(commit_id: str = SHA, body: str = "", state: str = "COMMENTED") -> gate.JsonObject:
    return {
        "commit_id": commit_id,
        "body": body,
        "state": state,
        "submitted_at": TIMESTAMP,
        "user": {"login": "copilot-pull-request-reviewer[bot]"},
    }


def codex_comment(
    commit_sha: str = SHA,
    status: str = "completed",
    *,
    has_findings: bool = False,
    unresolved: bool = False,
) -> gate.JsonObject:
    review = {
        "commit_sha": commit_sha,
        "status": status,
        "has_any_findings": has_findings,
        "has_unresolved_findings": unresolved,
    }
    return {
        "user": {"login": "chatgpt-codex-connector[bot]"},
        "body": gate.CODEX_STATE_MARKER + json.dumps({"code_review": review}) + " -->",
        "updated_at": TIMESTAMP,
        "html_url": "https://github.com/comment/1",
    }


def codex_quota() -> gate.JsonObject:
    return {
        "user": {"login": "chatgpt-codex-connector[bot]"},
        "body": "You have reached your Codex usage limits for code reviews. You can see your limits in the "
        "[Codex usage dashboard](https://chatgpt.com/codex/cloud/settings/usage).",
        "created_at": TIMESTAMP,
    }


def review_thread(author: str | None = "Copilot", *, resolved: bool = False) -> gate.JsonObject:
    comments: list[gate.Json] = [] if author is None else [{"author": {"login": author}}]
    return {"isResolved": resolved, "comments": {"nodes": comments}}


def thread_page(*threads: gate.JsonObject, cursor: str | None = None) -> gate.JsonObject:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": list(threads),
                        "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                    }
                }
            }
        }
    }


@dataclass(frozen=True)
class PostedStatus:
    state: str
    description: str
    target_url: str
    context: str


@dataclass(frozen=True)
class FakeHttpResponse:
    body: bytes
    status: int = 200

    def read(self) -> bytes:
        return self.body


@dataclass
class FakeConnection:
    github: FakeGitHub
    response: FakeHttpResponse | None = None

    def request(self, method: str, url: str, body: str | None, headers: dict[str, str]) -> None:
        assert headers["Authorization"] == "Bearer test-token"
        assert headers.get("User-Agent")
        self.response = self.github.request(method, url, body)

    def getresponse(self) -> FakeHttpResponse:
        assert self.response is not None
        return self.response

    def close(self) -> None:
        pass


@dataclass
class FakeGitHub:
    routes: dict[tuple[str, str], list[Reply]] = field(default_factory=dict)
    posted_statuses: list[PostedStatus] = field(default_factory=list)
    status_post_failures: list[Exception] = field(default_factory=list)
    requests: list[tuple[str, str, str | None]] = field(default_factory=list)

    def on(self, method: str, path: str, *replies: Reply) -> None:
        self.routes[method, path] = list(replies)

    def connect(self, host: str, timeout: float) -> FakeConnection:
        assert host == "api.github.com"
        assert timeout > 0
        return FakeConnection(self)

    def request(self, method: str, url: str, body: str | None) -> FakeHttpResponse:
        self.requests.append((method, url, body))
        path = urllib.parse.urlsplit(url).path.removeprefix("/")
        if method == "POST" and path == f"repos/{REPO}/statuses/{SHA}":
            return self._record_status(body)
        replies = self.routes.get((method, url.removeprefix("/"))) or self.routes.get((method, path))
        assert replies, f"unexpected GitHub call: {method} {url}"
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, FakeHttpResponse):
            return reply
        return FakeHttpResponse(json.dumps(reply).encode())

    def _record_status(self, body: str | None) -> FakeHttpResponse:
        if self.status_post_failures:
            raise self.status_post_failures.pop(0)
        assert body is not None
        payload = cast("gate.JsonObject", json.loads(body))
        self.posted_statuses.append(
            PostedStatus(
                cast("str", payload["state"]),
                cast("str", payload["description"]),
                cast("str", payload.get("target_url", "")),
                cast("str", payload["context"]),
            )
        )
        return FakeHttpResponse(b"{}")


@dataclass(frozen=True)
class GateHarness:
    github: FakeGitHub

    @property
    def statuses(self) -> list[PostedStatus]:
        return self.github.posted_statuses

    @staticmethod
    def run() -> int:
        return gate.main()

    def arrange_clean_pass(self) -> None:
        self.set_draft_reads(PR_READY)
        self.set_copilot_run_completed()
        self.set_reviews([copilot_review()])
        self.set_comments([codex_comment()])
        self.set_review_threads()

    def set_draft_reads(self, *reads: Reply) -> None:
        self.github.on("GET", f"repos/{REPO}/pulls/{PR}", *reads)

    def set_check_run_reads(self, *reads: Reply) -> None:
        replies = tuple({"check_runs": read} if isinstance(read, list) else read for read in reads)
        self.github.on("GET", f"repos/{REPO}/commits/{SHA}/check-runs", *replies)

    def set_copilot_run_completed(self, conclusion: str = "success") -> None:
        self.set_check_run_reads([copilot_run(conclusion=conclusion)])

    def set_reviews(self, *reads: Reply) -> None:
        self.github.on("GET", f"repos/{REPO}/pulls/{PR}/reviews", *reads)

    def set_comments(self, *reads: Reply) -> None:
        self.github.on("GET", f"repos/{REPO}/issues/{PR}/comments", *reads)

    def set_review_threads(self, *threads: gate.JsonObject) -> None:
        self.github.on("POST", "graphql", thread_page(*threads))

    def set_codex_quota(self, *comments: gate.JsonObject) -> None:
        summary = {**codex_comment(status="failed"), "updated_at": "2026-10-19T00:59:00Z"}
        self.set_comments([summary, codex_quota(), *comments])
