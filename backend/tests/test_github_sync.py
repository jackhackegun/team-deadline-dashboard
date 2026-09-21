"""깃허브 이슈/PR이 진행률을 만드는 경로 검증. 실제 네트워크는 타지 않는다."""
import pytest

from app import github_api
from app.routers import github as github_router
from app.routers import tasks as tasks_router


def _signup(client, email, name="X"):
    r = client.post("/auth/signup", json={"email": email, "password": "secret123", "name": name})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _issue(number, title="일감", state="open", merged=False, is_pr=False):
    item = {"number": number, "title": title, "state": state,
            "html_url": f"https://github.com/o/n/issues/{number}"}
    if is_pr:
        item["pull_request"] = {"merged_at": "2026-09-20T00:00:00Z" if merged else None}
    return item


@pytest.fixture()
def team(client, monkeypatch):
    """레포가 연결된 팀 + 할 일 하나. gh_get은 fake_items가 반환한다."""
    headers = _signup(client, "leader@test.com", "리더")
    t = client.post("/teams", json={"name": "캡스톤"}, headers=headers).json()

    state = {"items": []}

    def fake_gh_get(path, etag=None):
        if path.endswith(f"/repos/o/n"):
            return {"full_name": "o/n"}, None
        if "/issues/" in path:  # 단건 조회 (링크 생성 시)
            number = int(path.rsplit("/", 1)[-1])
            found = next((i for i in state["items"] if i["number"] == number), None)
            if not found:
                raise github_api.GithubError("없음", 404)
            return found, None
        return state["items"], "etag-1"  # 목록 조회 (동기화)

    monkeypatch.setattr(github_api, "gh_get", fake_gh_get)
    monkeypatch.setattr(github_router, "gh_get", fake_gh_get)
    monkeypatch.setattr(tasks_router, "gh_get", fake_gh_get)

    client.put(f"/teams/{t['id']}/github", json={"repo": "o/n"}, headers=headers)
    task = client.post(
        f"/teams/{t['id']}/tasks",
        json={"title": "로그인 구현", "assignee_id": 1, "deadline": "2026-12-01T00:00:00"},
        headers=headers,
    ).json()
    return {"client": client, "headers": headers, "team_id": t["id"], "task_id": task["id"], "state": state}


def test_pr_merge_completes_task(team):
    c, h, state = team["client"], team["headers"], team["state"]
    state["items"] = [_issue(7, "로그인 PR", is_pr=True)]

    linked = c.post(f"/tasks/{team['task_id']}/links", json={"ref": "#7"}, headers=h).json()
    assert [(l["kind"], l["number"], l["state"]) for l in linked["links"]] == [("pr", 7, "open")]
    assert linked["done"] is False

    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["progress_pct"] == 0  # 연결된 PR이 열려 있으면 0%

    # PR이 머지되면 동기화가 할 일을 자동 완료시킨다
    state["items"] = [_issue(7, "로그인 PR", state="closed", merged=True, is_pr=True)]
    assert c.post(f"/teams/{team['team_id']}/github/sync", headers=h).json()["updated"] == 1

    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["progress_pct"] == 100
    task = dash["tasks"][0]
    assert task["done"] is True and task["auto_completed_at"] is not None


def test_partial_progress_across_multiple_links(team):
    c, h, state = team["client"], team["headers"], team["state"]
    state["items"] = [_issue(1, "이슈"), _issue(2, "PR", is_pr=True)]
    c.post(f"/tasks/{team['task_id']}/links", json={"ref": "1"}, headers=h)
    c.post(f"/tasks/{team['task_id']}/links", json={"ref": "https://github.com/o/n/pull/2"}, headers=h)

    state["items"] = [_issue(1, "이슈", state="closed"), _issue(2, "PR", is_pr=True)]
    c.post(f"/teams/{team['team_id']}/github/sync", headers=h)

    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["progress_pct"] == 50  # 둘 중 하나만 닫힘
    assert dash["tasks"][0]["done"] is False


def test_reopened_issue_undoes_auto_completion(team):
    c, h, state = team["client"], team["headers"], team["state"]
    state["items"] = [_issue(3, "버그", state="closed")]
    c.post(f"/tasks/{team['task_id']}/links", json={"ref": "3"}, headers=h)

    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["tasks"][0]["done"] is True  # 연결 시점에 이미 닫혀 있었다

    state["items"] = [_issue(3, "버그", state="open")]
    c.post(f"/teams/{team['team_id']}/github/sync", headers=h)
    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["tasks"][0]["done"] is False and dash["tasks"][0]["auto_completed_at"] is None


def test_manual_override_survives_sync(team):
    """PR은 머지됐지만 사람이 '아직 안 끝났다'고 되돌리면 동기화가 다시 덮어쓰지 않는다."""
    c, h, state = team["client"], team["headers"], team["state"]
    state["items"] = [_issue(9, "PR", state="closed", merged=True, is_pr=True)]
    linked = c.post(f"/tasks/{team['task_id']}/links", json={"ref": "9"}, headers=h).json()
    assert linked["done"] is True

    reverted = c.patch(f"/tasks/{team['task_id']}", json={"done": False}, headers=h).json()
    assert reverted["done"] is False and reverted["done_override"] is True

    c.post(f"/teams/{team['team_id']}/github/sync", headers=h)
    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["tasks"][0]["done"] is False  # 사람의 판단이 이긴다
    assert dash["progress_pct"] == 0


def test_link_validation_and_permissions(client, team):
    c, h = team["client"], team["headers"]
    team["state"]["items"] = [_issue(5)]

    assert c.post(f"/tasks/{team['task_id']}/links", json={"ref": "abc"}, headers=h).status_code == 400
    assert c.post(f"/tasks/{team['task_id']}/links", json={"ref": "404"}, headers=h).status_code == 404

    c.post(f"/tasks/{team['task_id']}/links", json={"ref": "5"}, headers=h)
    dup = c.post(f"/tasks/{team['task_id']}/links", json={"ref": "5"}, headers=h)
    assert dup.status_code == 400  # 같은 번호 중복 연결 금지

    outsider = _signup(c, "outsider@test.com", "외부인")
    assert c.post(f"/tasks/{team['task_id']}/links", json={"ref": "6"}, headers=outsider).status_code == 403

    link_id = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()["tasks"][0]["links"][0]["id"]
    assert c.delete(f"/tasks/{team['task_id']}/links/{link_id}", headers=outsider).status_code == 403
    assert c.delete(f"/tasks/{team['task_id']}/links/{link_id}", headers=h).json()["links"] == []


def test_sync_survives_unchanged_repo_and_failures(team, monkeypatch):
    """304(안 바뀜)는 조용히 넘어가고, 깃허브 장애는 에러 메시지로 남아 대시보드에 보인다."""
    c, h, state = team["client"], team["headers"], team["state"]
    state["items"] = [_issue(4)]
    c.post(f"/tasks/{team['task_id']}/links", json={"ref": "4"}, headers=h)

    monkeypatch.setattr(github_api, "gh_get", lambda path, etag=None: (None, etag))
    assert c.post(f"/teams/{team['team_id']}/github/sync", headers=h).json()["skipped"] is True

    def boom(path, etag=None):
        raise github_api.GithubError("GitHub에 연결할 수 없습니다(네트워크 확인).")

    monkeypatch.setattr(github_api, "gh_get", boom)
    assert c.post(f"/teams/{team['team_id']}/github/sync", headers=h).status_code == 502

    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert "연결할 수 없습니다" in dash["github_last_error"]
    assert dash["tasks"][0]["links"][0]["state"] == "open"  # 장애가 데이터를 망가뜨리지 않는다


def test_steps_still_work_without_links(team):
    """기존 동작 보존 — 링크가 없으면 진행률은 예전처럼 로드맵 단계 기준."""
    c, h = team["client"], team["headers"]
    c.post(f"/tasks/{team['task_id']}/steps", json={"title": "설계"}, headers=h)
    stepped = c.post(f"/tasks/{team['task_id']}/steps", json={"title": "구현"}, headers=h).json()
    step_id = stepped["steps"][0]["id"]

    c.patch(f"/tasks/{team['task_id']}/steps/{step_id}", json={"done": True}, headers=h)
    dash = c.get(f"/teams/{team['team_id']}/dashboard", headers=h).json()
    assert dash["progress_pct"] == 50
