from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_leader, require_member
from ..database import get_db
from ..deps import get_current_user
from ..github_api import GithubError, recent_commits
from ..models import RoadmapStep, Task, TaskCommit, Team, User
from ..schemas import CommitLink, StepCreate, StepUpdate, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(tags=["tasks"])


def task_units(task: Task) -> tuple[int, int]:
    """(완료 단위, 전체 단위).

    완료 판정은 팀장 승인(`done`)이 한다 — 커밋이 붙었다고 저절로 오르지 않는다.
    승인 전에는 로드맵 단계만큼 부분 진행률을 준다.
    """
    if task.done:
        return 1, 1
    if task.steps:
        # 단계를 다 해도 승인 전이면 100%가 아니다. 마지막 한 칸은 팀장 몫
        return sum(1 for s in task.steps if s.done), len(task.steps) + 1
    return 0, 1


def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/teams/{team_id}/tasks", response_model=TaskOut)
def create_task(team_id: int, payload: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_member(db, team_id, user.id)
    task = Task(
        team_id=team_id, title=payload.title, assignee_id=payload.assignee_id,
        deadline=payload.deadline, created_by=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    db.delete(task)
    db.commit()
    return {}


@router.post("/tasks/{task_id}/request-review", response_model=TaskOut)
def request_review(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀원이 '다 했습니다'를 올린다. 진행률은 아직 오르지 않는다."""
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    if task.done:
        raise HTTPException(status_code=400, detail="이미 승인된 할 일입니다.")
    task.review_requested_at = datetime.utcnow()
    task.review_requested_by = user.id
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/approve", response_model=TaskOut)
def approve_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀장이 커밋을 확인하고 완료를 누른다. 이때 진행률이 오른다."""
    task = _get_task_or_404(db, task_id)
    require_leader(db, task.team_id, user.id)
    task.done = True
    task.approved_at = datetime.utcnow()
    task.approved_by = user.id
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/reject", response_model=TaskOut)
def reject_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """팀장이 '아직'이라고 돌려보낸다. 승인 취소에도 쓴다."""
    task = _get_task_or_404(db, task_id)
    require_leader(db, task.team_id, user.id)
    task.done = False
    task.approved_at = task.approved_by = None
    task.review_requested_at = task.review_requested_by = None
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/commits", response_model=TaskOut)
def link_commit(task_id: int, payload: CommitLink, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """`[#번호]`를 깜빡한 커밋을 손으로 붙인다."""
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    if any(c.sha == payload.sha for c in task.commits):
        raise HTTPException(status_code=400, detail="이미 붙어 있는 커밋입니다.")

    team = db.query(Team).get(task.team_id)
    try:
        found = next((c for c in recent_commits(team, limit=100) if c["sha"].startswith(payload.sha)), None)
    except GithubError as e:
        raise HTTPException(status_code=502, detail=e.message)
    if not found:
        raise HTTPException(status_code=404, detail="최근 커밋에서 찾지 못했습니다.")

    task.commits.append(TaskCommit(**found, linked_manually=True))
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}/commits/{commit_id}", response_model=TaskOut)
def unlink_commit(task_id: int, commit_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    commit = next((c for c in task.commits if c.id == commit_id), None)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    task.commits.remove(commit)
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/steps", response_model=TaskOut)
def add_step(task_id: int, payload: StepCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    task.steps.append(RoadmapStep(title=payload.title, done=False))
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}/steps/{step_id}", response_model=TaskOut)
def toggle_step(task_id: int, step_id: int, payload: StepUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    step = next((s for s in task.steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    step.done = payload.done
    # 단계를 전부 끝내면 자동으로 완료 요청까지만 올라간다. 승인은 여전히 팀장 몫
    if all(s.done for s in task.steps) and not task.review_requested_at:
        task.review_requested_at = datetime.utcnow()
        task.review_requested_by = user.id
    db.commit()
    db.refresh(task)
    return task
