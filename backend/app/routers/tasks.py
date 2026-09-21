import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..access import require_member
from ..database import get_db
from ..deps import get_current_user
from ..github_api import TERMINAL_STATES, GithubError, apply_auto_complete, gh_get, issue_kind_and_state
from ..models import RoadmapStep, Task, TaskLink, Team, User
from ..schemas import LinkCreate, StepCreate, StepUpdate, TaskCreate, TaskOut, TaskUpdate

router = APIRouter(tags=["tasks"])


def task_units(task: Task) -> tuple[int, int]:
    """(완료 단위, 전체 단위).

    우선순위: 사람이 직접 되돌린 판단 > 깃허브 이슈/PR > 로드맵 단계 > done 플래그.
    깃허브가 진행률을 만들되, 사람의 최종 판단을 이기지는 않는다.
    """
    if task.done_override:
        return (1 if task.done else 0), 1
    if task.links:
        return sum(1 for link in task.links if link.state in TERMINAL_STATES), len(task.links)
    if task.steps:
        return sum(1 for s in task.steps if s.done), len(task.steps)
    return (1 if task.done else 0), 1


def parse_ref(ref: str) -> int:
    """"123", "#123", ".../issues/123", ".../pull/123" 어느 쪽이든 번호로."""
    m = re.search(r"(?:issues|pull)/(\d+)", ref) or re.fullmatch(r"#?(\d+)", ref.strip())
    if not m:
        raise HTTPException(status_code=400, detail="이슈/PR 번호 또는 주소를 입력하세요. 예: 123 또는 https://github.com/owner/name/pull/123")
    return int(m.group(1))


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
    if "done" in data and task.links:
        # 이슈/PR이 붙은 할 일을 손으로 바꿨다 = 사람이 동기화 결과를 뒤집은 것
        task.done_override = True
        task.auto_completed_at = None
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


@router.post("/tasks/{task_id}/links", response_model=TaskOut)
def add_link(task_id: int, payload: LinkCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """할 일에 깃허브 이슈/PR을 연결한다. 연결 즉시 현재 상태를 가져온다."""
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)

    team = db.query(Team).get(task.team_id)
    if not team.github_repo:
        raise HTTPException(status_code=400, detail="팀에 깃허브 레포를 먼저 연결하세요.")

    number = parse_ref(payload.ref)
    if any(link.number == number for link in task.links):
        raise HTTPException(status_code=400, detail=f"#{number}은(는) 이미 연결돼 있습니다.")

    try:
        item, _ = gh_get(f"/repos/{team.github_repo}/issues/{number}")
    except GithubError as e:
        raise HTTPException(status_code=e.status if e.status == 404 else 502, detail=e.message)

    kind, state = issue_kind_and_state(item)
    task.links.append(TaskLink(
        kind=kind, number=number, title=item["title"], state=state,
        url=item["html_url"], last_synced_at=datetime.utcnow(),
    ))
    task.done_override = False  # 새로 연결했으면 깃허브 기준으로 다시 판단한다
    db.flush()
    apply_auto_complete(task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}/links/{link_id}", response_model=TaskOut)
def remove_link(task_id: int, link_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    require_member(db, task.team_id, user.id)
    link = next((l for l in task.links if l.id == link_id), None)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    task.links.remove(link)
    db.flush()
    apply_auto_complete(task)
    db.commit()
    db.refresh(task)
    return task
