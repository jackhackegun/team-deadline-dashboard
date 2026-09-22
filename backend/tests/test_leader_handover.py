"""리더가 팀을 나갈 때 팀이 얼어붙지 않아야 한다.

리더가 없으면 승인도, 팀 삭제도, 깃허브 설정도 아무도 할 수 없어
할 일이 '승인 대기'에 영원히 멈춘다.
"""


def _signup(client, email, name="X"):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": name})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _team_with_member(client):
    leader = _signup(client, "lead@t.com", "리더")
    member = _signup(client, "mem@t.com", "팀원")
    team = client.post("/teams", json={"name": "팀"}, headers=leader).json()
    client.post("/teams/join", json={"invite_code": team["invite_code"]}, headers=member)
    return leader, member, team


def _roles(client, team_id, headers):
    dash = client.get(f"/teams/{team_id}/dashboard", headers=headers).json()
    return {m["name"]: m["role"] for m in dash["members"]}


def test_leader_cannot_silently_abandon_team(client):
    """팀원이 남아 있는데 리더가 나가면, 남은 사람들이 아무것도 못 하게 된다."""
    leader, member, team = _team_with_member(client)

    res = client.delete(f"/teams/{team['id']}/leave", headers=leader)
    assert res.status_code == 400
    assert "위임" in res.json()["detail"]

    # 팀은 그대로고 리더도 그대로다
    assert _roles(client, team["id"], headers=member) == {"리더": "leader", "팀원": "member"}


def test_leader_can_leave_after_handover(client):
    leader, member, team = _team_with_member(client)
    task = client.post(f"/teams/{team['id']}/tasks",
                       json={"title": "일", "assignee_id": 2, "deadline": "2099-01-01T00:00:00"},
                       headers=leader).json()
    client.post(f"/tasks/{task['id']}/request-review", headers=member)

    member_id = next(m["user_id"] for m in
                     client.get(f"/teams/{team['id']}/dashboard", headers=leader).json()["members"]
                     if m["name"] == "팀원")
    handed = client.post(f"/teams/{team['id']}/transfer-leader",
                         json={"user_id": member_id}, headers=leader)
    assert handed.status_code == 200

    # 역할이 맞바뀐다
    assert _roles(client, team["id"], headers=member) == {"리더": "member", "팀원": "leader"}

    # 새 리더는 승인할 수 있고, 옛 리더는 이제 못 한다
    assert client.post(f"/tasks/{task['id']}/approve", headers=leader).status_code == 403
    assert client.post(f"/tasks/{task['id']}/approve", headers=member).status_code == 200

    # 위임했으니 이제 나갈 수 있다
    assert client.delete(f"/teams/{team['id']}/leave", headers=leader).status_code == 200


def test_last_member_leaving_removes_the_team(client):
    """혼자 남은 리더가 나가면 빈 팀이 남는다 — 아무도 지울 수 없는 팀이 된다."""
    leader = _signup(client, "solo@t.com", "혼자")
    team = client.post("/teams", json={"name": "혼자팀"}, headers=leader).json()
    client.post(f"/teams/{team['id']}/tasks",
                json={"title": "일", "assignee_id": 1, "deadline": "2099-01-01T00:00:00"}, headers=leader)

    assert client.delete(f"/teams/{team['id']}/leave", headers=leader).status_code == 200
    assert client.get("/teams", headers=leader).json() == []
    assert client.get(f"/teams/{team['id']}/dashboard", headers=leader).status_code == 404


def test_transfer_is_leader_only_and_target_must_be_a_member(client):
    leader, member, team = _team_with_member(client)
    outsider = _signup(client, "out@t.com", "외부인")

    assert client.post(f"/teams/{team['id']}/transfer-leader",
                       json={"user_id": 1}, headers=member).status_code == 403
    assert client.post(f"/teams/{team['id']}/transfer-leader",
                       json={"user_id": 999}, headers=leader).status_code == 404
    assert client.post(f"/teams/{team['id']}/transfer-leader",
                       json={"user_id": 1}, headers=outsider).status_code == 403
    # 자기 자신에게 위임하는 건 의미가 없다
    assert client.post(f"/teams/{team['id']}/transfer-leader",
                       json={"user_id": 1}, headers=leader).status_code == 400


def test_member_can_still_leave_freely(client):
    """팀원이 나가는 건 원래대로 막지 않는다."""
    leader, member, team = _team_with_member(client)
    assert client.delete(f"/teams/{team['id']}/leave", headers=member).status_code == 200
    assert _roles(client, team["id"], headers=leader) == {"리더": "leader"}
