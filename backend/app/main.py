import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .github_api import run_sync_job
from .notifications import run_notify_job
from .routers import auth, github, tasks, teams

Base.metadata.create_all(bind=engine)

# 기존 SQLite DB에 신규 컬럼 반영 (create_all은 기존 테이블을 변경하지 않음)
# ponytail: SQLite 전용 미니 마이그레이션. Postgres 전환 시 alembic으로 교체
_NEW_COLUMNS = [
    ("teams", "github_repo", "VARCHAR"),
    ("teams", "github_etag", "VARCHAR"),
    ("teams", "github_last_sync_at", "DATETIME"),
    ("teams", "github_last_error", "VARCHAR"),
    ("tasks", "auto_completed_at", "DATETIME"),
    ("tasks", "done_override", "BOOLEAN NOT NULL DEFAULT 0"),
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
