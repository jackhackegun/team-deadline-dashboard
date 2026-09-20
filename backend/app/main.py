from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .notifications import run_notify_job
from .routers import auth, github, tasks, teams

Base.metadata.create_all(bind=engine)

# 기존 SQLite DB에 신규 컬럼 반영 (create_all은 기존 테이블을 변경하지 않음)
# ponytail: SQLite 전용 미니 마이그레이션. 정식 마이그레이션이 필요해지면 alembic 도입
with engine.begin() as _conn:
    _cols = [r[1] for r in _conn.exec_driver_sql("PRAGMA table_info(teams)")]
    if "github_repo" not in _cols:
        _conn.exec_driver_sql("ALTER TABLE teams ADD COLUMN github_repo VARCHAR")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(run_notify_job, CronTrigger(hour=9, minute=0), id="d1-notify", replace_existing=True)
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
