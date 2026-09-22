"""깃허브 요청 한도를 아끼는 장치들. 한도(토큰 없으면 시간당 60회)는 금방 바닥난다."""
import time
from datetime import datetime, timedelta
from email.message import Message

import pytest

from app import github_api


def _headers(**kv):
    m = Message()
    for k, v in kv.items():
        m[k.replace("_", "-")] = str(v)
    return m


def test_since_is_stable_within_a_day():
    """URL이 매초 바뀌면 ETag가 무효가 되어 바뀐 게 없어도 한도를 깎는다."""
    first = github_api._since_day()
    time.sleep(1.1)
    assert github_api._since_day() == first
    assert first.endswith("T00:00:00Z")


def test_since_still_covers_the_lookback_window():
    since = datetime.strptime(github_api._since_day(), "%Y-%m-%dT%H:%M:%SZ")
    age_days = (datetime.utcnow() - since).days
    assert github_api.COMMIT_LOOKBACK_DAYS <= age_days <= github_api.COMMIT_LOOKBACK_DAYS + 1


def test_rate_limit_message_says_when_it_recovers():
    reset = int(time.time()) + 9 * 60
    msg = github_api._rate_limit_message(
        _headers(X_RateLimit_Remaining=0, X_RateLimit_Limit=60, X_RateLimit_Reset=reset))
    assert "한도" in msg and "60회" in msg and "분 뒤" in msg


def test_permission_error_is_not_reported_as_rate_limit():
    """한도가 남아 있는데 거부당한 건 권한 문제다 — 다른 안내를 해야 한다."""
    assert github_api._rate_limit_message(_headers(X_RateLimit_Remaining=42)) is None


def test_commit_list_is_cached_to_save_quota(monkeypatch):
    """팀원 여러 명이 '커밋 붙이기'를 열어도 요청이 한 번만 나가야 한다."""
    calls = []

    def fake_gh_get(path, etag=None):
        calls.append(path)
        return [{
            "sha": "a" * 40, "html_url": "u",
            "author": {"login": "kim"},
            "commit": {"message": "m", "author": {"name": "김", "date": "2026-09-20T10:00:00Z"}},
        }], None

    monkeypatch.setattr(github_api, "gh_get", fake_gh_get)

    class FakeTeam:
        id = 1
        repos = [type("R", (), {"full_name": "acme/api"})()]

    github_api.invalidate_commit_cache(1)
    team = FakeTeam()
    assert len(github_api.recent_commits(team)) == 1
    github_api.recent_commits(team)
    github_api.recent_commits(team)
    assert len(calls) == 1, f"캐시가 안 먹었다: {len(calls)}회 호출"

    # 레포 선택이 바뀌면 다시 가져와야 한다
    github_api.invalidate_commit_cache(1)
    github_api.recent_commits(team)
    assert len(calls) == 2
