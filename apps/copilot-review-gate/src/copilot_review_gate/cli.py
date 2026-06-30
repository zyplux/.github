from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import cast

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type JsonObject = dict[str, Json]

API_ROOT = "https://api.github.com"
HTTP_TIMEOUT_SECONDS = 30
STATUS_CONTEXT = "copilot-review-complete"
COPILOT_CHECK_NAME = "copilot-pull-request-reviewer"
COPILOT_LOGIN_FRAGMENT = "copilot"

READY_POLL_ATTEMPTS = 40
READY_POLL_SECONDS = 5
APPEAR_POLL_ATTEMPTS = 12
APPEAR_POLL_SECONDS = 15
COMPLETE_POLL_ATTEMPTS = 60
COMPLETE_POLL_SECONDS = 15
REVIEW_POLL_ATTEMPTS = 6
REVIEW_POLL_SECONDS = 5

REVIEW_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes {
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}
"""

logger = logging.getLogger(__name__)


class GraphQlError(RuntimeError):
    def __init__(self, errors: object) -> None:
        super().__init__(f"GraphQL request failed: {errors}")


def _send(method: str, url: str, data: bytes | None, headers: dict[str, str]) -> bytes:
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme != "https":
        msg = f"refusing to open non-https URL with scheme {scheme!r}"
        raise ValueError(msg)
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310
    for key, value in headers.items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read()


def _auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _request(method: str, path: str, payload: JsonObject | None = None) -> Json:
    data = json.dumps(payload).encode() if payload is not None else None
    body = _send(method, f"{API_ROOT}/{path}", data, _auth_headers())
    return json.loads(body) if body else None


def _graphql(query: str, variables: JsonObject) -> JsonObject:
    data = json.dumps({"query": query, "variables": variables}).encode()
    headers = {**_auth_headers(), "Content-Type": "application/json"}
    body = _send("POST", f"{API_ROOT}/graphql", data, headers)
    result = json.loads(body)
    if result.get("errors"):
        raise GraphQlError(result["errors"])
    return cast("JsonObject", result["data"])


def read_is_draft(repo: str, pr: str) -> bool:
    pull = cast("JsonObject", _request("GET", f"repos/{repo}/pulls/{pr}"))
    return bool(pull["draft"])


def find_copilot_run(check_runs: list[JsonObject]) -> JsonObject | None:
    return next((run for run in check_runs if run.get("name") == COPILOT_CHECK_NAME), None)


def fetch_copilot_run(repo: str, sha: str) -> JsonObject | None:
    query = urllib.parse.urlencode({"check_name": COPILOT_CHECK_NAME, "per_page": 100})
    result = cast("JsonObject", _request("GET", f"repos/{repo}/commits/{sha}/check-runs?{query}") or {})
    return find_copilot_run(cast("list[JsonObject]", result.get("check_runs", [])))


def is_copilot_author(login: str) -> bool:
    return COPILOT_LOGIN_FRAGMENT in login.lower()


def fetch_copilot_review(repo: str, pr: str, sha: str) -> JsonObject | None:
    reviews = cast("list[JsonObject]", _request("GET", f"repos/{repo}/pulls/{pr}/reviews?per_page=100") or [])
    return next(
        (
            review
            for review in reviews
            if review.get("commit_id") == sha
            and is_copilot_author(cast("str", cast("JsonObject", review.get("user") or {}).get("login", "")))
        ),
        None,
    )


def count_unresolved_copilot_threads(repo: str, pr: str) -> int:
    owner, name = repo.split("/", 1)
    data = _graphql(REVIEW_THREADS_QUERY, {"owner": owner, "name": name, "number": int(pr)})
    threads = cast(
        "list[JsonObject]",
        cast("JsonObject", cast("JsonObject", cast("JsonObject", data["repository"])["pullRequest"])["reviewThreads"])[
            "nodes"
        ],
    )
    unresolved = 0
    for thread in threads:
        if thread["isResolved"]:
            continue
        comments = cast("list[JsonObject]", cast("JsonObject", thread["comments"])["nodes"])
        if not comments:
            continue
        author = cast("JsonObject", comments[0].get("author") or {})
        if is_copilot_author(cast("str", author.get("login", ""))):
            unresolved += 1
    return unresolved


def build_status(conclusion: str) -> tuple[str, str]:
    if conclusion == "success":
        return "success", "Copilot review success"
    return "failure", f"Copilot review concluded: {conclusion}"


def post_status(repo: str, sha: str, state: str, description: str, target_url: str = "") -> None:
    payload: JsonObject = {"state": state, "context": STATUS_CONTEXT, "description": description}
    if target_url:
        payload["target_url"] = target_url
    _request("POST", f"repos/{repo}/statuses/{sha}", payload)


def wait_for_ready(repo: str, pr: str) -> str:
    read_ok = False
    for _ in range(READY_POLL_ATTEMPTS):
        try:
            draft = read_is_draft(repo, pr)
        except urllib.error.URLError:
            draft = None
        if draft is False:
            return "ready"
        if draft is True:
            read_ok = True
        time.sleep(READY_POLL_SECONDS)
    return "draft" if read_ok else "unreadable"


def await_copilot_run(repo: str, sha: str) -> tuple[str, JsonObject | None]:
    fetched_ok = False
    run = None
    for _ in range(APPEAR_POLL_ATTEMPTS):
        try:
            run = fetch_copilot_run(repo, sha)
            fetched_ok = True
        except urllib.error.URLError:
            run = None
        if run is not None:
            break
        time.sleep(APPEAR_POLL_SECONDS)
    if run is None:
        return ("not_requested", None) if fetched_ok else ("unqueryable", None)

    for _ in range(COMPLETE_POLL_ATTEMPTS):
        if run is not None and run.get("status") == "completed":
            return ("completed", run)
        time.sleep(COMPLETE_POLL_SECONDS)
        with contextlib.suppress(urllib.error.URLError):
            run = fetch_copilot_run(repo, sha)
    return ("incomplete", run)


def await_copilot_review(repo: str, pr: str, sha: str) -> JsonObject | None:
    for _ in range(REVIEW_POLL_ATTEMPTS):
        try:
            review = fetch_copilot_review(repo, pr, sha)
        except urllib.error.URLError:
            review = None
        if review is not None:
            return review
        time.sleep(REVIEW_POLL_SECONDS)
    return None


def _report_not_ready(repo: str, sha: str, readiness: str) -> int:
    if readiness == "unreadable":
        post_status(repo, sha, "error", "Could not read PR draft state to gate the Copilot review")
        return 1
    logger.info("PR is still draft after waiting; Copilot review is not expected, leaving no status")
    return 0


def _post_pending(repo: str, sha: str) -> None:
    try:
        post_status(repo, sha, "pending", "Waiting for Copilot review to complete")
    except urllib.error.URLError as error:
        logger.warning("::warning::could not post pending %s status (continuing): %s", STATUS_CONTEXT, error)


def _report_incomplete_run(repo: str, sha: str, outcome: str) -> int:
    if outcome == "not_requested":
        post_status(
            repo,
            sha,
            "failure",
            "Copilot review was not requested for this push — re-run `just pr` to re-trigger it",
        )
        return 0
    if outcome == "incomplete":
        post_status(repo, sha, "error", "Copilot review started but did not complete in time")
        return 0
    post_status(repo, sha, "error", "Could not query the Copilot review check-run")
    return 1


def _report_review_threads(repo: str, pr: str, sha: str, target_url: str) -> int:
    await_copilot_review(repo, pr, sha)
    try:
        unresolved = count_unresolved_copilot_threads(repo, pr)
    except urllib.error.URLError, RuntimeError, KeyError:
        post_status(repo, sha, "error", "Could not query Copilot review comments")
        logger.exception("::error::could not count Copilot review threads")
        return 1

    if unresolved == 0:
        state, description = build_status("success")
        post_status(repo, sha, state, description, target_url)
        return 0

    noun = "comment" if unresolved == 1 else "comments"
    post_status(
        repo,
        sha,
        "failure",
        f"Copilot left {unresolved} unresolved {noun} — resolve them, then re-run `just pr`",
    )
    return 0


def main() -> int:
    repo = os.environ["REPO"]
    pr = os.environ["PR"]
    sha = os.environ["SHA"]

    readiness = wait_for_ready(repo, pr)
    if readiness != "ready":
        return _report_not_ready(repo, sha, readiness)

    _post_pending(repo, sha)

    outcome, run = await_copilot_run(repo, sha)
    if outcome != "completed":
        return _report_incomplete_run(repo, sha, outcome)

    record = run or {}
    conclusion = cast("str", record.get("conclusion") or "")
    target_url = cast("str", record.get("details_url") or "")
    if conclusion != "success":
        state, description = build_status(conclusion)
        post_status(repo, sha, state, description, target_url)
        return 0

    return _report_review_threads(repo, pr, sha, target_url)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    sys.exit(main())
