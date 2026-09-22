from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_leader, require_member
from ..database import get_db
from ..deps import get_current_user
from ..github_api import (
    ORG_RE, REPO_RE, GithubError, gh_get, invalidate_commit_cache,
    list_org_repos, recent_commits, sync_team,
)
from ..models import Team, TeamRepo, User
from ..schemas import GithubOrgConnect, RepoSelection

router = APIRouter(tags=["github"])


def _team(db: Session, team_id: int, user_id: int) -> Team:
    require_member(db, team_id, user_id)
    return db.query(Team).get(team_id)


def _http(e: GithubError) -> HTTPException:
    # 404(없음)와 429(한도 초과)는 그대로 내보낸다 — 502로 뭉뚱그리면 원인을 알 수 없다
    passthrough = e.status in (404, 429)
    return HTTPException(status_code=e.status if passthrough else 502, detail=e.message)


@router.put("/teams/{team_id}/github/org")
def connect_org(team_id: int, payload: GithubOrgConnect, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀장이 오가니제이션을 등록한다."""
    require_leader(db, team_id, user.id)
    team = db.query(Team).get(team_id)

    org = payload.org.strip().removeprefix("https://github.com/").strip("/")
    if not ORG_RE.match(org):
        raise HTTPException(status_code=400, detail="오가니제이션 이름만 넣으세요. 예: vercel")
    try:
        gh_get(f"/orgs/{org}")  # 존재·접근 가능 여부 확인
    except GithubError as e:
        raise _http(e)

    if team.github_org and team.github_org != org:
        team.repos.clear()  # org가 바뀌면 이전 org의 레포 선택은 의미가 없다
    team.github_org = org
    db.commit()
    return {"org": org}


@router.delete("/teams/{team_id}/github/org")
def disconnect_org(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_leader(db, team_id, user.id)
    team = db.query(Team).get(team_id)
    team.github_org = None
    team.repos.clear()
    db.commit()
    return {}


@router.get("/teams/{team_id}/github/org/repos")
def browse_org_repos(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """등록한 org의 레포 목록과 현재 선택 상태."""
    team = _team(db, team_id, user.id)
    if not team.github_org:
        raise HTTPException(status_code=400, detail="먼저 오가니제이션을 등록하세요.")
    try:
        available = list_org_repos(team.github_org)
    except GithubError as e:
        raise _http(e)
    selected = {r.full_name for r in team.repos}
    return {
        "org": team.github_org,
        "repos": [{**r, "selected": r["full_name"] in selected} for r in available],
    }


@router.put("/teams/{team_id}/github/repos")
def select_repos(team_id: int, payload: RepoSelection, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """이 팀이 실제로 쓸 레포를 고른다. 고른 것만 커밋을 훑는다."""
    require_leader(db, team_id, user.id)
    team = db.query(Team).get(team_id)
    if not team.github_org:
        raise HTTPException(status_code=400, detail="먼저 오가니제이션을 등록하세요.")

    wanted = {r.strip() for r in payload.repos if r.strip()}
    for full_name in wanted:
        if not REPO_RE.match(full_name) or not full_name.startswith(f"{team.github_org}/"):
            raise HTTPException(status_code=400, detail=f"{full_name}은(는) {team.github_org} 소속 레포가 아닙니다.")

    current = {r.full_name: r for r in team.repos}
    for full_name in current.keys() - wanted:
        team.repos.remove(current[full_name])
    for full_name in wanted - current.keys():
        team.repos.append(TeamRepo(full_name=full_name))
    db.commit()
    invalidate_commit_cache(team_id)
    return {"repos": sorted(wanted)}


@router.get("/teams/{team_id}/github/commits")
def list_recent_commits(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """최근 커밋 목록. `[#번호]`를 깜빡한 커밋을 할 일에 손으로 붙일 때 쓴다."""
    team = _team(db, team_id, user.id)
    return {"commits": recent_commits(team)}


@router.post("/teams/{team_id}/github/sync")
def sync_now(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """5분 주기를 기다리지 않고 지금 커밋을 가져온다."""
    team = _team(db, team_id, user.id)
    if not team.repos:
        raise HTTPException(status_code=400, detail="먼저 볼 레포를 고르세요.")
    result = sync_team(db, team)
    db.commit()
    return result
