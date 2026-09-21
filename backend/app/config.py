"""환경설정을 한 곳에서 읽고, 없으면 안 되는 값은 기동 시점에 막는다.

배포에서 가장 흔한 사고가 '개발용 기본값이 그대로 운영에 올라가는 것'이다.
그래서 시크릿류는 기본값을 두지 않고, 없으면 프로세스를 띄우지 않는다.
"""
import os
import sys


class ConfigError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(
            f"환경변수 {name}이(가) 필요합니다. .env를 확인하세요.\n"
            f"  개발용으로 급히 띄우려면: export {name}=$(openssl rand -hex 32)"
        )
    return value


# 개발 편의를 위해 DEV_MODE=1이면 임시 시크릿을 만들어 쓴다.
# 컨테이너·운영에서는 절대 켜지 않는다(기본 꺼짐).
DEV_MODE = os.getenv("DEV_MODE") == "1"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dashboard.db")

if DEV_MODE:
    import secrets
    JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
else:
    JWT_SECRET = _require("JWT_SECRET")

# "http://localhost,https://내도메인" 형식. 브라우저가 이 목록의 출처에서만 API를 부를 수 있다
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if not ALLOWED_ORIGINS:
    if DEV_MODE:
        ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
    else:
        raise ConfigError("ALLOWED_ORIGINS가 필요합니다. 예: ALLOWED_ORIGINS=http://localhost:8080")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_SYNC_MINUTES = int(os.getenv("GITHUB_SYNC_MINUTES", "5"))


def describe() -> str:
    """기동 로그용 한 줄 요약. 시크릿 값 자체는 절대 찍지 않는다."""
    engine = DATABASE_URL.split("://", 1)[0]
    return (f"db={engine} origins={len(ALLOWED_ORIGINS)}개 "
            f"github_token={'설정됨' if GITHUB_TOKEN else '없음'} sync={GITHUB_SYNC_MINUTES}분")


def fail_fast(err: ConfigError) -> None:
    print(f"[설정 오류] {err}", file=sys.stderr)
    raise SystemExit(1)
