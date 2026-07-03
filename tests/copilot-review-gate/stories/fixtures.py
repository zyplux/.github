from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Self, cast

import copilot_review_gate.cli as gate

REPO = "zyplux/demo"
PR = "1"
SHA = "headsha"

MAX_POLL_ATTEMPTS = 3

type Reply = Exception | object

PR_DRAFT: gate.JsonObject = {"draft": True}
PR_READY: gate.JsonObject = {"draft": False}


def copilot_run(status: str, conclusion: str = "", details_url: str = "") -> gate.JsonObject:
    return {"name": gate.COPILOT_CHECK_NAME, "status": status, "conclusion": conclusion, "details_url": details_url}


def copilot_review(commit_id: str) -> gate.JsonObject:
    return {"commit_id": commit_id, "user": {"login": "copilot-pull-request-reviewer[bot]"}}


def review_thread(author: str | None = "Copilot", *, resolved: bool = False) -> gate.JsonObject:
    comments: list[gate.Json] = [] if author is None else [{"author": {"login": author}}]
    return {"isResolved": resolved, "comments": {"nodes": comments}}


@dataclass(frozen=True)
class PostedStatus:
    state: str
    description: str
    target_url: str


@dataclass(frozen=True)
class FakeHttpResponse:
    body: bytes

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


@dataclass
class FakeGitHub:
    routes: dict[tuple[str, str], list[Reply]] = field(default_factory=dict)
    posted_statuses: list[PostedStatus] = field(default_factory=list)
    status_post_failures: list[Exception] = field(default_factory=list)

    def on(self, method: str, path: str, *replies: Reply) -> None:
        self.routes[method, path] = list(replies)

    def fail_next_status_post(self, error: Exception) -> None:
        self.status_post_failures.append(error)

    def urlopen(self, request: urllib.request.Request, timeout: float) -> FakeHttpResponse:
        del timeout
        method = request.get_method()
        path = urllib.parse.urlsplit(request.full_url).path.removeprefix("/")
        if method == "POST" and path == f"repos/{REPO}/statuses/{SHA}":
            return self._record_status(request)
        reply = self._next_reply(method, path)
        if isinstance(reply, Exception):
            raise reply
        return FakeHttpResponse(json.dumps(reply).encode())

    def _record_status(self, request: urllib.request.Request) -> FakeHttpResponse:
        if self.status_post_failures:
            raise self.status_post_failures.pop(0)
        payload = cast("gate.JsonObject", json.loads(cast("bytes", request.data)))
        self.posted_statuses.append(
            PostedStatus(
                cast("str", payload["state"]),
                cast("str", payload["description"]),
                cast("str", payload.get("target_url", "")),
            )
        )
        return FakeHttpResponse(b"{}")

    def _next_reply(self, method: str, path: str) -> Reply:
        replies = self.routes.get((method, path))
        if not replies:
            msg = f"unexpected GitHub call: {method} {path}"
            raise AssertionError(msg)
        return replies.pop(0) if len(replies) > 1 else replies[0]


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
        self.set_reviews([copilot_review(SHA)])
        self.set_review_threads()

    def set_draft_reads(self, *reads: Reply) -> None:
        self.github.on("GET", f"repos/{REPO}/pulls/{PR}", *reads)

    def set_check_run_reads(self, *reads: Reply) -> None:
        replies = tuple({"check_runs": read} if isinstance(read, list) else read for read in reads)
        self.github.on("GET", f"repos/{REPO}/commits/{SHA}/check-runs", *replies)

    def set_copilot_run_completed(self, conclusion: str = "success", details_url: str = "") -> None:
        self.set_check_run_reads([copilot_run("completed", conclusion, details_url)])

    def set_reviews(self, reviews: list[gate.JsonObject]) -> None:
        self.github.on("GET", f"repos/{REPO}/pulls/{PR}/reviews", reviews)

    def fail_review_reads(self, error: Exception) -> None:
        self.github.on("GET", f"repos/{REPO}/pulls/{PR}/reviews", error)

    def set_review_threads(self, *threads: gate.JsonObject) -> None:
        data = {"repository": {"pullRequest": {"reviewThreads": {"nodes": list(threads)}}}}
        self.github.on("POST", "graphql", {"data": data})

    def fail_thread_query(self, error: Exception) -> None:
        self.github.on("POST", "graphql", error)

    def answer_thread_query_with_errors(self) -> None:
        self.github.on("POST", "graphql", {"errors": [{"message": "query failed"}]})
