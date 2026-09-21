"""GitHub REST 호출과 이슈/PR 동기화.

라우터(app/routers/github.py)와 스케줄러(app/main.py)가 함께 쓴다.
ponytail: 웹훅 대신 폴링. 공개 URL이 필요 없어서 어디에 올려도 그대로 돈다.
실시간이 필요해지면 POST /webhooks/github가 sync_repo()를 그대로 부르면 된다.
"""
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from .models import Task, TaskLink, Team

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # 비공개 레포·rate limit 완화용(선택)
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
TERMINAL_STATES = ("closed", "merged")


class GithubError(Exception):
    """GitHub 호출 실패. 라우터는 HTTPException으로, 스케줄러는 팀별 에러 메시지로 바꿔 쓴다."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def gh_get(path: str, etag: str | None = None):
    """GitHub REST GET. (데이터, ETag)를 반환. 내용이 안 바뀌었으면 (None, 기존 ETag)."""
    headers = {"User-Agent": "deadline-dashboard", "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            return json.load(res), res.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:  # 조건부 요청 — 바뀐 게 없다
            return None, etag
        if e.code == 404:
            raise GithubError("레포를 찾을 수 없습니다. owner/name 형식과 공개 여부를 확인하세요.", 404)
        if e.code in (401, 403, 429):
            raise GithubError("GitHub 접근이 거부되었습니다(비공개 레포거나 요청 한도 초과). GITHUB_TOKEN 설정이 필요할 수 있어요.")
        raise GithubError(f"GitHub 오류 ({e.code})")
    except urllib.error.URLError:
        raise GithubError("GitHub에 연결할 수 없습니다(네트워크 확인).")


def issue_kind_and_state(item: dict) -> tuple[str, str]:
    """issues API 항목 하나를 (kind, state)로. PR이면 pull_request 키가 있고 merged_at이 채워진다."""
    pr = item.get("pull_request")
    if pr is None:
        return "issue", item["state"]
    return "pr", "merged" if pr.get("merged_at") else item["state"]


def apply_auto_complete(task: Task) -> None:
    """연결된 이슈/PR이 전부 종료되면 할 일을 완료 처리. 사람이 직접 되돌린 할 일은 건드리지 않는다."""
    if task.done_override or not task.links:
        return
    all_terminal = all(link.state in TERMINAL_STATES for link in task.links)
    if all_terminal and not task.done:
        task.done = True
        task.auto_completed_at = datetime.utcnow()
    elif not all_terminal and task.auto_completed_at:
        # 이슈가 다시 열렸다 — 자동으로 켠 완료는 자동으로 끈다
        task.done = False
        task.auto_completed_at = None


def sync_repo(db: Session, team: Team) -> dict:
    """팀 레포의 이슈/PR 상태를 TaskLink에 반영하고 할 일 자동 완료를 갱신한다.

    커밋하지 않는다 — 호출한 쪽이 커밋한다.
    """
    result = {"team_id": team.id, "updated": 0, "skipped": False}
    if not team.github_repo:
        return result

    links = db.query(TaskLink).join(Task).filter(Task.team_id == team.id).all()
    if not links:
        team.github_last_sync_at = datetime.utcnow()
        team.github_last_error = None
        return result

    path = f"/repos/{team.github_repo}/issues?state=all&sort=updated&direction=desc&per_page=100"
    items, etag = gh_get(path, etag=team.github_etag)
    team.github_etag = etag
    team.github_last_sync_at = datetime.utcnow()
    team.github_last_error = None

    if items is None:  # 304 — 마지막 동기화 이후 바뀐 게 없다
        result["skipped"] = True
        return result

    by_number = {item["number"]: item for item in items}
    touched_tasks = {}
    for link in links:
        item = by_number.get(link.number)
        if not item:
            continue  # 최근 목록에 없다 = 그 사이 바뀐 게 없다
        kind, state = issue_kind_and_state(item)
        if (link.kind, link.state, link.title) != (kind, state, item["title"]):
            result["updated"] += 1
        link.kind, link.state = kind, state
        link.title = item["title"]
        link.url = item["html_url"]
        link.last_synced_at = datetime.utcnow()
        touched_tasks[link.task_id] = link.task

    for task in touched_tasks.values():
        apply_auto_complete(task)

    return result


def run_sync_job() -> None:
    """스케줄러 진입점. 팀 단위로 예외를 격리해 한 레포의 문제가 다른 팀을 막지 않게 한다."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        for team in db.query(Team).filter(Team.github_repo.isnot(None)):
            try:
                sync_repo(db, team)
            except GithubError as e:
                team.github_last_sync_at = datetime.utcnow()
                team.github_last_error = e.message
                logger.warning("github sync 실패 team=%s repo=%s: %s", team.id, team.github_repo, e.message)
            except Exception:
                logger.exception("github sync 예외 team=%s", team.id)
        db.commit()
    finally:
        db.close()
