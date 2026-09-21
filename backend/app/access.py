from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Role, Team, TeamMember


def require_member(db: Session, team_id: int, user_id: int) -> TeamMember:
    """team_id 팀이 존재하고 user_id가 그 팀원인지 확인. 아니면 404/403."""
    if not db.query(Team).get(team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    member = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a team member")
    return member


def require_leader(db: Session, team_id: int, user_id: int) -> TeamMember:
    """팀장만 할 수 있는 일(오가니제이션 등록, 완료 승인) 앞에 세운다."""
    member = require_member(db, team_id, user_id)
    if member.role != Role.leader:
        raise HTTPException(status_code=403, detail="팀장만 할 수 있습니다.")
    return member
