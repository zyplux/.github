from __future__ import annotations

import http.client
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from typing import Literal, cast

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type JsonObject = dict[str, Json]
type ReviewState = Literal["missing", "pending", "clean", "unavailable", "blocked"]

STATUS_CONTEXT = "bot-review-complete"
COPILOT_CHECK_NAME = "copilot-pull-request-reviewer"
COPILOT_LOGINS = {"copilot", "copilot-pull-request-reviewer"}
CODEX_LOGIN = "chatgpt-codex-connector"
CODEX_STATE_MARKER = "<!-- codex-review-state:v1 "
COPILOT_QUOTA_MESSAGES = {
    "copilot was unable to review this pull request because the user who requested the review " + reason
    for reason in ("has reached their quota limit.", "has insufficient remaining quota.")
}
CODEX_QUOTA_PREFIX = "you have reached your codex usage limits for code reviews"
PAGE_SIZE = 100
HTTP_TIMEOUT_SECONDS = 30
READY_POLL_ATTEMPTS = 40
READY_POLL_SECONDS = 5
REVIEW_POLL_ATTEMPTS = 120
REVIEW_POLL_SECONDS = 15

REVIEW_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first: 1) {
            nodes { author { login } }
          }
        }
      }
    }
  }
}
"""

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BotReview:
    state: ReviewState
    description: str
    url: str = ""
    commit_sha: str = ""


class GitHubApiError(RuntimeError):
    def __init__(self, status: int) -> None:
        super().__init__(f"GitHub API returned HTTP {status}")


class GraphQlError(RuntimeError):
    def __init__(self, errors: object) -> None:
        super().__init__(f"GraphQL request failed: {errors}")


def _request(method: str, path: str, payload: JsonObject | None = None) -> Json:
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "zyplux-bot-review-gate",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload) if payload is not None else None
    connection = http.client.HTTPSConnection("api.github.com", timeout=HTTP_TIMEOUT_SECONDS)
    try:
        connection.request(method, f"/{path}", body, headers)
        response = connection.getresponse()
        if response.status >= HTTPStatus.BAD_REQUEST:
            raise GitHubApiError(response.status)
        content = response.read()
        return json.loads(content) if content else None
    finally:
        connection.close()


def fetch_pages(path: str, collection: str = "") -> list[JsonObject]:
    records: list[JsonObject] = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        payload = _request("GET", f"{path}{separator}per_page={PAGE_SIZE}&page={page}")
        batch = cast("list[JsonObject]", cast("JsonObject", payload)[collection] if collection else payload)
        records.extend(batch)
        if len(batch) < PAGE_SIZE:
            return records
        page += 1


def fetch_pull(repo: str, pr: str) -> JsonObject:
    return cast("JsonObject", _request("GET", f"repos/{repo}/pulls/{pr}"))


def get_head_sha(pull: JsonObject) -> str:
    return cast("str", cast("JsonObject", pull["head"])["sha"])


def get_author(record: JsonObject) -> str:
    author = cast("JsonObject", record.get("user") or record.get("author") or {})
    return cast("str", author.get("login", "")).removesuffix("[bot]").casefold()


def get_activity_time(record: JsonObject) -> str:
    return cast("str", record.get("updated_at") or record.get("submitted_at") or record.get("created_at") or "")


def find_copilot_review(reviews: list[JsonObject], runs: list[JsonObject], sha: str) -> BotReview:
    review = next(
        (
            review
            for review in reversed(reviews)
            if review.get("commit_id") == sha and get_author(review) in COPILOT_LOGINS
        ),
        None,
    )
    run = next((run for run in runs if run.get("name") == COPILOT_CHECK_NAME), None)
    if review is not None:
        body = cast("str", review.get("body") or "").strip().casefold()
        started_at = cast("str", (run or {}).get("started_at") or "")
        if (
            body in COPILOT_QUOTA_MESSAGES
            and review.get("state") == "COMMENTED"
            and started_at <= get_activity_time(review)
        ):
            return BotReview("unavailable", "Copilot quota exhausted", cast("str", review.get("html_url") or ""))
    if run is None or run.get("status") != "completed":
        is_missing = review is None and (run is None or run.get("status") == "queued")
        return BotReview(
            "missing" if is_missing else "pending",
            "Copilot review not started" if is_missing else "Waiting for Copilot review",
        )
    url = cast("str", run.get("details_url") or "")
    conclusion = run.get("conclusion")
    if conclusion != "success":
        return BotReview("blocked", f"Copilot review concluded: {conclusion}", url)
    if review is None or review.get("state") not in {"COMMENTED", "APPROVED", "CHANGES_REQUESTED"}:
        return BotReview("pending", "Waiting for Copilot review on the current head", url)
    if review.get("state") == "CHANGES_REQUESTED":
        return BotReview("blocked", "Copilot requested changes", url)
    return BotReview("clean", "Copilot review clean", url)


def parse_codex_state(comment: JsonObject, sha: str) -> BotReview:
    url = cast("str", comment.get("html_url") or "")
    body = cast("str", comment.get("body") or "")
    encoded = body.partition(CODEX_STATE_MARKER)[2].partition("-->")[0]
    pending = BotReview("pending", "Waiting for readable Codex review state", url)
    try:
        state = json.loads(encoded)
    except ValueError:
        state = None
    if not isinstance(state, dict) or not isinstance(state.get("code_review"), dict):
        return pending
    review = cast("JsonObject", state["code_review"])
    if review.get("commit_sha") != sha:
        return BotReview("missing", "Codex review not started on the current head")
    if review.get("status") == "completed" and isinstance(review.get("has_any_findings"), bool):
        return BotReview("clean", "Codex review clean", url, sha)
    status = review.get("status")
    if isinstance(status, str) and status in {"failed", "cancelled", "error"}:
        return BotReview("blocked", f"Codex review {review['status']}", url, sha)
    return BotReview("pending", "Waiting for Codex Code Review to complete", url, sha)


def assess_codex_quota(
    comment: JsonObject, summary: BotReview | None, comments: list[JsonObject], sha: str
) -> BotReview:
    if comment.get("commit_id") != sha and (summary is None or summary.commit_sha != sha):
        return BotReview("missing", "Codex review not started on the current head")
    request_times = [
        get_activity_time(comment)
        for comment in comments
        if get_author(comment) != CODEX_LOGIN
        and re.search(r"@codex\s+review\b", cast("str", comment.get("body") or ""), re.IGNORECASE)
    ]
    if request_times and max(request_times) > get_activity_time(comment):
        return BotReview("pending", "Waiting for Codex to answer the latest review request")
    return BotReview("unavailable", "Codex quota exhausted", cast("str", comment.get("html_url") or ""))


def find_codex_review(comments: list[JsonObject], reviews: list[JsonObject], sha: str) -> BotReview:
    activity = [
        comment
        for comment in comments
        if get_author(comment) == CODEX_LOGIN
        and (
            CODEX_STATE_MARKER in cast("str", comment.get("body") or "")
            or cast("str", comment.get("body") or "").strip().casefold().startswith(CODEX_QUOTA_PREFIX)
        )
    ]
    activity.extend(
        review for review in reviews if get_author(review) == CODEX_LOGIN and review.get("commit_id") == sha
    )
    if not activity:
        return BotReview("missing", "Codex Code Review not detected")
    summaries = [comment for comment in activity if CODEX_STATE_MARKER in cast("str", comment.get("body") or "")]
    summary = parse_codex_state(max(summaries, key=get_activity_time), sha) if summaries else None
    latest = max(activity, key=get_activity_time)
    body = cast("str", latest.get("body") or "")
    if body.strip().casefold().startswith(CODEX_QUOTA_PREFIX):
        return assess_codex_quota(latest, summary, comments, sha)
    if CODEX_STATE_MARKER in body:
        return parse_codex_state(latest, sha)
    return BotReview("pending", "Waiting for Codex Code Review state")


def count_unresolved_threads(repo: str, pr: str) -> int:
    owner, name = repo.split("/", 1)
    cursor: Json = None
    unresolved = 0
    while True:
        payload = cast(
            "JsonObject",
            _request(
                "POST",
                "graphql",
                {
                    "query": REVIEW_THREADS_QUERY,
                    "variables": {"owner": owner, "name": name, "number": int(pr), "cursor": cursor},
                },
            ),
        )
        if payload.get("errors"):
            raise GraphQlError(payload["errors"])
        data = cast("JsonObject", payload["data"])
        repository = cast("JsonObject", data["repository"])
        pull = cast("JsonObject", repository["pullRequest"])
        connection = cast("JsonObject", pull["reviewThreads"])
        for thread in cast("list[JsonObject]", connection["nodes"]):
            comments = cast("list[JsonObject]", cast("JsonObject", thread["comments"])["nodes"])
            if not thread["isResolved"] and comments and get_author(comments[0]) in {*COPILOT_LOGINS, CODEX_LOGIN}:
                unresolved += 1
        page = cast("JsonObject", connection["pageInfo"])
        if not page["hasNextPage"]:
            return unresolved
        cursor = page["endCursor"]


def build_status(copilot: BotReview, codex: BotReview, unresolved: int) -> tuple[str, str]:
    if unresolved:
        return "failure", f"Bot reviews have {unresolved} unresolved threads"
    for review in (copilot, codex):
        if review.state == "blocked":
            return "failure", review.description
    for review in (copilot, codex):
        if review.state == "pending":
            return "pending", review.description
    if copilot.state == codex.state == "unavailable":
        return "failure", "Both review bots are unavailable; a clean review is required"
    clean = [review.description for review in (copilot, codex) if review.state == "clean"]
    if clean:
        return "success", "; ".join(clean)
    return "pending", "Waiting for a clean Copilot or Codex review"


def post_status(repo: str, sha: str, state: str, description: str, target_url: str = "") -> None:
    payload: JsonObject = {"state": state, "context": STATUS_CONTEXT, "description": description}
    if target_url:
        payload["target_url"] = target_url
    _request("POST", f"repos/{repo}/statuses/{sha}", payload)


def wait_for_ready(repo: str, pr: str, sha: str) -> str:
    read_ok = False
    for _ in range(READY_POLL_ATTEMPTS):
        try:
            pull = fetch_pull(repo, pr)
        except OSError, http.client.HTTPException, GitHubApiError:
            time.sleep(READY_POLL_SECONDS)
            continue
        if get_head_sha(pull) != sha:
            return "stale"
        if pull["draft"] is False:
            return "ready"
        read_ok = True
        time.sleep(READY_POLL_SECONDS)
    return "draft" if read_ok else "unreadable"


def watch_reviews(repo: str, pr: str, sha: str) -> int:
    previous: tuple[str, str] | None = None
    for attempt in range(REVIEW_POLL_ATTEMPTS + 1):
        pull = fetch_pull(repo, pr)
        if get_head_sha(pull) != sha or pull["draft"] or pull.get("state") == "closed":
            logger.info("PR head, readiness or open state changed; stopping this watcher")
            return 0
        reviews = fetch_pages(f"repos/{repo}/pulls/{pr}/reviews")
        comments = fetch_pages(f"repos/{repo}/issues/{pr}/comments")
        query = urllib.parse.urlencode({"check_name": COPILOT_CHECK_NAME})
        runs = fetch_pages(f"repos/{repo}/commits/{sha}/check-runs?{query}", "check_runs")
        copilot = find_copilot_review(reviews, runs, sha)
        codex = find_codex_review(comments, reviews, sha)
        unresolved = count_unresolved_threads(repo, pr)
        verdict = build_status(copilot, codex, unresolved)
        if verdict != previous:
            post_status(repo, sha, *verdict, codex.url or copilot.url)
            previous = verdict
        has_missing_review = "missing" in {copilot.state, codex.state}
        if (verdict[0] == "success" and not has_missing_review) or copilot.state == codex.state == "unavailable":
            return 0
        if attempt < REVIEW_POLL_ATTEMPTS:
            time.sleep(REVIEW_POLL_SECONDS)
    return 0


def main() -> int:
    repo = os.environ["REPO"]
    pr = str(int(os.environ["PR"]))
    sha = os.environ.get("SHA") or get_head_sha(fetch_pull(repo, pr))
    readiness = wait_for_ready(repo, pr, sha)
    if readiness == "unreadable":
        post_status(repo, sha, "error", "Could not read PR draft state to gate bot reviews")
        return 1
    if readiness != "ready":
        logger.info("PR is draft or this head is stale; bot reviews are not gated by this run")
        return 0
    try:
        post_status(repo, sha, "pending", "Waiting for bot reviews to complete")
    except OSError, http.client.HTTPException, GitHubApiError:
        logger.warning("::warning::could not post pending %s status; continuing", STATUS_CONTEXT)
    try:
        return watch_reviews(repo, pr, sha)
    except OSError, http.client.HTTPException, RuntimeError, KeyError, TypeError, ValueError:
        post_status(repo, sha, "error", "Could not read bot review state from GitHub")
        logger.exception("::error::could not evaluate bot reviews")
        return 1


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    sys.exit(main())
