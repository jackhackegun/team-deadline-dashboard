from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TeamCreate(BaseModel):
    name: str


class TeamJoin(BaseModel):
    invite_code: str


class GithubOrgConnect(BaseModel):
    org: str  # 오가니제이션 이름


class RepoSelection(BaseModel):
    repos: list[str]  # "org/name" 목록


class CommitLink(BaseModel):
    sha: str


class MeUpdate(BaseModel):
    github_login: Optional[str] = None


class TeamOut(BaseModel):
    id: int
    name: str
    invite_code: str
    role: str
    # 팀을 열어보기 전에도 어느 팀이 급한지 알 수 있도록 목록에 요약을 싣는다
    member_count: int = 1
    task_count: int = 0
    progress_pct: int = 0
    overdue_count: int = 0
    pending_review_count: int = 0


class RepoStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool


class StepCreate(BaseModel):
    title: str


class StepUpdate(BaseModel):
    done: bool


class TaskCreate(BaseModel):
    title: str
    assignee_id: int
    deadline: datetime


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    assignee_id: Optional[int] = None
    deadline: Optional[datetime] = None
    done: Optional[bool] = None


class CommitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sha: str
    repo: str
    message: str
    author_login: Optional[str] = None
    author_name: Optional[str] = None
    url: str
    committed_at: datetime
    linked_manually: bool = False


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    title: str
    assignee_id: int
    deadline: datetime
    done: bool
    created_by: int
    review_requested_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    steps: list[StepOut] = []
    commits: list[CommitOut] = []


class MemberProgress(BaseModel):
    user_id: int
    name: str
    role: str
    progress_pct: int
    overdue_count: int
    github_login: Optional[str] = None


class DashboardOut(BaseModel):
    team_id: int
    team_name: str
    progress_pct: int
    members: list[MemberProgress]
    tasks: list[TaskOut]
    invite_code: str = ""
    github_org: Optional[str] = None
    repos: list[RepoStatus] = []
    my_role: str = "member"
    pending_review_count: int = 0
