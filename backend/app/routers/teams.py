import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_member
from ..database import get_db
from ..deps import get_current_user
from ..models import Role, Task, Team, TeamMember, User
from ..schemas import DashboardOut, MemberProgress, TeamCreate, TeamJoin, TeamOut
from .tasks import task_units

router = APIRouter(tags=["teams"])


def _team_out(team: Team, role: Role) -> TeamOut:
    return TeamOut(id=team.id, name=team.name, invite_code=team.invite_code, role=role.value)


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
    return [_team_out(team, role) for team, role in rows]


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


@router.delete("/teams/{team_id}/leave")
def leave_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = require_member(db, team_id, user.id)
    db.delete(member)
    db.commit()
    return {}


@router.delete("/teams/{team_id}")
def delete_team(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = require_member(db, team_id, user.id)
    if member.role != Role.leader:
        raise HTTPException(status_code=403, detail="Only the leader can delete the team")
    team = db.query(Team).get(team_id)
    for task in db.query(Task).filter(Task.team_id == team_id).all():
        db.delete(task)  # RoadmapStep은 relationship cascade로 함께 삭제됨
    db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()
    db.delete(team)
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
            )
        )
        team_done += m_done
        team_total += m_total

    return DashboardOut(
        team_id=team.id, team_name=team.name, progress_pct=_pct(team_done, team_total),
        members=members_out, tasks=tasks,
    )
