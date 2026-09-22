import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_leader, require_member
from ..database import get_db
from ..deps import get_current_user
from ..models import Role, Task, Team, TeamMember, User
from ..schemas import DashboardOut, LeaderTransfer, MemberProgress, TeamCreate, TeamJoin, TeamOut
from .tasks import task_units

router = APIRouter(tags=["teams"])


def _team_out(team: Team, role: Role, db: Session | None = None) -> TeamOut:
    out = TeamOut(id=team.id, name=team.name, invite_code=team.invite_code, role=role.value)
    if db is None:  # 갓 만든 팀 — 집계할 것이 없다
        return out

    out.member_count = db.query(TeamMember).filter(TeamMember.team_id == team.id).count()
    tasks = db.query(Task).filter(Task.team_id == team.id).all()
    out.task_count = len(tasks)

    now = datetime.utcnow()
    done = total = 0
    for task in tasks:
        d, u = task_units(task)
        done += d
        total += u
        if not task.done and task.deadline < now:
            out.overdue_count += 1
        if task.review_requested_at and not task.done:
            out.pending_review_count += 1
    out.progress_pct = _pct(done, total)
    return out


def _pct(done: int, total: int) -> int:
    return round(done / total * 100) if total else 0


@router.get("/teams", response_model=list[TeamOut])
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Team, TeamMember.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .filter(TeamMember.user_id == user.id)
        .all()
    )
    return [_team_out(team, role, db) for team, role in rows]


@router.post("/teams", response_model=TeamOut)
def create_team(payload: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = Team(name=payload.name, invite_code=secrets.token_hex(4))
    db.add(team)
    db.flush()
    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.leader))
    db.commit()
    db.refresh(team)
    return _team_out(team, Role.leader)


# 명세서는 POST /teams/{team_id}/join 이지만, 초대코드만 아는 클라이언트는 team_id를
# 미리 알 수 없어 코드만으로 조회한다.
@router.post("/teams/join", response_model=TeamOut)
def join_team(payload: TeamJoin, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.invite_code == payload.invite_code).first()
    if not team:
        raise HTTPException(status_code=404, detail="Invalid team or invite code")
    already = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="Already member")
    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.member))
    db.commit()
    return _team_out(team, Role.member)


def _purge_team(db: Session, team_id: int) -> None:
    """팀과 딸린 것들을 전부 지운다. 할 일의 단계·커밋은 relationship cascade로 함께 사라진다."""
    for task in db.query(Task).filter(Task.team_id == team_id).all():
        db.delete(task)
    db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()
    db.delete(db.query(Team).get(team_id))


@router.post("/teams/{team_id}/transfer-leader", response_model=TeamOut)
def transfer_leader(team_id: int, payload: LeaderTransfer,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀장 자리를 다른 팀원에게 넘긴다. 넘긴 사람은 일반 팀원이 된다."""
    me = require_leader(db, team_id, user.id)
    if payload.user_id == user.id:
        raise HTTPException(status_code=400, detail="이미 팀장입니다.")

    target = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == payload.user_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="그 팀의 팀원이 아닙니다.")

    target.role = Role.leader
    me.role = Role.member
    db.commit()
    team = db.query(Team).get(team_id)
    return _team_out(team, Role.member, db)


@router.delete("/teams/{team_id}/leave")
def leave_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀에서 나간다.

    팀장이 그냥 나가면 팀에 팀장이 없어져 승인도, 팀 삭제도, 깃허브 설정도
    아무도 할 수 없는 상태가 된다. 그래서 팀장은 위임하거나 팀을 정리해야 한다.
    """
    member = require_member(db, team_id, user.id)
    others = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id != user.id)
        .count()
    )

    if others == 0:
        # 마지막 한 명 — 빈 팀을 남기면 아무도 지울 수 없는 팀이 된다
        _purge_team(db, team_id)
        db.commit()
        return {"team_deleted": True}

    if member.role == Role.leader:
        raise HTTPException(
            status_code=400,
            detail="팀장은 바로 나갈 수 없습니다. 먼저 다른 팀원에게 팀장을 위임하거나 팀을 삭제하세요.",
        )

    db.delete(member)
    db.commit()
    return {"team_deleted": False}


@router.delete("/teams/{team_id}")
def delete_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = require_member(db, team_id, user.id)
    if member.role != Role.leader:
        raise HTTPException(status_code=403, detail="Only the leader can delete the team")
    _purge_team(db, team_id)
    db.commit()
    return {}


@router.get("/teams/{team_id}/dashboard", response_model=DashboardOut)
def get_dashboard(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_member(db, team_id, user.id)
    team = db.query(Team).get(team_id)
    tasks = db.query(Task).filter(Task.team_id == team_id).all()
    now = datetime.utcnow()

    team_done = team_total = 0
    members_out = []
    for tm, member in db.query(TeamMember, User).join(User, User.id == TeamMember.user_id).filter(
        TeamMember.team_id == team_id
    ):
        my_tasks = [t for t in tasks if t.assignee_id == tm.user_id]
        m_done = m_total = 0
        overdue = 0
        for t in my_tasks:
            d, u = task_units(t)
            m_done += d
            m_total += u
            if not t.done and t.deadline < now:
                overdue += 1
        members_out.append(
            MemberProgress(
                user_id=tm.user_id, name=member.name, role=tm.role.value,
                progress_pct=_pct(m_done, m_total), overdue_count=overdue,
                github_login=member.github_login,
            )
        )
        team_done += m_done
        team_total += m_total

    my_member = next((m for m in members_out if m.user_id == user.id), None)
    return DashboardOut(
        team_id=team.id, team_name=team.name, progress_pct=_pct(team_done, team_total),
        members=members_out, tasks=tasks,
        invite_code=team.invite_code,
        github_org=team.github_org,
        repos=team.repos,
        my_role=my_member.role if my_member else "member",
        # 팀장 화면에 '승인 기다리는 일 N건'을 띄우기 위한 값
        pending_review_count=sum(1 for t in tasks if t.review_requested_at and not t.done),
    )
