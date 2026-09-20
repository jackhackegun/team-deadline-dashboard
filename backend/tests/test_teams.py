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

    # 단계 없는 task는 done을 직접 토글 가능
    client.patch(f"/tasks/{task['id']}", json={"done": True}, headers=leader)
    dash = client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()
    assert dash["progress_pct"] == 100

    # 로드맵 단계가 생기면 done 직접 토글은 400, 단계 토글로만 완료
    stepped = client.post(f"/tasks/{task['id']}/steps", json={"title": "자료조사"}, headers=leader).json()
    assert stepped["done"] is False
    step_id = stepped["steps"][0]["id"]
    assert client.patch(f"/tasks/{task['id']}", json={"done": True}, headers=leader).status_code == 400

    done_task = client.patch(f"/tasks/{task['id']}/steps/{step_id}", json={"done": True}, headers=leader).json()
    assert done_task["done"] is True

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
    assert client.patch(f"/tasks/{other_task['id']}", json={"done": True}, headers=outsider).status_code == 403
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
