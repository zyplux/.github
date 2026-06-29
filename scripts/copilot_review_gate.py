from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_ROOT = "https://api.github.com"
STATUS_CONTEXT = "copilot-review-complete"
COPILOT_CHECK_NAME = "copilot-pull-request-reviewer"

READY_POLL_ATTEMPTS = 40
READY_POLL_SECONDS = 5
APPEAR_POLL_ATTEMPTS = 12
APPEAR_POLL_SECONDS = 15
COMPLETE_POLL_ATTEMPTS = 60
COMPLETE_POLL_SECONDS = 15


def _request(method: str, path: str, payload: dict | None = None) -> object:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(f"{API_ROOT}/{path}", data=data, method=method)
    request.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(request) as response:
        body = response.read()
    return json.loads(body) if body else None


def read_is_draft(repo: str, pr: str) -> bool:
    pull = _request("GET", f"repos/{repo}/pulls/{pr}")
    return bool(pull["draft"])


def find_copilot_run(check_runs: list[dict]) -> dict | None:
    return next(
        (run for run in check_runs if run.get("name") == COPILOT_CHECK_NAME), None
    )


def fetch_copilot_run(repo: str, sha: str) -> dict | None:
    query = urllib.parse.urlencode({"check_name": COPILOT_CHECK_NAME, "per_page": 100})
    result = _request("GET", f"repos/{repo}/commits/{sha}/check-runs?{query}") or {}
    return find_copilot_run(result.get("check_runs", []))


def build_status(conclusion: str) -> tuple[str, str]:
    if conclusion == "success":
        return "success", "Copilot review success"
    return "failure", f"Copilot review concluded: {conclusion}"


def post_status(
    repo: str, sha: str, state: str, description: str, target_url: str = ""
) -> None:
    payload = {"state": state, "context": STATUS_CONTEXT, "description": description}
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


def await_copilot_run(repo: str, sha: str) -> tuple[str, dict | None]:
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
        try:
            run = fetch_copilot_run(repo, sha)
        except urllib.error.URLError:
            pass
    return ("incomplete", run)


def main() -> int:
    repo = os.environ["REPO"]
    pr = os.environ["PR"]
    sha = os.environ["SHA"]

    readiness = wait_for_ready(repo, pr)
    if readiness == "unreadable":
        post_status(
            repo,
            sha,
            "error",
            "Could not read PR draft state to gate the Copilot review",
        )
        return 1
    if readiness == "draft":
        print(
            "PR is still draft after waiting; Copilot review is not expected, leaving no status"
        )
        return 0

    try:
        post_status(repo, sha, "pending", "Waiting for Copilot review to complete")
    except urllib.error.URLError as error:
        print(
            f"::warning::could not post pending {STATUS_CONTEXT} status (continuing): {error}"
        )

    outcome, run = await_copilot_run(repo, sha)
    if outcome == "completed":
        state, description = build_status(run.get("conclusion") or "")
        post_status(repo, sha, state, description, run.get("details_url") or "")
        return 0
    if outcome == "not_requested":
        post_status(
            repo,
            sha,
            "failure",
            "Copilot review was not requested for this push — re-run `just pr` to re-trigger it",
        )
        return 0
    if outcome == "incomplete":
        post_status(
            repo,
            sha,
            "error",
            "Copilot review started but did not complete in time",
        )
        return 0
    post_status(
        repo,
        sha,
        "error",
        "Could not query the Copilot review check-run",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
