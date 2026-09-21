from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_member
from ..database import get_db
from ..deps import get_current_user
from ..github_api import REPO_RE, GithubError, gh_get, sync_repo
from ..models import Team, User
from ..schemas import GithubConnect

router = APIRouter(tags=["github"])


def _gh_get(path: str):
    """GithubError를 HTTP 응답으로 바꿔주는 얇은 래퍼."""
    try:
        data, _etag = gh_get(path)
        return data
    except GithubError as e:
        raise HTTPException(status_code=e.status if e.status == 404 else 502, detail=e.message)


def _team(db: Session, team_id: int, user_id: int) -> Team:
    require_member(db, team_id, user_id)
    return db.query(Team).get(team_id)


@router.put("/teams/{team_id}/github")
def connect_repo(team_id: int, payload: GithubConnect, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id, user.id)
    repo = payload.repo.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
    if not REPO_RE.match(repo):
        raise HTTPException(status_code=400, detail="owner/name 형식으로 입력하세요. 예: facebook/react")
    _gh_get(f"/repos/{repo}")  # 존재·접근 가능 여부 검증(없으면 404)
    team.github_repo = repo
    db.commit()
    return {"repo": repo}


@router.delete("/teams/{team_id}/github")
def disconnect_repo(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id, user.id)
    team.github_repo = None
    team.github_etag = team.github_last_error = team.github_last_sync_at = None
    db.commit()
    return {}


@router.get("/teams/{team_id}/github")
def get_activity(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = _team(db, team_id, user.id)
    if not team.github_repo:
        return {"repo": None, "commits": [], "pulls": []}

    commits = _gh_get(f"/repos/{team.github_repo}/commits?per_page=8")
    pulls = _gh_get(f"/repos/{team.github_repo}/pulls?state=all&sort=updated&direction=desc&per_page=8")

    return {
        "repo": team.github_repo,
        "commits": [
            {
                "sha": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0],
                "author": (c.get("author") or {}).get("login") or c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
                "url": c["html_url"],
            }
            for c in commits
        ],
        "pulls": [
            {
                "number": p["number"],
                "title": p["title"],
                "state": "merged" if p.get("merged_at") else p["state"],
                "author": (p.get("user") or {}).get("login"),
                "url": p["html_url"],
            }
            for p in pulls
        ],
    }


@router.post("/teams/{team_id}/github/sync")
def sync_now(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """5분 주기를 기다리지 않고 지금 동기화한다."""
    team = _team(db, team_id, user.id)
    if not team.github_repo:
        raise HTTPException(status_code=400, detail="연결된 레포가 없습니다.")
    try:
        result = sync_repo(db, team)
    except GithubError as e:
        team.github_last_sync_at = datetime.utcnow()
        team.github_last_error = e.message
        db.commit()
        raise HTTPException(status_code=e.status if e.status == 404 else 502, detail=e.message)
    db.commit()
    return result
