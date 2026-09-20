import json
import os
import re
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_member
from ..database import get_db
from ..deps import get_current_user
from ..models import Team, User
from ..schemas import GithubConnect

router = APIRouter(tags=["github"])

REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # 비공개 레포·rate limit 완화용(선택)


def _gh_get(path: str):
    """GitHub REST API GET. stdlib urllib만 사용(동기 def 엔드포인트라 스레드풀에서 실행됨)."""
    headers = {"User-Agent": "deadline-dashboard", "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTPException(status_code=404, detail="레포를 찾을 수 없습니다. owner/name 형식과 공개 여부를 확인하세요.")
        if e.code in (401, 403):
            raise HTTPException(status_code=502, detail="GitHub 접근이 거부되었습니다(비공개 레포거나 요청 한도 초과). GITHUB_TOKEN 설정이 필요할 수 있어요.")
        raise HTTPException(status_code=502, detail=f"GitHub 오류 ({e.code})")
    except urllib.error.URLError:
        raise HTTPException(status_code=502, detail="GitHub에 연결할 수 없습니다(네트워크 확인).")


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
