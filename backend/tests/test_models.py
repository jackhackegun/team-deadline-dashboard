from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Team, TeamMember, Task, RoadmapStep, Role


def test_create_user_team_task_round_trip():
    """Test User, Team, TeamMember model creation"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create and save user
    user = User(email="a@test.com", password_hash="hash", name="A")
    db.add(user)
    db.commit()

    # Create and save team
    team = Team(name="팀", invite_code="ABC123")
    db.add(team)
    db.commit()

    # Create and save team member
    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.leader))
    db.commit()

    # Create and save task
    db.add(
        Task(
            team_id=team.id,
            title="작업1",
            assignee_id=user.id,
            deadline=datetime.utcnow() + timedelta(days=1),
            created_by=user.id,
        )
    )
    db.commit()

    # Verify task count and done field
    assert db.query(Task).count() == 1
    assert db.query(Task).first().done == False


def test_roadmap_step_belongs_to_task():
    """Test Task with RoadmapStep relationship"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create user
    user = User(email="b@test.com", password_hash="x", name="B")
    db.add(user)
    db.commit()

    # Create team
    team = Team(name="팀", invite_code="XYZ999")
    db.add(team)
    db.commit()

    # Create task
    task = Task(
        team_id=team.id,
        title="발표자료",
        assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=1),
        created_by=user.id,
    )
    db.add(task)
    db.commit()

    # Add roadmap step
    db.add(RoadmapStep(task_id=task.id, title="자료조사"))
    db.commit()

    # Verify step relationship
    saved_task = db.query(Task).get(task.id)
    assert len(saved_task.steps) == 1
    assert saved_task.steps[0].done == False
