from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_member
from ..database import get_db
from ..deps import get_current_user
from ..models import RoadmapStep, Task, User
from ..schemas import StepCreate, StepUpdate, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(tags=["tasks"])


def task_units(task: Task) -> tuple[int, int]:
    """(완료 단위, 전체 단위). 로드맵 단계가 있으면 단계 기준, 없으면 done 자체가 1단위."""
    if task.steps:
        return sum(1 for s in task.steps if s.done), len(task.steps)
    return (1 if task.done else 0), 1


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

    data = payload.model_dump(exclude_unset=True)
    if "done" in data and task.steps:
        raise HTTPException(status_code=400, detail="Cannot toggle done directly when roadmap steps exist")
    for field, value in data.items():
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


@router.post("/tasks/{task_id}/steps", response_model=TaskOut)
def add_step(task_id: int, payload: StepCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    task.steps.append(RoadmapStep(title=payload.title, done=False))
    task.done = False  # 새 단계가 생기면 아직 전부 완료된 상태가 아님
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
    task.done = bool(task.steps) and all(s.done for s in task.steps)
    db.commit()
    db.refresh(task)
    return task
