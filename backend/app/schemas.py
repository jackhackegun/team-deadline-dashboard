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


class GithubConnect(BaseModel):
    repo: str  # "owner/name" 또는 GitHub URL


class TeamOut(BaseModel):
    id: int
    name: str
    invite_code: str
    role: str


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


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    title: str
    assignee_id: int
    deadline: datetime
    done: bool
    created_by: int
    steps: list[StepOut] = []


class MemberProgress(BaseModel):
    user_id: int
    name: str
    role: str
    progress_pct: int
    overdue_count: int


class DashboardOut(BaseModel):
    team_id: int
    team_name: str
    progress_pct: int
    members: list[MemberProgress]
    tasks: list[TaskOut]
