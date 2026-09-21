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
    # 커밋 작성자(author.login)와 팀원을 잇는 열쇠. 본인이 직접 입력한다
    github_login = Column(String, nullable=True, index=True)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    invite_code = Column(String, unique=True, nullable=False)
    github_org = Column(String, nullable=True)  # 깃허브 오가니제이션 이름

    repos = relationship("TeamRepo", back_populates="team", cascade="all, delete-orphan")


class TeamRepo(Base):
    """org 안에서 이 팀이 실제로 쓰는 레포. org의 모든 레포를 훑지 않기 위해 골라서 담는다."""

    __tablename__ = "team_repos"
    __table_args__ = (UniqueConstraint("team_id", "full_name", name="uq_team_repo"),)

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    full_name = Column(String, nullable=False)  # "org/name"
    etag = Column(String, nullable=True)  # 조건부 요청용
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)

    team = relationship("Team", back_populates="repos")


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
    done = Column(Boolean, default=False, nullable=False)  # 팀장이 승인해야만 True가 된다
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)

    # 완료 요청 → 팀장 승인 흐름
    review_requested_at = Column(DateTime, nullable=True)
    review_requested_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    steps = relationship("RoadmapStep", back_populates="task", cascade="all, delete-orphan")
    commits = relationship(
        "TaskCommit", back_populates="task", cascade="all, delete-orphan",
        order_by="TaskCommit.committed_at.desc()",
    )


class RoadmapStep(Base):
    __tablename__ = "roadmap_steps"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    done = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="steps")


class TaskCommit(Base):
    """할 일에 붙은 커밋. 팀장이 '정말 했는지' 확인하는 근거가 된다."""

    __tablename__ = "task_commits"
    __table_args__ = (UniqueConstraint("task_id", "sha", name="uq_task_commit"),)

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    sha = Column(String, nullable=False)
    repo = Column(String, nullable=False)  # "org/name"
    message = Column(String, nullable=False)  # 첫 줄만
    author_login = Column(String, nullable=True)  # 깃허브 계정
    author_name = Column(String, nullable=True)  # 계정을 못 찾을 때 표시용
    url = Column(String, nullable=False)
    committed_at = Column(DateTime, nullable=False)
    linked_manually = Column(Boolean, default=False, nullable=False)  # 규칙이 아니라 손으로 붙인 커밋

    task = relationship("Task", back_populates="commits")
