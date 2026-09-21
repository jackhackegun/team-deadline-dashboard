import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .database import Base, engine
from .github_api import run_sync_job
from .notifications import run_notify_job
from .routers import auth, github, tasks, teams

Base.metadata.create_all(bind=engine)

# 기존 SQLite DB에 신규 컬럼 반영 (create_all은 기존 테이블을 변경하지 않음)
# ponytail: SQLite 전용 미니 마이그레이션. Postgres 전환 시 alembic으로 교체
_NEW_COLUMNS = [
    ("teams", "github_org", "VARCHAR"),
    ("users", "github_login", "VARCHAR"),
    ("tasks", "review_requested_at", "DATETIME"),
    ("tasks", "review_requested_by", "INTEGER"),
    ("tasks", "approved_at", "DATETIME"),
    ("tasks", "approved_by", "INTEGER"),
]
if engine.dialect.name == "sqlite":
    with engine.begin() as _conn:
        for _table, _column, _type in _NEW_COLUMNS:
            _cols = [r[1] for r in _conn.exec_driver_sql(f"PRAGMA table_info({_table})")]
            if _column not in _cols:
                _conn.exec_driver_sql(f"ALTER TABLE {_table} ADD COLUMN {_column} {_type}")

SYNC_MINUTES = int(os.getenv("GITHUB_SYNC_MINUTES", "5"))

# ponytail: 스케줄러가 API 프로세스 안에서 돈다 — 인스턴스를 2개 이상 띄우면 알림·동기화가 중복된다.
# 컨테이너 1개 전제. 스케일아웃이 필요해지면 DB 잠금이나 별도 워커로 분리할 것
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_notify_job, CronTrigger(hour=9, minute=0), id="d1-notify", replace_existing=True)
    # ponytail: 폴링. 공개 URL이 필요 없어서 어디에 올려도 돈다. ETag 조건부 요청이라 호출 비용은 거의 없다
    scheduler.add_job(run_sync_job, "interval", minutes=SYNC_MINUTES, id="github-sync", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Team Deadline Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # localhost·LAN IP 등 Vite(5173)에서 오는 요청 모두 허용. ponytail: 개발용 와일드카드, 배포 시 실제 도메인으로 좁힐 것
    allow_origin_regex=r"http://[\w.\-]+:5173",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(tasks.router)
app.include_router(github.router)



# 입력 검증 실패(422)의 detail은 기본적으로 배열이라 프론트가 그대로 띄우면 "[object Object]"가 된다.
# 한 문장으로 바꿔 어느 화면에서든 사용자가 읽을 수 있게 한다.
_FIELD_NAMES = {"email": "이메일", "password": "비밀번호", "name": "이름",
                "title": "제목", "deadline": "마감일", "org": "오가니제이션", "repo": "레포"}


def _josa(word: str, with_batchim: str, without: str) -> str:
    """받침 유무에 따라 조사를 고른다. '비밀번호은(는)' 같은 문구를 피하려고."""
    last = word[-1]
    has_batchim = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
    return word + (with_batchim if has_batchim else without)


def _describe(error: dict) -> str:
    field = _FIELD_NAMES.get(str(error["loc"][-1]), str(error["loc"][-1]))
    kind = error["type"]
    if kind == "missing":
        return f"{_josa(field, '을', '를')} 입력하세요."
    if kind == "string_too_short":
        least = error.get("ctx", {}).get("min_length")
        subject = _josa(field, "은", "는")
        return f"{subject} {least}자 이상이어야 합니다." if least else f"{_josa(field, '이', '가')} 너무 짧습니다."
    if kind.startswith("value_error") and field == "이메일":
        return "이메일 형식이 올바르지 않습니다."
    return f"{field}: {error.get('msg', '입력값을 확인하세요.')}"


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    detail = _describe(errors[0]) if errors else "입력값을 확인하세요."
    return JSONResponse(status_code=422, content={"detail": detail})
