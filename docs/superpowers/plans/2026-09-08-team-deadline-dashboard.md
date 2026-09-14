# 팀 프로젝트 데드라인 대시보드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 팀플/사이드 프로젝트 팀원들의 할 일과 마감을 한 화면에서 진행률 게이지로 보여주는 웹 대시보드(FastAPI 백엔드 + React 프론트)를 구축한다.

**Architecture:** 단일 FastAPI 프로세스가 REST API와 APScheduler 기반 D-1 이메일 알림을 함께 처리하는 모놀리스. React(Vite) SPA가 60초 폴링으로 대시보드를 갱신한다. 실시간(WebSocket)은 사용하지 않는다.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite(개발/테스트)/PostgreSQL(운영), PyJWT, APScheduler, smtplib, pytest, httpx / React 18, Vite, react-router-dom, Vitest, @testing-library/react

**Spec:** `docs/team-deadline-dashboard-design-doc.md` (및 `docs/superpowers/specs/2026-09-08-team-deadline-dashboard-design.md`)

## Global Constraints

- 백엔드: FastAPI + SQLAlchemy. 개발/테스트는 SQLite, 운영 전환 시 `DATABASE_URL` 환경변수로 PostgreSQL 사용 (스펙 3절).
- 인증: JWT(PyJWT). 비밀번호 해싱은 외부 라이브러리 없이 stdlib `hashlib.pbkdf2_hmac` 사용.
- 마이그레이션 도구(Alembic) 없이 `Base.metadata.create_all`로 테이블 생성 (MVP 범위, 스펙 8절 "제외 범위").
- 실시간 갱신 없음 — 프론트는 진입 시 fetch + 60초 폴링만 사용 (스펙 3절 아키텍처 결정).
- 알림은 별도 워커/외부 크론 없이 API 프로세스 내 APScheduler가 1일 1회 처리 (스펙 3절).
- 할 일 생성·배정은 팀원 누구나 가능 (역할은 leader/member로 구분되지만 생성 권한 제한 없음, 스펙 2절 F4).
- 진행률·마감 임박 여부는 저장 컬럼이 아니라 조회 시점 집계로 계산 (스펙 4절).

---

### Task 0: 저장소 초기화

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: git 저장소 초기화 (이미 되어있지 않다면)**

```bash
cd "/Users/kmsmss/Desktop/class/claude project/ch05"
git init
```

- [ ] **Step 2: .gitignore 작성**

```
__pycache__/
*.pyc
.venv/
backend/dashboard.db
node_modules/
frontend/dist/
```

- [ ] **Step 3: 커밋**

```bash
git add .gitignore
git commit -m "chore: initialize repository"
```

---

### Task 1: 백엔드 스캐폴드 및 ORM 모델

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Base`(declarative base), `SessionLocal`, `get_db()` (from `app.database`) / `User`, `Team`, `TeamMember`, `Task`, `RoadmapStep`, `Role`(enum: leader, member) (from `app.models`). `Task.done`(bool)과 `RoadmapStep.done`(bool)이 진행률 계산의 기반 — 단계가 있으면 단계 완료 비율로, 없으면 `Task.done` 자체가 1단위로 집계된다 (Task 5에서 사용).

- [ ] **Step 1: requirements.txt 작성**

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic[email]
pyjwt
apscheduler
pytest
httpx
```

- [ ] **Step 2: 가상환경 생성 및 의존성 설치**

```bash
cd "/Users/kmsmss/Desktop/class/claude project/ch05/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 3: database.py 작성**

```python
# backend/app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dashboard.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: models.py 작성 (실패하는 테스트 먼저 작성)**

```python
# backend/tests/test_models.py
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User, Team, TeamMember, Task, RoadmapStep, Role


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_create_user_team_task_round_trip():
    db = make_session()
    user = User(email="a@test.com", password_hash="x", name="A")
    db.add(user)
    db.commit()

    team = Team(name="캡스톤", invite_code="ABC123")
    db.add(team)
    db.commit()

    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.leader))
    db.add(Task(
        team_id=team.id, title="발표자료", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=1), created_by=user.id,
    ))
    db.commit()

    assert db.query(Task).count() == 1
    assert db.query(Task).first().done is False


def test_roadmap_step_belongs_to_task():
    db = make_session()
    user = User(email="b@test.com", password_hash="x", name="B")
    db.add(user)
    db.commit()
    team = Team(name="팀", invite_code="XYZ999")
    db.add(team)
    db.commit()
    task = Task(
        team_id=team.id, title="발표자료", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=1), created_by=user.id,
    )
    db.add(task)
    db.commit()

    db.add(RoadmapStep(task_id=task.id, title="자료조사"))
    db.commit()

    saved_task = db.query(Task).get(task.id)
    assert len(saved_task.steps) == 1
    assert saved_task.steps[0].done is False
```

- [ ] **Step 5: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.models'"

- [ ] **Step 6: models.py 구현**

```python
# backend/app/models.py
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
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
    invite_code = Column(String, unique=True, nullable=False, index=True)


class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.member)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    title = Column(String, nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deadline = Column(DateTime, nullable=False)
    done = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)
    steps = relationship("RoadmapStep", backref="task", cascade="all, delete-orphan")


class RoadmapStep(Base):
    __tablename__ = "roadmap_steps"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    title = Column(String, nullable=False)
    done = Column(Boolean, nullable=False, default=False)
```

- 로드맵 단계가 없는 Task는 `done`을 직접 토글, 단계가 있으면 `done`은 모든 단계 완료 시 자동으로 true가 된다 (Task 4에서 구현).
- 진행률 계산 시 한 Task의 "단위(unit)"는 `len(steps) if steps else 1`, "완료 단위"는 `sum(step.done) if steps else (1 if done else 0)`로 취급한다 (Task 5에서 사용).

`backend/app/__init__.py`는 빈 파일로 생성.

- [ ] **Step 7: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 8: 커밋**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/database.py backend/app/models.py backend/tests/test_models.py
git commit -m "feat: add backend scaffold and ORM models"
```

---

### Task 2: 인증 (회원가입/로그인, JWT)

**Files:**
- Create: `backend/app/security.py`
- Create: `backend/app/schemas.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_security.py`, `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `Base`, `get_db`, `User` (Task 1)
- Produces: `hash_password(password)`, `verify_password(password, password_hash)`, `create_access_token(user_id)`, `decode_access_token(token)` (from `app.security`) / `get_current_user` dependency (from `app.deps`) / pytest fixture `client` (from `tests.conftest`, 이후 모든 라우터 테스트가 재사용)

- [ ] **Step 1: 실패하는 보안 유닛 테스트 작성**

```python
# backend/tests/test_security.py
from app.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token(user_id=42)
    assert decode_access_token(token) == 42
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.security'"

- [ ] **Step 3: security.py 구현**

```python
# backend/app/security.py
import hashlib
import hmac
import os
import secrets
import time
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7일


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, digest_hex = password_hash.split("$")
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return hmac.compare_digest(expected.hex(), digest_hex)


def create_access_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + JWT_EXPIRE_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: schemas.py 작성 (인증 관련 스키마)**

```python
# backend/app/schemas.py
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 6: deps.py 작성 (get_current_user)**

```python
# backend/app/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .security import decode_access_token
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        user_id = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 7: auth 라우터 작성**

```python
# backend/app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserLogin, TokenResponse
from ..security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email, password_hash=hash_password(payload.password), name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))
```

`backend/app/routers/__init__.py`는 빈 파일로 생성.

- [ ] **Step 8: main.py 작성**

```python
# backend/app/main.py
from fastapi import FastAPI
from .database import Base, engine
from .routers import auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Team Deadline Dashboard")
app.include_router(auth.router)
```

- [ ] **Step 9: 공용 테스트 fixture 작성**

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 10: 실패하는 API 테스트 작성**

```python
# backend/tests/test_auth.py
def test_signup_then_login(client):
    r = client.post("/auth/signup", json={"email": "a@test.com", "password": "secret123", "name": "A"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    r2 = client.post("/auth/login", json={"email": "a@test.com", "password": "secret123"})
    assert r2.status_code == 200


def test_login_wrong_password(client):
    client.post("/auth/signup", json={"email": "b@test.com", "password": "secret123", "name": "B"})
    r = client.post("/auth/login", json={"email": "b@test.com", "password": "wrong"})
    assert r.status_code == 401
```

- [ ] **Step 11: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 12: 커밋**

```bash
git add backend/app/security.py backend/app/schemas.py backend/app/deps.py backend/app/routers/__init__.py backend/app/routers/auth.py backend/app/main.py backend/tests/conftest.py backend/tests/test_security.py backend/tests/test_auth.py
git commit -m "feat: add JWT auth signup/login"
```

---

### Task 3: 팀 (생성/목록/합류)

**Files:**
- Modify: `backend/app/schemas.py` (TeamCreate, TeamJoin, TeamOut 추가)
- Create: `backend/app/routers/teams.py`
- Modify: `backend/app/main.py` (teams 라우터 등록)
- Test: `backend/tests/test_teams.py`

**Interfaces:**
- Consumes: `get_current_user`(Task 2), `Team`/`TeamMember`/`Role`(Task 1), fixture `client`(Task 2)
- Produces: `GET /teams`, `POST /teams`, `POST /teams/{team_id}/join` 엔드포인트, `TeamOut` 스키마 (id, name, invite_code, role)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# backend/tests/test_teams.py
def _signup(client, email):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": email})
    return r.json()["access_token"]


def test_create_list_and_join_team(client):
    token_a = _signup(client, "leader@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    r = client.post("/teams", json={"name": "캡스톤"}, headers=headers_a)
    assert r.status_code == 200
    team = r.json()
    assert team["role"] == "leader"

    r_list = client.get("/teams", headers=headers_a)
    assert len(r_list.json()) == 1

    token_b = _signup(client, "member@test.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    r_join = client.post(
        f"/teams/{team['id']}/join", json={"invite_code": team["invite_code"]}, headers=headers_b
    )
    assert r_join.status_code == 200
    assert r_join.json()["role"] == "member"
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_teams.py -v`
Expected: FAIL with "404 Not Found" (라우터 없음)

- [ ] **Step 3: schemas.py에 팀 관련 스키마 추가**

```python
# backend/app/schemas.py 에 추가
class TeamCreate(BaseModel):
    name: str


class TeamJoin(BaseModel):
    invite_code: str


class TeamOut(BaseModel):
    id: int
    name: str
    invite_code: str
    role: str
```

- [ ] **Step 4: teams 라우터 구현**

```python
# backend/app/routers/teams.py
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User, Team, TeamMember, Role
from ..schemas import TeamCreate, TeamJoin, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_my_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(TeamMember).filter(TeamMember.user_id == user.id).all()
    result = []
    for m in memberships:
        team = db.query(Team).get(m.team_id)
        result.append(TeamOut(id=team.id, name=team.name, invite_code=team.invite_code, role=m.role.value))
    return result


@router.post("", response_model=TeamOut)
def create_team(payload: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = Team(name=payload.name, invite_code=secrets.token_hex(4))
    db.add(team)
    db.commit()
    db.refresh(team)
    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.leader))
    db.commit()
    return TeamOut(id=team.id, name=team.name, invite_code=team.invite_code, role=Role.leader.value)


@router.post("/{team_id}/join", response_model=TeamOut)
def join_team(
    team_id: int, payload: TeamJoin, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    team = db.query(Team).get(team_id)
    if not team or team.invite_code != payload.invite_code:
        raise HTTPException(status_code=404, detail="Invalid team or invite code")
    existing = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == user.id, TeamMember.team_id == team.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    db.add(TeamMember(user_id=user.id, team_id=team.id, role=Role.member))
    db.commit()
    return TeamOut(id=team.id, name=team.name, invite_code=team.invite_code, role=Role.member.value)
```

- [ ] **Step 5: main.py에 라우터 등록**

```python
# backend/app/main.py — import 및 include_router 추가
from .routers import auth, teams
...
app.include_router(teams.router)
```

- [ ] **Step 6: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_teams.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/schemas.py backend/app/routers/teams.py backend/app/main.py backend/tests/test_teams.py
git commit -m "feat: add team create/list/join endpoints"
```

---

### Task 4: 할 일 + 로드맵 단계 (생성/수정/삭제, 단계 추가/완료 토글)

**Files:**
- Modify: `backend/app/schemas.py` (TaskCreate, TaskUpdate, TaskOut, StepCreate, StepUpdate, StepOut 추가)
- Create: `backend/app/routers/tasks.py`
- Modify: `backend/app/main.py` (tasks 라우터 등록)
- Test: `backend/tests/test_tasks.py`

**Interfaces:**
- Consumes: `get_current_user`(Task 2), `Task`/`RoadmapStep`/`TeamMember`(Task 1)
- Produces: `POST /teams/{team_id}/tasks`, `PATCH /tasks/{task_id}`(단계 없을 때만 `done` 토글 허용, 있으면 400), `DELETE /tasks/{task_id}`, `POST /tasks/{task_id}/steps`, `PATCH /tasks/{task_id}/steps/{step_id}` / `TaskOut` 스키마 (id, team_id, title, assignee_id, deadline, done, created_by, steps: StepOut[])

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# backend/tests/test_tasks.py
def _signup(client, email):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": email})
    return r.json()["access_token"]


def test_task_without_steps_can_be_toggled_done_directly(client):
    token = _signup(client, "leader2@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    team = client.post("/teams", json={"name": "팀"}, headers=headers).json()

    r = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "회의록 정리", "assignee_id": 1, "deadline": "2026-09-10T00:00:00"},
        headers=headers,
    )
    assert r.status_code == 200
    task = r.json()
    assert task["done"] is False
    assert task["steps"] == []

    r2 = client.patch(f"/tasks/{task['id']}", json={"done": True}, headers=headers)
    assert r2.json()["done"] is True

    r3 = client.delete(f"/tasks/{task['id']}", headers=headers)
    assert r3.status_code == 200


def test_task_with_steps_completes_automatically_and_blocks_manual_toggle(client):
    token = _signup(client, "leader4@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    team = client.post("/teams", json={"name": "팀"}, headers=headers).json()
    task = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "발표자료", "assignee_id": 1, "deadline": "2026-09-10T00:00:00"},
        headers=headers,
    ).json()

    client.post(f"/tasks/{task['id']}/steps", json={"title": "자료조사"}, headers=headers)
    with_step2 = client.post(
        f"/tasks/{task['id']}/steps", json={"title": "초안작성"}, headers=headers
    ).json()
    assert len(with_step2["steps"]) == 2
    assert with_step2["done"] is False

    rejected = client.patch(f"/tasks/{task['id']}", json={"done": True}, headers=headers)
    assert rejected.status_code == 400

    step_ids = [s["id"] for s in with_step2["steps"]]
    client.patch(f"/tasks/{task['id']}/steps/{step_ids[0]}", json={"done": True}, headers=headers)
    final = client.patch(f"/tasks/{task['id']}/steps/{step_ids[1]}", json={"done": True}, headers=headers)
    assert final.json()["done"] is True
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_tasks.py -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: schemas.py에 Task/Step 관련 스키마 추가**

```python
# backend/app/schemas.py 에 추가
from datetime import datetime
from typing import Optional


class TaskCreate(BaseModel):
    title: str
    assignee_id: int
    deadline: datetime


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    assignee_id: Optional[int] = None
    deadline: Optional[datetime] = None
    done: Optional[bool] = None


class StepCreate(BaseModel):
    title: str


class StepUpdate(BaseModel):
    done: bool


class StepOut(BaseModel):
    id: int
    title: str
    done: bool


class TaskOut(BaseModel):
    id: int
    team_id: int
    title: str
    assignee_id: int
    deadline: datetime
    done: bool
    created_by: int
    steps: list[StepOut] = []
```

- [ ] **Step 4: tasks 라우터 구현**

```python
# backend/app/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User, Task, RoadmapStep, TeamMember
from ..schemas import TaskCreate, TaskUpdate, TaskOut, StepCreate, StepUpdate, StepOut

router = APIRouter(tags=["tasks"])


def _require_membership(db: Session, user_id: int, team_id: int):
    m = db.query(TeamMember).filter(TeamMember.user_id == user_id, TeamMember.team_id == team_id).first()
    if not m:
        raise HTTPException(status_code=403, detail="Not a team member")


def _to_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id, team_id=task.team_id, title=task.title, assignee_id=task.assignee_id,
        deadline=task.deadline, done=task.done, created_by=task.created_by,
        steps=[StepOut(id=s.id, title=s.title, done=s.done) for s in task.steps],
    )


def _get_task_or_404(db: Session, task_id: int) -> Task:
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/teams/{team_id}/tasks", response_model=TaskOut)
def create_task(
    team_id: int, payload: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _require_membership(db, user.id, team_id)
    task = Task(
        team_id=team_id, title=payload.title, assignee_id=payload.assignee_id,
        deadline=payload.deadline, created_by=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _to_out(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, payload: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    task = _get_task_or_404(db, task_id)
    _require_membership(db, user.id, task.team_id)
    if payload.title is not None:
        task.title = payload.title
    if payload.assignee_id is not None:
        task.assignee_id = payload.assignee_id
    if payload.deadline is not None:
        task.deadline = payload.deadline
    if payload.done is not None:
        if task.steps:
            raise HTTPException(
                status_code=400, detail="로드맵 단계가 있는 할 일은 단계를 통해서만 완료 처리할 수 있습니다"
            )
        task.done = payload.done
    db.commit()
    db.refresh(task)
    return _to_out(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, task_id)
    _require_membership(db, user.id, task.team_id)
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/steps", response_model=TaskOut)
def add_step(
    task_id: int, payload: StepCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    task = _get_task_or_404(db, task_id)
    _require_membership(db, user.id, task.team_id)
    db.add(RoadmapStep(task_id=task.id, title=payload.title, done=False))
    task.done = False  # 새 단계가 생기면 아직 전부 완료된 상태가 아님
    db.commit()
    db.refresh(task)
    return _to_out(task)


@router.patch("/tasks/{task_id}/steps/{step_id}", response_model=TaskOut)
def toggle_step(
    task_id: int, step_id: int, payload: StepUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    task = _get_task_or_404(db, task_id)
    _require_membership(db, user.id, task.team_id)
    step = db.query(RoadmapStep).filter(RoadmapStep.id == step_id, RoadmapStep.task_id == task_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    step.done = payload.done
    db.flush()
    task.done = bool(task.steps) and all(s.done for s in task.steps)
    db.commit()
    db.refresh(task)
    return _to_out(task)
```

- [ ] **Step 5: main.py에 라우터 등록**

```python
# backend/app/main.py
from .routers import auth, teams, tasks
...
app.include_router(tasks.router)
```

- [ ] **Step 6: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_tasks.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/schemas.py backend/app/routers/tasks.py backend/app/main.py backend/tests/test_tasks.py
git commit -m "feat: add task CRUD with roadmap step checklist"
```

---

### Task 5: 대시보드 집계 엔드포인트

**Files:**
- Modify: `backend/app/schemas.py` (MemberProgress, DashboardOut 추가)
- Create: `backend/app/routers/dashboard.py`
- Modify: `backend/app/main.py` (dashboard 라우터 등록)
- Test: `backend/tests/test_dashboard.py`

**Interfaces:**
- Consumes: `Team`/`TeamMember`/`Task`/`RoadmapStep`(Task 1), `TaskOut`/`StepOut`(Task 4 스키마, 여기서도 자체 변환 함수로 조립 — 라우터 간 결합 최소화)
- Produces: `GET /teams/{team_id}/dashboard` → `DashboardOut` (team_id, team_name, progress_pct, members: MemberProgress[], tasks: TaskOut[]). `progress_pct`는 Task 1에서 정의한 "단위/완료단위" 규칙(단계 있으면 단계 비율, 없으면 done 자체가 1단위)으로 집계.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# backend/tests/test_dashboard.py
from datetime import datetime, timedelta


def _signup(client, email):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": email})
    return r.json()["access_token"]


def test_dashboard_aggregates_progress_from_roadmap_steps(client):
    token = _signup(client, "leader3@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    team = client.post("/teams", json={"name": "팀"}, headers=headers).json()

    future = (datetime.utcnow() + timedelta(days=5)).isoformat()
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()

    # 로드맵 없는 할 일, 직접 완료 처리 -> 1/1 단위
    t1 = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "A", "assignee_id": 1, "deadline": future}, headers=headers,
    ).json()
    client.patch(f"/tasks/{t1['id']}", json={"done": True}, headers=headers)

    # 로드맵 2단계 중 1단계만 완료, 마감 초과 -> 1/2 단위 + overdue 1건
    t2 = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "B", "assignee_id": 1, "deadline": past}, headers=headers,
    ).json()
    step1 = client.post(f"/tasks/{t2['id']}/steps", json={"title": "step1"}, headers=headers).json()["steps"][-1]
    client.post(f"/tasks/{t2['id']}/steps", json={"title": "step2"}, headers=headers)
    client.patch(f"/tasks/{t2['id']}/steps/{step1['id']}", json={"done": True}, headers=headers)

    r = client.get(f"/teams/{team['id']}/dashboard", headers=headers)
    data = r.json()
    assert data["progress_pct"] == 67  # (1 + 1) 완료단위 / (1 + 2) 전체단위 ≈ 67%
    assert data["members"][0]["overdue_count"] == 1  # t2는 아직 전부 끝나지 않았고 마감 초과
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_dashboard.py -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: schemas.py에 대시보드 스키마 추가**

```python
# backend/app/schemas.py 에 추가
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
```

- [ ] **Step 4: dashboard 라우터 구현**

```python
# backend/app/routers/dashboard.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User, Team, TeamMember, Task
from ..schemas import DashboardOut, MemberProgress, TaskOut, StepOut

router = APIRouter(tags=["dashboard"])


def _task_units(task: Task) -> tuple[int, int]:
    """(완료 단위, 전체 단위) — 단계가 있으면 단계 비율, 없으면 done 자체가 1단위."""
    if task.steps:
        return sum(1 for s in task.steps if s.done), len(task.steps)
    return (1 if task.done else 0), 1


def _to_task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id, team_id=task.team_id, title=task.title, assignee_id=task.assignee_id,
        deadline=task.deadline, done=task.done, created_by=task.created_by,
        steps=[StepOut(id=s.id, title=s.title, done=s.done) for s in task.steps],
    )


@router.get("/teams/{team_id}/dashboard", response_model=DashboardOut)
def get_dashboard(team_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(Team).get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not db.query(TeamMember).filter(
        TeamMember.user_id == user.id, TeamMember.team_id == team_id
    ).first():
        raise HTTPException(status_code=403, detail="Not a team member")

    tasks = db.query(Task).filter(Task.team_id == team_id).all()

    total_completed = total_units = 0
    for t in tasks:
        c, u = _task_units(t)
        total_completed += c
        total_units += u
    team_progress = round(total_completed / total_units * 100) if total_units else 0

    now = datetime.utcnow()
    members = []
    for m in db.query(TeamMember).filter(TeamMember.team_id == team_id).all():
        member_user = db.query(User).get(m.user_id)
        my_tasks = [t for t in tasks if t.assignee_id == m.user_id]
        my_completed = my_total = 0
        overdue = 0
        for t in my_tasks:
            c, u = _task_units(t)
            my_completed += c
            my_total += u
            if not t.done and t.deadline < now:
                overdue += 1
        members.append(MemberProgress(
            user_id=m.user_id, name=member_user.name, role=m.role.value,
            progress_pct=round(my_completed / my_total * 100) if my_total else 0,
            overdue_count=overdue,
        ))

    return DashboardOut(
        team_id=team.id, team_name=team.name, progress_pct=team_progress,
        members=members, tasks=[_to_task_out(t) for t in tasks],
    )
```

- [ ] **Step 5: main.py에 라우터 등록**

```python
# backend/app/main.py
from .routers import auth, teams, tasks, dashboard
...
app.include_router(dashboard.router)
```

- [ ] **Step 6: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add backend/app/schemas.py backend/app/routers/dashboard.py backend/app/main.py backend/tests/test_dashboard.py
git commit -m "feat: add dashboard aggregation endpoint"
```

---

### Task 6: 마감 D-1 알림 스케줄러

**Files:**
- Create: `backend/app/email_utils.py`
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py` (startup 이벤트에 스케줄러 등록)
- Test: `backend/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `SessionLocal`(Task 1 `app.database`), `Task`/`User`(Task 1) — 완료 여부는 `Task.done`으로 판단(로드맵 단계 유무와 무관하게 Task 4가 항상 최신 상태로 동기화)
- Produces: `send_deadline_reminder(to_email, task_title, deadline_str)` (`app.email_utils`) / `check_and_notify_deadlines(db) -> int`, `start_scheduler() -> BackgroundScheduler` (`app.scheduler`)

- [ ] **Step 1: email_utils.py 작성**

```python
# backend/app/email_utils.py
import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def send_deadline_reminder(to_email: str, task_title: str, deadline_str: str) -> None:
    msg = MIMEText(f"'{task_title}' 마감이 {deadline_str}입니다. 아직 완료되지 않았어요!")
    msg["Subject"] = f"[마감 D-1] {task_title}"
    msg["From"] = SMTP_USER or "noreply@dashboard.local"
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USER:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(msg["From"], [to_email], msg.as_string())
```

- [ ] **Step 2: 실패하는 테스트 작성 (이메일 발송은 mock 처리)**

```python
# backend/tests/test_scheduler.py
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User, Team, Task
from app.scheduler import check_and_notify_deadlines


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_notifies_only_tasks_due_tomorrow_and_unnotified():
    db = make_session()
    user = User(email="a@test.com", password_hash="x", name="A")
    db.add(user)
    db.commit()
    team = Team(name="팀", invite_code="X")
    db.add(team)
    db.commit()

    due_tomorrow = Task(
        team_id=team.id, title="내일마감", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(hours=20), created_by=user.id,
    )
    due_later = Task(
        team_id=team.id, title="다음주마감", assignee_id=user.id,
        deadline=datetime.utcnow() + timedelta(days=10), created_by=user.id,
    )
    db.add_all([due_tomorrow, due_later])
    db.commit()

    with patch("app.scheduler.send_deadline_reminder") as mock_send:
        count = check_and_notify_deadlines(db)

    assert count == 1
    mock_send.assert_called_once()
    assert due_tomorrow.notified_at is not None
    assert due_later.notified_at is None
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `cd backend && pytest tests/test_scheduler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.scheduler'"

- [ ] **Step 4: scheduler.py 구현**

```python
# backend/app/scheduler.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from .database import SessionLocal
from .models import Task, User
from .email_utils import send_deadline_reminder


def check_and_notify_deadlines(db: Session) -> int:
    now = datetime.utcnow()
    window_end = now + timedelta(days=1)
    tasks = (
        db.query(Task)
        .filter(Task.done.is_(False))
        .filter(Task.deadline >= now)
        .filter(Task.deadline <= window_end)
        .filter(Task.notified_at.is_(None))
        .all()
    )
    for task in tasks:
        user = db.query(User).get(task.assignee_id)
        send_deadline_reminder(user.email, task.title, task.deadline.isoformat())
        task.notified_at = now
    db.commit()
    return len(tasks)


def run_daily_check():
    db = SessionLocal()
    try:
        check_and_notify_deadlines(db)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_check, "interval", days=1)
    scheduler.start()
    return scheduler
```

- [ ] **Step 5: 테스트 실행 (통과 확인)**

Run: `cd backend && pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 6: main.py에 스케줄러 startup 이벤트 등록**

```python
# backend/app/main.py
from .scheduler import start_scheduler

@app.on_event("startup")
def _start_scheduler():
    start_scheduler()
```

- [ ] **Step 7: 전체 백엔드 테스트 실행 (회귀 확인)**

Run: `cd backend && pytest -v`
Expected: 모든 테스트 PASS (test_models, test_security, test_auth, test_teams, test_tasks, test_dashboard, test_scheduler)

- [ ] **Step 8: 커밋**

```bash
git add backend/app/email_utils.py backend/app/scheduler.py backend/app/main.py backend/tests/test_scheduler.py
git commit -m "feat: add D-1 deadline email notification scheduler"
```

---

### Task 7: 프론트엔드 스캐폴드 (Vite + API 클라이언트)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api.js`
- Create: `frontend/src/setupTests.js`
- Test: `frontend/src/api.test.js`, `frontend/src/App.test.jsx`

**Interfaces:**
- Produces: `apiFetch(path, options)`, `getToken()`, `setToken(token)` (from `src/api.js`) — Task 8/9의 모든 페이지가 이 3개 함수로 백엔드와 통신

- [ ] **Step 1: package.json 작성**

```json
{
  "name": "team-deadline-dashboard-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.23.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^14.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "jsdom": "^24.0.0",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

- [ ] **Step 2: 의존성 설치**

```bash
cd "/Users/kmsmss/Desktop/class/claude project/ch05/frontend"
npm install
```

- [ ] **Step 3: vite.config.js, index.html, main.jsx, setupTests.js 작성**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
  },
})
```

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <title>팀 데드라인 대시보드</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

```jsx
// frontend/src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

```javascript
// frontend/src/setupTests.js
import '@testing-library/jest-dom'
```

- [ ] **Step 4: 실패하는 api.js 테스트 작성**

```javascript
// frontend/src/api.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiFetch, setToken } from './api'

describe('apiFetch', () => {
  beforeEach(() => {
    localStorage.clear()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hello: 'world' }),
    })
  })

  it('attaches Authorization header when token exists', async () => {
    setToken('abc123')
    await apiFetch('/teams')
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer abc123')
  })

  it('throws when response is not ok', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'bad' }),
    })
    await expect(apiFetch('/teams')).rejects.toThrow('bad')
  })
})
```

- [ ] **Step 5: 테스트 실행 (실패 확인)**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module './api'"

- [ ] **Step 6: api.js 구현**

```javascript
// frontend/src/api.js
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function getToken() {
  return localStorage.getItem('token')
}

export function setToken(token) {
  localStorage.setItem('token', token)
}

export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}
```

- [ ] **Step 7: App.jsx placeholder 및 테스트 작성**

```jsx
// frontend/src/App.jsx (Task 9에서 라우팅 포함 버전으로 교체됨)
export default function App() {
  return <div>Team Deadline Dashboard</div>
}
```

```jsx
// frontend/src/App.test.jsx (Task 9에서 교체됨)
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('renders placeholder heading', () => {
    render(<App />)
    expect(screen.getByText(/Team Deadline Dashboard/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 8: 테스트 실행 (통과 확인)**

Run: `cd frontend && npm test`
Expected: PASS (api.test.js 2개, App.test.jsx 1개)

- [ ] **Step 9: 커밋**

```bash
git add frontend/package.json frontend/vite.config.js frontend/index.html frontend/src/main.jsx frontend/src/App.jsx frontend/src/api.js frontend/src/setupTests.js frontend/src/api.test.js frontend/src/App.test.jsx
git commit -m "feat: add frontend scaffold and API client"
```

---

### Task 8: 로그인/회원가입/팀 목록 페이지

**Files:**
- Create: `frontend/src/pages/Login.jsx`
- Create: `frontend/src/pages/Signup.jsx`
- Create: `frontend/src/pages/Teams.jsx`
- Test: `frontend/src/pages/Login.test.jsx`, `frontend/src/pages/Teams.test.jsx`

**Interfaces:**
- Consumes: `apiFetch`, `setToken`(Task 7 `src/api.js`)
- Produces: `Login`, `Signup`, `Teams` 컴포넌트 (default export) — Task 9 최종 `App.jsx`가 라우트로 연결

- [ ] **Step 1: 실패하는 Login 테스트 작성**

```jsx
// frontend/src/pages/Login.test.jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Login from './Login'

describe('Login', () => {
  beforeEach(() => {
    localStorage.clear()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'tok123' }),
    })
  })

  it('logs in and stores token', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )
    fireEvent.change(screen.getByLabelText('이메일'), { target: { value: 'a@test.com' } })
    fireEvent.change(screen.getByLabelText('비밀번호'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByText('로그인'))
    await waitFor(() => expect(localStorage.getItem('token')).toBe('tok123'))
  })
})
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module './Login'"

- [ ] **Step 3: Login.jsx 구현**

```jsx
// frontend/src/pages/Login.jsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiFetch, setToken } from '../api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setToken(data.access_token)
      navigate('/teams')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>로그인</h1>
      <input aria-label="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input
        aria-label="비밀번호"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit">로그인</button>
      <Link to="/signup">회원가입</Link>
    </form>
  )
}
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 5: Signup.jsx 구현 (테스트 없이 Login과 동일 패턴 — 이름 필드만 추가)**

```jsx
// frontend/src/pages/Signup.jsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { apiFetch, setToken } from '../api'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await apiFetch('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email, password, name }),
      })
      setToken(data.access_token)
      navigate('/teams')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>회원가입</h1>
      <input aria-label="이름" value={name} onChange={(e) => setName(e.target.value)} />
      <input aria-label="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input
        aria-label="비밀번호"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit">회원가입</button>
      <Link to="/login">로그인</Link>
    </form>
  )
}
```

- [ ] **Step 6: 실패하는 Teams 테스트 작성**

```jsx
// frontend/src/pages/Teams.test.jsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Teams from './Teams'

describe('Teams', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: 1, name: '캡스톤', invite_code: 'ABC', role: 'leader' }],
    })
  })

  it('lists my teams', async () => {
    render(
      <MemoryRouter>
        <Teams />
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('캡스톤')).toBeInTheDocument())
  })
})
```

- [ ] **Step 7: 테스트 실행 (실패 확인)**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module './Teams'"

- [ ] **Step 8: Teams.jsx 구현**

```jsx
// frontend/src/pages/Teams.jsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'

export default function Teams() {
  const [teams, setTeams] = useState([])
  const [name, setName] = useState('')

  async function load() {
    setTeams(await apiFetch('/teams'))
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    await apiFetch('/teams', { method: 'POST', body: JSON.stringify({ name }) })
    setName('')
    load()
  }

  return (
    <div>
      <h1>내 팀</h1>
      <ul>
        {teams.map((t) => (
          <li key={t.id}>
            <Link to={`/teams/${t.id}`}>{t.name}</Link> ({t.role})
          </li>
        ))}
      </ul>
      <form onSubmit={handleCreate}>
        <input aria-label="팀 이름" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit">팀 만들기</button>
      </form>
    </div>
  )
}
```

- [ ] **Step 9: 테스트 실행 (통과 확인)**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 10: 커밋**

```bash
git add frontend/src/pages/Login.jsx frontend/src/pages/Signup.jsx frontend/src/pages/Teams.jsx frontend/src/pages/Login.test.jsx frontend/src/pages/Teams.test.jsx
git commit -m "feat: add login/signup/teams pages"
```

---

### Task 9: 대시보드 화면 (게이지/멤버카드/할일테이블) 및 라우팅 연결

**Files:**
- Create: `frontend/src/components/Gauge.jsx`
- Create: `frontend/src/components/MemberCard.jsx`
- Create: `frontend/src/components/TaskItem.jsx`
- Create: `frontend/src/components/TaskList.jsx`
- Create: `frontend/src/pages/Dashboard.jsx`
- Modify: `frontend/src/App.jsx` (전체 라우팅으로 교체)
- Modify: `frontend/src/App.test.jsx` (라우팅 테스트로 교체)
- Test: `frontend/src/components/Gauge.test.jsx`, `frontend/src/pages/Dashboard.test.jsx`

**Interfaces:**
- Consumes: `apiFetch`, `getToken`(Task 7), `Login`/`Signup`/`Teams`(Task 8), `TaskOut`/`StepOut` 응답 형태(Task 4/5: `task.steps`는 `{id, title, done}[]`, 단계가 있으면 `task.done`은 서버가 자동 계산해 직접 토글 불가)
- Produces: `Gauge`, `MemberCard`, `TaskItem`, `TaskList`, `Dashboard` 컴포넌트 (Dashboard는 할 일 조회/등록뿐 아니라 완료 토글·로드맵 단계 추가/완료 토글까지 담당) / 최종 `App` (라우트: `/login`, `/signup`, `/teams`, `/teams/:teamId`)

- [ ] **Step 1: 실패하는 Gauge 테스트 작성**

```jsx
// frontend/src/components/Gauge.test.jsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Gauge from './Gauge'

describe('Gauge', () => {
  it('renders percent label', () => {
    render(<Gauge percent={68} />)
    expect(screen.getByText('68%')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module './Gauge'"

- [ ] **Step 3: Gauge.jsx 구현 (CSS conic-gradient, 차트 라이브러리 없이 순수 CSS)**

```jsx
// frontend/src/components/Gauge.jsx
export default function Gauge({ percent, size = 100, color = '#4f46e5' }) {
  const outerStyle = {
    width: size,
    height: size,
    borderRadius: '50%',
    background: `conic-gradient(${color} ${percent * 3.6}deg, #e5e7eb 0)`,
  }
  const innerStyle = {
    position: 'absolute',
    inset: size * 0.12,
    background: '#fff',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 700,
  }

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <div style={outerStyle} />
      <div style={innerStyle}>{percent}%</div>
    </div>
  )
}
```

- [ ] **Step 4: 테스트 실행 (통과 확인)**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 5: MemberCard.jsx, TaskItem.jsx, TaskList.jsx 구현 (테스트 없이 — Dashboard 통합 검증으로 갈음)**

```jsx
// frontend/src/components/MemberCard.jsx
import Gauge from './Gauge'

export default function MemberCard({ member }) {
  const warn = member.overdue_count > 0
  return (
    <div className="member-card">
      <Gauge percent={member.progress_pct} size={60} color={warn ? '#dc2626' : '#4f46e5'} />
      <div>
        <div>{member.name}</div>
        <span>{warn ? `미완료 ${member.overdue_count}개` : '정상 진행중'}</span>
      </div>
    </div>
  )
}
```

```jsx
// frontend/src/components/TaskItem.jsx
import { useState } from 'react'

export default function TaskItem({ task, onToggleDone, onAddStep, onToggleStep }) {
  const [newStep, setNewStep] = useState('')
  const now = new Date()
  const deadline = new Date(task.deadline)
  const overdue = !task.done && deadline < now
  const soon = !overdue && !task.done && deadline - now < 24 * 60 * 60 * 1000
  const background = overdue ? '#fef2f2' : soon ? '#fffbeb' : 'transparent'

  function handleAddStep(e) {
    e.preventDefault()
    if (!newStep.trim()) return
    onAddStep(task.id, newStep)
    setNewStep('')
  }

  return (
    <li style={{ background }}>
      <label>
        <input
          type="checkbox"
          checked={task.done}
          disabled={task.steps.length > 0}
          onChange={(e) => onToggleDone(task.id, e.target.checked)}
        />
        {task.title} (담당: {task.assignee_id}, 마감: {deadline.toLocaleDateString()})
      </label>

      {task.steps.length > 0 && (
        <ul>
          {task.steps.map((s) => (
            <li key={s.id}>
              <label>
                <input
                  type="checkbox"
                  checked={s.done}
                  onChange={(e) => onToggleStep(task.id, s.id, e.target.checked)}
                />
                {s.title}
              </label>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAddStep}>
        <input
          aria-label={`${task.title} 로드맵 단계 추가`}
          value={newStep}
          onChange={(e) => setNewStep(e.target.value)}
        />
        <button type="submit">단계 추가</button>
      </form>
    </li>
  )
}
```

```jsx
// frontend/src/components/TaskList.jsx
import TaskItem from './TaskItem'

export default function TaskList({ tasks, onToggleDone, onAddStep, onToggleStep }) {
  return (
    <ul>
      {tasks.map((t) => (
        <TaskItem
          key={t.id}
          task={t}
          onToggleDone={onToggleDone}
          onAddStep={onAddStep}
          onToggleStep={onToggleStep}
        />
      ))}
    </ul>
  )
}
```

- [ ] **Step 6: 실패하는 Dashboard 테스트 작성 (할 일 등록 폼 포함)**

```jsx
// frontend/src/pages/Dashboard.test.jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Dashboard from './Dashboard'

const dashboardData = {
  team_id: 1,
  team_name: '캡스톤',
  progress_pct: 50,
  members: [{ user_id: 1, name: '김민수', role: 'leader', progress_pct: 50, overdue_count: 0 }],
  tasks: [
    {
      id: 10, team_id: 1, title: '발표자료', assignee_id: 1,
      deadline: '2026-09-20T00:00:00', done: false, created_by: 1,
      steps: [{ id: 100, title: '자료조사', done: false }],
    },
    {
      id: 11, team_id: 1, title: '회의록 정리', assignee_id: 1,
      deadline: '2026-09-21T00:00:00', done: false, created_by: 1,
      steps: [],
    },
  ],
}

describe('Dashboard', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => dashboardData,
    })
  })

  it('submits new task via the add-task form', async () => {
    render(
      <MemoryRouter initialEntries={['/teams/1']}>
        <Routes>
          <Route path="/teams/:teamId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('캡스톤')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('할 일 제목'), { target: { value: '발표자료' } })
    fireEvent.change(screen.getByLabelText('담당자'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('마감일'), { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByText('할 일 추가'))

    await waitFor(() => {
      const postCall = global.fetch.mock.calls.find(([, opts]) => opts?.method === 'POST')
      expect(postCall).toBeTruthy()
      expect(postCall[0]).toBe('http://localhost:8000/teams/1/tasks')
    })
  })

  it('toggles a roadmap step checkbox', async () => {
    render(
      <MemoryRouter initialEntries={['/teams/1']}>
        <Routes>
          <Route path="/teams/:teamId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('캡스톤')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('자료조사'))

    await waitFor(() => {
      const patchCall = global.fetch.mock.calls.find(
        ([url, opts]) => opts?.method === 'PATCH' && url.includes('/steps/')
      )
      expect(patchCall).toBeTruthy()
      expect(patchCall[0]).toBe('http://localhost:8000/tasks/10/steps/100')
    })
  })

  it('toggles done directly for a task with no roadmap steps', async () => {
    render(
      <MemoryRouter initialEntries={['/teams/1']}>
        <Routes>
          <Route path="/teams/:teamId" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    )
    await waitFor(() => expect(screen.getByText('캡스톤')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText(/회의록 정리/))

    await waitFor(() => {
      const patchCall = global.fetch.mock.calls.find(
        ([url, opts]) => opts?.method === 'PATCH' && url === 'http://localhost:8000/tasks/11'
      )
      expect(patchCall).toBeTruthy()
      expect(JSON.parse(patchCall[1].body)).toEqual({ done: true })
    })
  })
})
```

- [ ] **Step 7: 테스트 실행 (실패 확인)**

Run: `cd frontend && npm test`
Expected: FAIL with "Cannot find module './Dashboard'"

- [ ] **Step 8: Dashboard.jsx 구현 (60초 폴링 + 할 일 등록 폼)**

```jsx
// frontend/src/pages/Dashboard.jsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../api'
import Gauge from '../components/Gauge'
import MemberCard from '../components/MemberCard'
import TaskList from '../components/TaskList'

export default function Dashboard() {
  const { teamId } = useParams()
  const [data, setData] = useState(null)
  const [title, setTitle] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [deadline, setDeadline] = useState('')

  async function load() {
    const result = await apiFetch(`/teams/${teamId}/dashboard`)
    setData(result)
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [teamId])

  async function handleAddTask(e) {
    e.preventDefault()
    await apiFetch(`/teams/${teamId}/tasks`, {
      method: 'POST',
      body: JSON.stringify({
        title,
        assignee_id: Number(assigneeId),
        deadline: new Date(deadline).toISOString(),
      }),
    })
    setTitle('')
    setDeadline('')
    load()
  }

  async function handleToggleDone(taskId, done) {
    await apiFetch(`/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify({ done }) })
    load()
  }

  async function handleAddStep(taskId, title) {
    await apiFetch(`/tasks/${taskId}/steps`, { method: 'POST', body: JSON.stringify({ title }) })
    load()
  }

  async function handleToggleStep(taskId, stepId, done) {
    await apiFetch(`/tasks/${taskId}/steps/${stepId}`, { method: 'PATCH', body: JSON.stringify({ done }) })
    load()
  }

  if (!data) return <p>불러오는 중...</p>

  return (
    <div>
      <h1>{data.team_name}</h1>
      <Gauge percent={data.progress_pct} size={130} />
      {data.members.map((m) => (
        <MemberCard key={m.user_id} member={m} />
      ))}

      <form onSubmit={handleAddTask}>
        <input aria-label="할 일 제목" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select aria-label="담당자" value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
          <option value="">담당자 선택</option>
          {data.members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.name}
            </option>
          ))}
        </select>
        <input
          aria-label="마감일"
          type="date"
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
        <button type="submit">할 일 추가</button>
      </form>

      <TaskList
        tasks={data.tasks}
        onToggleDone={handleToggleDone}
        onAddStep={handleAddStep}
        onToggleStep={handleToggleStep}
      />
    </div>
  )
}
```

- [ ] **Step 9: 테스트 실행 (통과 확인)**

Run: `cd frontend && npm test`
Expected: PASS

- [ ] **Step 10: App.jsx를 전체 라우팅 버전으로 교체**

```jsx
// frontend/src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Teams from './pages/Teams'
import Dashboard from './pages/Dashboard'
import { getToken } from './api'

function RequireAuth({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/teams"
          element={
            <RequireAuth>
              <Teams />
            </RequireAuth>
          }
        />
        <Route
          path="/teams/:teamId"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/teams" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 11: App.test.jsx를 라우팅 테스트로 교체**

```jsx
// frontend/src/App.test.jsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import App from './App'

describe('App routing', () => {
  beforeEach(() => {
    localStorage.clear()
    window.history.pushState({}, '', '/teams')
  })

  it('redirects unauthenticated user from /teams to /login', () => {
    render(<App />)
    expect(screen.getByText('로그인')).toBeInTheDocument()
  })
})
```

- [ ] **Step 12: 전체 프론트엔드 테스트 실행 (회귀 확인)**

Run: `cd frontend && npm test`
Expected: 모든 테스트 PASS

- [ ] **Step 13: 브라우저에서 골든패스 수동 확인**

```bash
# 터미널 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
# 터미널 2
cd frontend && npm run dev
```
브라우저에서 회원가입 → 팀 생성 → 대시보드의 "할 일 추가" 폼으로 할 일 등록 → 게이지·멤버카드·할 일 목록이 실제 데이터로 렌더링되는지, 로드맵 단계를 추가하고 체크하면 진행률이 갱신되는지, 단계가 없는 할 일은 체크박스로 직접 완료 처리되는지, 마감 초과/임박 행 강조가 반영되는지 확인.

- [ ] **Step 14: 커밋**

```bash
git add frontend/src/components/Gauge.jsx frontend/src/components/MemberCard.jsx frontend/src/components/TaskItem.jsx frontend/src/components/TaskList.jsx frontend/src/pages/Dashboard.jsx frontend/src/pages/Dashboard.test.jsx frontend/src/App.jsx frontend/src/App.test.jsx frontend/src/components/Gauge.test.jsx
git commit -m "feat: add roadmap-step-aware dashboard screen and wire up full routing"
```
