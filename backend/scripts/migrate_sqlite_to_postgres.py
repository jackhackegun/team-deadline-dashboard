"""개발용 SQLite의 데이터를 배포된 Postgres로 옮긴다.

기존 행을 지우지 않고 덧붙인다. id는 새로 받고 참조를 다시 이어준다.
"""
import sqlite3
import sys

sys.path.insert(0, "/app")
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Role, RoadmapStep, Task, TaskCommit, Team, TeamMember, TeamRepo, User,
)

src = sqlite3.connect("/tmp/dashboard.db")
src.row_factory = sqlite3.Row
db = SessionLocal()


def rows(table):
    try:
        return [dict(r) for r in src.execute(f"select * from {table}")]
    except sqlite3.OperationalError:
        return []  # 그쪽 DB에 없던 테이블


user_map, team_map, task_map = {}, {}, {}
skipped = []

for r in rows("users"):
    if db.query(User).filter(User.email == r["email"]).first():
        skipped.append(r["email"])
        continue
    u = User(email=r["email"], password_hash=r["password_hash"], name=r["name"],
             github_login=r.get("github_login"))
    db.add(u)
    db.flush()
    user_map[r["id"]] = u.id

for r in rows("teams"):
    t = Team(name=r["name"], invite_code=r["invite_code"], github_org=r.get("github_org"))
    db.add(t)
    db.flush()
    team_map[r["id"]] = t.id

for r in rows("team_repos"):
    if r["team_id"] not in team_map:
        continue
    db.add(TeamRepo(team_id=team_map[r["team_id"]], full_name=r["full_name"]))

for r in rows("team_members"):
    if r["user_id"] not in user_map or r["team_id"] not in team_map:
        continue
    db.add(TeamMember(user_id=user_map[r["user_id"]], team_id=team_map[r["team_id"]],
                      role=Role(r["role"].lower() if isinstance(r["role"], str) else r["role"])))

for r in rows("tasks"):
    if r["team_id"] not in team_map:
        continue
    t = Task(
        team_id=team_map[r["team_id"]], title=r["title"],
        assignee_id=user_map.get(r["assignee_id"]), deadline=r["deadline"],
        created_by=user_map.get(r["created_by"]), done=bool(r["done"]),
        created_at=r["created_at"], updated_at=r["updated_at"], notified_at=r.get("notified_at"),
        review_requested_at=r.get("review_requested_at"),
        review_requested_by=user_map.get(r.get("review_requested_by")),
        approved_at=r.get("approved_at"), approved_by=user_map.get(r.get("approved_by")),
    )
    if t.assignee_id is None or t.created_by is None:
        continue  # 옮기지 못한 사용자를 가리키는 할 일은 건너뛴다
    db.add(t)
    db.flush()
    task_map[r["id"]] = t.id

for r in rows("roadmap_steps"):
    if r["task_id"] not in task_map:
        continue
    db.add(RoadmapStep(task_id=task_map[r["task_id"]], title=r["title"], done=bool(r["done"]),
                       created_at=r["created_at"], updated_at=r["updated_at"]))

for r in rows("task_commits"):
    if r["task_id"] not in task_map:
        continue
    db.add(TaskCommit(task_id=task_map[r["task_id"]], sha=r["sha"], repo=r["repo"],
                      message=r["message"], author_login=r.get("author_login"),
                      author_name=r.get("author_name"), url=r["url"],
                      committed_at=r["committed_at"], linked_manually=bool(r["linked_manually"])))

db.commit()
print(f"사용자 {len(user_map)}명, 팀 {len(team_map)}개, 할 일 {len(task_map)}건 이관")
if skipped:
    print(f"건너뜀(이미 있는 이메일): {skipped}")
print("옮겨진 계정:", [e for e in (r["email"] for r in rows("users")) if e not in skipped])
