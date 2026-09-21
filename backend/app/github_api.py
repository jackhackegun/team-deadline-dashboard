"""GitHub REST 호출과 커밋 수집.

팀원이 `[#12] 로그인 API 구현`처럼 커밋하면 12번 할 일에 그 커밋이 붙는다.
규칙을 깜빡한 커밋은 화면에서 직접 골라 붙일 수 있다(수동 연결).

ponytail: 웹훅 대신 폴링. 공개 URL이 필요 없어서 어디에 올려도 그대로 돈다.
실시간이 필요해지면 POST /webhooks/github가 sync_repo()를 그대로 부르면 된다.
"""
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import Task, TaskCommit, Team, TeamRepo

logger = logging.getLogger(__name__)

from .config import GITHUB_TOKEN  # 비공개 org 레포 접근·요청 한도 완화용
ORG_RE = re.compile(r"^[\w.-]+$")
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")

# 커밋 메시지에서 할 일 번호를 찾는 규칙. 대괄호를 요구하는 이유:
# 맨 #12는 깃허브가 이슈/PR을 가리키는 표기라 "Merge pull request #6" 같은 커밋이 6번 할 일로 잘못 붙는다
TASK_REF_RE = re.compile(r"\[#(\d+)\]")

COMMIT_LOOKBACK_DAYS = int(os.getenv("GITHUB_COMMIT_LOOKBACK_DAYS", "30"))


class GithubError(Exception):
    """GitHub 호출 실패. 라우터는 HTTP 응답으로, 스케줄러는 레포별 에러 메시지로 바꿔 쓴다."""

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
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.load(res), res.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:  # 조건부 요청 — 바뀐 게 없다
            return None, etag
        if e.code == 404:
            raise GithubError("찾을 수 없습니다. 이름과 공개 여부를 확인하세요.", 404)
        if e.code in (401, 403, 429):
            raise GithubError("GitHub 접근이 거부되었습니다(비공개거나 요청 한도 초과). GITHUB_TOKEN 설정이 필요할 수 있어요.")
        raise GithubError(f"GitHub 오류 ({e.code})")
    except urllib.error.URLError:
        raise GithubError("GitHub에 연결할 수 없습니다(네트워크 확인).")


def list_org_repos(org: str) -> list[dict]:
    """org의 레포 목록. 팀장이 이 중에서 쓸 것만 고른다."""
    items, _ = gh_get(f"/orgs/{org}/repos?per_page=100&sort=updated")
    return [
        {"full_name": r["full_name"], "private": r["private"],
         "description": r.get("description"), "pushed_at": r.get("pushed_at")}
        for r in (items or [])
    ]


def parse_commit(item: dict, repo: str) -> dict:
    """깃허브 커밋 응답에서 필요한 것만 추린다."""
    commit = item["commit"]
    return {
        "sha": item["sha"],
        "repo": repo,
        "message": commit["message"].split("\n")[0][:300],
        "author_login": (item.get("author") or {}).get("login"),
        "author_name": commit["author"]["name"],
        "url": item["html_url"],
        "committed_at": datetime.strptime(commit["author"]["date"], "%Y-%m-%dT%H:%M:%SZ"),
    }


def sync_repo(db: Session, repo: TeamRepo) -> dict:
    """레포의 최근 커밋을 가져와 `[#번호]` 규칙에 맞는 할 일에 붙인다.

    커밋하지 않는다 — 호출한 쪽이 커밋한다.
    """
    since = (datetime.utcnow() - timedelta(days=COMMIT_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = f"/repos/{repo.full_name}/commits?per_page=100&since={since}"
    items, etag = gh_get(path, etag=repo.etag)
    repo.etag = etag
    repo.last_sync_at = datetime.utcnow()
    repo.last_error = None

    if items is None:  # 304 — 마지막 동기화 이후 새 커밋이 없다
        return {"repo": repo.full_name, "linked": 0, "skipped": True}

    # 이 팀의 할 일만 대상 — 다른 팀 번호가 적힌 커밋이 넘어오면 안 된다
    task_ids = {t.id for t in db.query(Task.id).filter(Task.team_id == repo.team_id)}
    existing = {
        (c.task_id, c.sha)
        for c in db.query(TaskCommit.task_id, TaskCommit.sha)
        .join(Task).filter(Task.team_id == repo.team_id)
    }

    linked = 0
    for item in items:
        data = parse_commit(item, repo.full_name)
        for ref in set(TASK_REF_RE.findall(data["message"])):
            task_id = int(ref)
            if task_id not in task_ids or (task_id, data["sha"]) in existing:
                continue
            db.add(TaskCommit(task_id=task_id, **data))
            existing.add((task_id, data["sha"]))
            linked += 1

    return {"repo": repo.full_name, "linked": linked, "skipped": False}


def sync_team(db: Session, team: Team) -> dict:
    """팀이 고른 레포를 모두 훑는다. 레포 단위로 예외를 격리한다."""
    results = []
    for repo in team.repos:
        try:
            results.append(sync_repo(db, repo))
        except GithubError as e:
            repo.last_sync_at = datetime.utcnow()
            repo.last_error = e.message
            results.append({"repo": repo.full_name, "error": e.message})
            logger.warning("커밋 동기화 실패 repo=%s: %s", repo.full_name, e.message)
    return {"team_id": team.id, "repos": results}


def recent_commits(team: Team, limit: int = 30) -> list[dict]:
    """팀 레포의 최근 커밋. 규칙을 깜빡한 커밋을 손으로 붙일 때 고르는 목록."""
    out = []
    for repo in team.repos:
        try:
            items, _ = gh_get(f"/repos/{repo.full_name}/commits?per_page={limit}")
        except GithubError:
            continue  # 한 레포가 죽어도 나머지는 보여준다
        out.extend(parse_commit(i, repo.full_name) for i in (items or []))
    out.sort(key=lambda c: c["committed_at"], reverse=True)
    return out[:limit]


def run_sync_job() -> None:
    """스케줄러 진입점. 팀 단위로 예외를 격리한다."""
    from .database import SessionLocal

    db = SessionLocal()
    try:
        for team in db.query(Team).filter(Team.github_org.isnot(None)):
            try:
                sync_team(db, team)
            except Exception:
                logger.exception("커밋 동기화 예외 team=%s", team.id)
        db.commit()
    finally:
        db.close()
