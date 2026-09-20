from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Task, Team, User
from app.notifications import notify_due_tomorrow


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return Session()


def test_notify_due_tomorrow_sends_once_per_task():
    db = _session()
    user = User(email="a@test.com", password_hash="x", name="A")
    db.add(user)
    db.commit()
    team = Team(name="T", invite_code="code1")
    db.add(team)
    db.commit()

    tomorrow_noon = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
    task = Task(team_id=team.id, title="발표자료", assignee_id=user.id, deadline=tomorrow_noon, created_by=user.id)
    db.add(task)
    db.commit()

    assert notify_due_tomorrow(db) == 1
    db.refresh(task)
    assert task.notified_at is not None

    # 이미 알림 보낸 task는 다시 세지 않는다
    assert notify_due_tomorrow(db) == 0


def test_notify_due_tomorrow_ignores_other_deadlines():
    db = _session()
    user = User(email="b@test.com", password_hash="x", name="B")
    db.add(user)
    db.commit()
    team = Team(name="T2", invite_code="code2")
    db.add(team)
    db.commit()

    today = Task(team_id=team.id, title="오늘마감", assignee_id=user.id, deadline=datetime.utcnow(), created_by=user.id)
    next_week = Task(
        team_id=team.id, title="다음주마감", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=7), created_by=user.id,
    )
    done_tomorrow = Task(
        team_id=team.id, title="완료됨", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=1), done=True, created_by=user.id,
    )
    db.add_all([today, next_week, done_tomorrow])
    db.commit()

    assert notify_due_tomorrow(db) == 0
