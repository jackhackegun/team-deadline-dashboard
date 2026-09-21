import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base


class Role(str, enum.Enum):
    leader = "leader"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    invite_code = Column(String, unique=True, nullable=False)
    github_repo = Column(String, nullable=True)  # "owner/name" 형식, 미연결 시 None
    github_etag = Column(String, nullable=True)  # 조건부 요청용 — 안 바뀌었으면 304로 넘긴다
    github_last_sync_at = Column(DateTime, nullable=True)
    github_last_error = Column(String, nullable=True)  # 성공하면 None으로 지운다


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    role = Column(Enum(Role), default=Role.member, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    title = Column(String, nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deadline = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    done = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)
    auto_completed_at = Column(DateTime, nullable=True)  # 이슈/PR 종료로 자동 완료된 시각
    # 사람이 자동 완료를 직접 되돌렸다는 표시. 켜지면 동기화가 done을 건드리지 않는다
    done_override = Column(Boolean, default=False, nullable=False)

    steps = relationship("RoadmapStep", back_populates="task", cascade="all, delete-orphan")
    links = relationship("TaskLink", back_populates="task", cascade="all, delete-orphan")


class RoadmapStep(Base):
    __tablename__ = "roadmap_steps"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    done = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="steps")


class TaskLink(Base):
    """할 일에 연결된 깃허브 이슈/PR. 하나의 할 일에 여러 개가 붙을 수 있다."""

    __tablename__ = "task_links"
    __table_args__ = (UniqueConstraint("task_id", "number", name="uq_task_link_number"),)

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    kind = Column(String, nullable=False)  # "issue" | "pr"
    number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    state = Column(String, nullable=False, default="open")  # "open" | "closed" | "merged"
    url = Column(String, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="links")
