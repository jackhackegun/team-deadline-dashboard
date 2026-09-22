def _signup(client, email, name="X"):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": name})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_team_join_and_dashboard_flow(client):
    leader = _signup(client, "leader@test.com", "리더")
    member = _signup(client, "member@test.com", "멤버")

    team = client.post("/teams", json={"name": "캡스톤"}, headers=leader).json()
    assert team["role"] == "leader"

    joined = client.post("/teams/join", json={"invite_code": team["invite_code"]}, headers=member)
    assert joined.status_code == 200
    assert joined.json()["role"] == "member"

    # 잘못된 코드는 404, 이미 합류한 팀은 400
    assert client.post("/teams/join", json={"invite_code": "bogus"}, headers=member).status_code == 404
    assert client.post("/teams/join", json={"invite_code": team["invite_code"]}, headers=member).status_code == 400

    task = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "발표자료", "assignee_id": 2, "deadline": "2026-09-01T00:00:00"},
        headers=leader,
    ).json()
    assert task["done"] is False and task["steps"] == []

    dash = client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    assert dash["progress_pct"] == 0
    assert {m["user_id"]: m["progress_pct"] for m in dash["members"]} == {1: 0, 2: 0}

    # 진행도는 팀장 승인으로만 100%가 된다 (자세한 흐름은 test_commit_flow.py)
    client.post(f"/tasks/{task['id']}/request-review", headers=member)
    assert client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 0
    client.post(f"/tasks/{task['id']}/approve", headers=leader)
    assert client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["progress_pct"] == 100

    # 로드맵 단계는 승인 전까지 부분 진행률만 준다
    client.post(f"/tasks/{task['id']}/reject", headers=leader)
    stepped = client.post(f"/tasks/{task['id']}/steps", json={"title": "자료조사"}, headers=leader).json()
    assert stepped["done"] is False
    step_id = stepped["steps"][0]["id"]

    still_pending = client.patch(f"/tasks/{task['id']}/steps/{step_id}", json={"done": True}, headers=leader).json()
    assert still_pending["done"] is False and still_pending["review_requested_at"] is not None

    assert client.delete(f"/tasks/{task['id']}", headers=leader).status_code == 200

    # 팀원이 아니면 대시보드도, task/step 엔드포인트도 전부 403
    outsider = _signup(client, "outsider@test.com")
    assert client.get(f"/teams/{team['id']}/dashboard", headers=outsider).status_code == 403

    other_task = client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "회의록", "assignee_id": 1, "deadline": "2026-09-05T00:00:00"},
        headers=leader,
    ).json()
    assert client.post(
        f"/teams/{team['id']}/tasks",
        json={"title": "몰래", "assignee_id": 1, "deadline": "2026-09-05T00:00:00"},
        headers=outsider,
    ).status_code == 403
    assert client.patch(f"/tasks/{other_task['id']}", json={"title": "몰래"}, headers=outsider).status_code == 403
    assert client.post(f"/tasks/{other_task['id']}/request-review", headers=outsider).status_code == 403
    assert client.post(f"/tasks/{other_task['id']}/approve", headers=outsider).status_code == 403
    assert client.post(f"/tasks/{other_task['id']}/steps", json={"title": "몰래"}, headers=outsider).status_code == 403
    step = client.post(f"/tasks/{other_task['id']}/steps", json={"title": "자료조사"}, headers=leader).json()["steps"][0]
    assert client.patch(f"/tasks/{other_task['id']}/steps/{step['id']}", json={"done": True}, headers=outsider).status_code == 403
    assert client.delete(f"/tasks/{other_task['id']}", headers=outsider).status_code == 403


def test_leave_and_delete_team(client):
    leader = _signup(client, "leader2@test.com", "리더")
    member = _signup(client, "member2@test.com", "멤버")

    team = client.post("/teams", json={"name": "탈퇴테스트"}, headers=leader).json()
    client.post("/teams/join", json={"invite_code": team["invite_code"]}, headers=member)

    # 멤버만 삭제 시도 -> 403, 본인은 나갈 수 있음
    assert client.delete(f"/teams/{team['id']}", headers=member).status_code == 403
    assert client.delete(f"/teams/{team['id']}/leave", headers=member).status_code == 200
    assert client.get(f"/teams/{team['id']}/dashboard", headers=member).status_code == 403

    # 리더는 팀을 통째로 삭제할 수 있다
    assert client.delete(f"/teams/{team['id']}", headers=leader).status_code == 200
    assert client.get(f"/teams/{team['id']}/dashboard", headers=leader).status_code == 404


def test_team_list_carries_summary(client):
    """팀을 열어보기 전에도 진행률·마감 초과·승인 대기를 알 수 있어야 한다."""
    leader = _signup(client, "sum-leader@test.com", "리더")
    member = _signup(client, "sum-member@test.com", "멤버")
    team = client.post("/teams", json={"name": "요약"}, headers=leader).json()
    client.post("/teams/join", json={"invite_code": team["invite_code"]}, headers=member)

    done = client.post(f"/teams/{team['id']}/tasks",
                       json={"title": "끝난 일", "assignee_id": 2, "deadline": "2099-01-01T00:00:00"},
                       headers=leader).json()
    client.post(f"/teams/{team['id']}/tasks",
                json={"title": "지난 일", "assignee_id": 2, "deadline": "2020-01-01T00:00:00"},
                headers=leader)
    waiting = client.post(f"/teams/{team['id']}/tasks",
                          json={"title": "검토 대기", "assignee_id": 2, "deadline": "2099-01-01T00:00:00"},
                          headers=leader).json()
    client.post(f"/tasks/{done['id']}/request-review", headers=member)
    client.post(f"/tasks/{done['id']}/approve", headers=leader)
    client.post(f"/tasks/{waiting['id']}/request-review", headers=member)

    summary = next(t for t in client.get("/teams", headers=leader).json() if t["id"] == team["id"])
    assert summary["member_count"] == 2
    assert summary["task_count"] == 3
    assert summary["progress_pct"] == 33  # 3개 중 1개 승인
    assert summary["overdue_count"] == 1
    assert summary["pending_review_count"] == 1


def test_dashboard_carries_invite_code(client):
    """팀 안에서도 초대코드를 볼 수 있어야 한다 — 목록으로 되돌아가지 않고 팀원을 부를 수 있게."""
    leader = _signup(client, "invite@test.com", "리더")
    team = client.post("/teams", json={"name": "초대"}, headers=leader).json()
    dash = client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    assert dash["invite_code"] == team["invite_code"]
