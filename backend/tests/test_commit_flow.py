"""4단계 흐름 검증: org 등록 → 팀원 커밋 → 팀장이 화면에서 확인 → 팀장 승인으로 진행도 상승."""
from datetime import datetime

import pytest

from app import github_api
from app.routers import github as github_router
from app.routers import tasks as tasks_router


def _signup(client, email, name):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": name})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _commit(sha, message, login="devkim", date="2026-09-20T10:00:00Z"):
    return {
        "sha": sha, "html_url": f"https://github.com/acme/api/commit/{sha}",
        "author": {"login": login},
        "commit": {"message": message, "author": {"name": "김개발", "date": date}},
    }


@pytest.fixture()
def team(client, monkeypatch):
    """팀장/팀원이 있고 org·레포가 등록된 팀. state['commits']가 깃허브 응답을 대신한다."""
    leader = _signup(client, "leader@test.com", "팀장")
    member = _signup(client, "member@test.com", "팀원")
    t = client.post("/teams", json={"name": "캡스톤"}, headers=leader).json()
    client.post("/teams/join", json={"invite_code": t["invite_code"]}, headers=member)

    state = {"commits": [], "repos": [{"full_name": "acme/api", "private": False,
                                       "description": None, "pushed_at": None}]}

    def fake_gh_get(path, etag=None):
        if path.startswith("/orgs/") and path.endswith("/repos"[:0] or "") and "/repos?" in path:
            return state["repos"], "etag-repos"
        if path.startswith("/orgs/"):
            return {"login": "acme"}, None
        if "/commits" in path:
            return state["commits"], "etag-commits"
        raise AssertionError(f"예상 못 한 호출: {path}")

    for mod in (github_api, github_router, tasks_router):
        monkeypatch.setattr(mod, "gh_get", fake_gh_get, raising=False)

    client.put(f"/teams/{t['id']}/github/org", json={"org": "acme"}, headers=leader)
    client.put(f"/teams/{t['id']}/github/repos", json={"repos": ["acme/api"]}, headers=leader)
    return {"c": client, "leader": leader, "member": member, "id": t["id"], "state": state}


def _make_task(team, title="로그인 구현"):
    return team["c"].post(f"/teams/{team['id']}/tasks",
                          json={"title": title, "assignee_id": 2, "deadline": "2026-12-01T00:00:00"},
                          headers=team["leader"]).json()


def test_full_flow_commit_then_leader_approves(team):
    c, leader, member = team["c"], team["leader"], team["member"]
    task = _make_task(team)

    # 2. 팀원이 할 일 번호를 적어 커밋한다
    team["state"]["commits"] = [_commit("abc1234", f"[#{task['id']}] 로그인 API 구현")]
    assert c.post(f"/teams/{team['id']}/github/sync", headers=member).json()["repos"][0]["linked"] == 1

    # 3. 팀장 화면에서 그 커밋이 할 일에 붙어 보인다
    dash = c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    commits = dash["tasks"][0]["commits"]
    assert [(x["sha"], x["message"], x["author_login"]) for x in commits] == [
        ("abc1234", f"[#{task['id']}] 로그인 API 구현", "devkim")]
    assert dash["progress_pct"] == 0  # 커밋이 있어도 아직 진행도는 오르지 않는다

    # 팀원이 완료 요청 — 여전히 진행도는 그대로, 팀장 화면에 대기 건수만 뜬다
    c.post(f"/tasks/{task['id']}/request-review", headers=member)
    dash = c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    assert dash["pending_review_count"] == 1 and dash["progress_pct"] == 0

    # 4. 팀장이 완료를 누르면 그때 오른다
    approved = c.post(f"/tasks/{task['id']}/approve", headers=leader).json()
    assert approved["done"] is True and approved["approved_by"] == 1
    assert c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 100


def test_member_cannot_approve(team):
    """팀원은 자기 일을 스스로 완료 처리할 수 없다 — 진행도는 팀장만 올린다."""
    c, member = team["c"], team["member"]
    task = _make_task(team)
    c.post(f"/tasks/{task['id']}/request-review", headers=member)

    assert c.post(f"/tasks/{task['id']}/approve", headers=member).status_code == 403
    assert c.get(f"/teams/{team['id']}/dashboard", headers=member).json()["progress_pct"] == 0


def test_leader_can_reject_and_progress_drops(team):
    c, leader, member = team["c"], team["leader"], team["member"]
    task = _make_task(team)
    c.post(f"/tasks/{task['id']}/request-review", headers=member)
    c.post(f"/tasks/{task['id']}/approve", headers=leader)
    assert c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 100

    rejected = c.post(f"/tasks/{task['id']}/reject", headers=leader).json()
    assert rejected["done"] is False and rejected["review_requested_at"] is None
    assert c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 0


def test_commit_for_other_task_or_team_is_ignored(team):
    """남의 번호가 적힌 커밋이 엉뚱한 할 일에 붙으면 안 된다."""
    c, leader = team["c"], team["leader"]
    task = _make_task(team)

    team["state"]["commits"] = [
        _commit("dead001", "Merge pull request #6 from acme/patch-1"),  # 깃허브 PR 표기 — 붙으면 안 됨
        _commit("dead002", "[#99999] 존재하지 않는 할 일"),
        _commit("good001", f"[#{task['id']}] 진짜 이 할 일"),
    ]
    c.post(f"/teams/{team['id']}/github/sync", headers=leader)

    commits = c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["tasks"][0]["commits"]
    assert [x["sha"] for x in commits] == ["good001"]


def test_sync_is_idempotent(team):
    """같은 커밋을 두 번 훑어도 중복으로 붙지 않는다."""
    c, leader = team["c"], team["leader"]
    task = _make_task(team)
    team["state"]["commits"] = [_commit("abc1234", f"[#{task['id']}] 구현")]

    assert c.post(f"/teams/{team['id']}/github/sync", headers=leader).json()["repos"][0]["linked"] == 1
    assert c.post(f"/teams/{team['id']}/github/sync", headers=leader).json()["repos"][0]["linked"] == 0
    assert len(c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["tasks"][0]["commits"]) == 1


def test_manual_commit_link_for_forgotten_rule(team):
    """규칙을 깜빡한 커밋은 손으로 붙인다."""
    c, leader, member = team["c"], team["leader"], team["member"]
    task = _make_task(team)
    team["state"]["commits"] = [_commit("f00dcafe", "로그인 되게 고침")]  # 번호 없음

    c.post(f"/teams/{team['id']}/github/sync", headers=leader)
    assert c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["tasks"][0]["commits"] == []

    linked = c.post(f"/tasks/{task['id']}/commits", json={"sha": "f00dcafe"}, headers=member).json()
    assert [x["sha"] for x in linked["commits"]] == ["f00dcafe"]
    assert linked["commits"][0]["linked_manually"] is True

    assert c.post(f"/tasks/{task['id']}/commits", json={"sha": "f00dcafe"}, headers=member).status_code == 400
    assert c.post(f"/tasks/{task['id']}/commits", json={"sha": "nope"}, headers=member).status_code == 404


def test_only_leader_manages_org_and_repos(team):
    c, member = team["c"], team["member"]
    assert c.put(f"/teams/{team['id']}/github/org", json={"org": "evil"}, headers=member).status_code == 403
    assert c.put(f"/teams/{team['id']}/github/repos", json={"repos": []}, headers=member).status_code == 403
    # 다른 org 소속 레포는 고를 수 없다
    assert c.put(f"/teams/{team['id']}/github/repos", json={"repos": ["other/api"]},
                 headers=team["leader"]).status_code == 400


def test_github_login_links_commit_author_to_member(team):
    c, member = team["c"], team["member"]
    assert c.patch("/auth/me", json={"github_login": "@devkim"}, headers=member).json()["github_login"] == "devkim"
    members = c.get(f"/teams/{team['id']}/dashboard", headers=member).json()["members"]
    assert {m["name"]: m["github_login"] for m in members} == {"팀장": None, "팀원": "devkim"}


def test_steps_give_partial_progress_but_never_full(team):
    """단계를 다 끝내도 승인 전에는 100%가 아니다 — 마지막 한 칸은 팀장 몫."""
    c, leader, member = team["c"], team["leader"], team["member"]
    task = _make_task(team)
    c.post(f"/tasks/{task['id']}/steps", json={"title": "설계"}, headers=member)
    stepped = c.post(f"/tasks/{task['id']}/steps", json={"title": "구현"}, headers=member).json()

    for step in stepped["steps"]:
        c.patch(f"/tasks/{task['id']}/steps/{step['id']}", json={"done": True}, headers=member)

    dash = c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    assert dash["progress_pct"] == 67  # 2/3 — 단계는 끝났고 승인만 남았다
    assert dash["pending_review_count"] == 1  # 단계를 다 끝내면 완료 요청까지는 자동

    c.post(f"/tasks/{task['id']}/approve", headers=leader)
    assert c.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 100
