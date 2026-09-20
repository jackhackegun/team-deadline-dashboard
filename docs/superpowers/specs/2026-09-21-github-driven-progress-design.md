# 깃허브 연동 기반 진행상태 자동화 설계

**작성일:** 2026-09-21
**전제 문서:** `docs/team-deadline-dashboard-design-doc.md`, `docs/team-deadline-dashboard-api-spec.md`

## 1. 목표

대시보드의 진행률을 **깃허브의 실제 코드 활동에서 끌어온다.** 지금은 사람이 체크박스를 눌러야만 진행률이 움직인다. 앞으로는 연결된 이슈가 닫히고 PR이 머지되면 할 일이 저절로 완료되고, 팀은 체크를 누르는 대신 코드를 밀면 된다. 수동 체크는 없애지 않고 최종 판단 수단으로 남긴다.

동시에 지금의 개발용 구성(SQLite 파일, 하드코딩된 시크릿 기본값, 배포 수단 없음)을 한 팀이 서버에 올려놓고 상시 사용할 수 있는 수준으로 올린다.

## 2. 현재 한계

1. **진행률과 실제 진척의 괴리.** 체크를 안 하면 일이 끝나도 0%, 누르기만 하면 아무것도 안 해도 100%다.
2. **깃허브 연동이 읽기 전용 장식이다.** 팀 레포의 최근 커밋·PR 8건을 보여줄 뿐, 할 일과 아무 관계가 없다.
3. **커밋 작성자와 팀 멤버가 이어지지 않는다.** 로그인은 이메일/비밀번호뿐이라 `author.login`을 대시보드의 누구인지 알 수 없다.
4. **비공개 레포를 못 읽는다.** 서버 전역 `GITHUB_TOKEN` 하나에 의존한다.
5. **운영 공백.** `main.py`가 `PRAGMA`로 컬럼을 덧붙이는 임시 마이그레이션, `JWT_SECRET` 기본값 `dev-secret-change-me`, CORS 와일드카드, 전역 에러 핸들러·헬스체크·배포 스크립트 없음.

## 3. 범위 밖 (의도적 제외)

- **역방향 동기화** (대시보드에서 체크 → 깃허브 이슈 닫기). 동기화 루프와 "어느 쪽이 진실인가" 문제를 부른다. 깃허브 → 대시보드 단방향만 한다.
- **웹훅.** 폴링으로 시작한다(§5.3). 동기화 본체를 함수로 분리해 나중에 웹훅 엔드포인트가 같은 함수를 부르도록 자리만 만들어 둔다.
- **GitHub App 설치 흐름.** OAuth App으로 충분하다(§5.1).
- **커밋 메시지 자동 파싱**(`#task-12` 같은 규칙으로 링크 자동 생성). 할 일 ↔ 이슈/PR 연결은 수동으로만 만든다.
- **외부 공개 가입에 필요한 것들** — 이메일 인증, 비밀번호 재설정, 약관·개인정보 처리, 레이트 리밋, 결제. "내 팀이 쓴다"가 기준이다.

## 4. 데이터 흐름

```
GitHub 레포
   │  (5분 폴링, ETag 조건부 요청)
   ▼
sync_repo(db, team)  ── 이슈/PR 상태를 TaskLink에 반영
   │
   ▼
Task.done 자동 갱신 (연결된 링크가 전부 종료되면)
   │
   ▼
GET /teams/{id}/dashboard  ── 조회 시점 집계
   │
   ▼
프론트 60초 폴링
```

## 5. 설계

### 5.1 깃허브 아이덴티티 — OAuth App

GitHub App이 아니라 **OAuth App**을 쓴다. 로그인과 레포 접근을 토큰 하나로 해결해서 설치 흐름·앱 JWT 서명·1시간 토큰 갱신이 전부 필요 없다. 대신 사용자 토큰은 그 사람의 레포 전체에 접근할 수 있는 과한 권한이므로, 암호화해서 저장하고(§5.6) 스코프를 환경변수로 낮출 수 있게 한다.

**흐름**

- `GET /auth/github` — `state`(서명된 난수, 10분 만료)를 담아 GitHub authorize로 리다이렉트
- `GET /auth/github/callback` — `state` 검증 → `code`를 access token으로 교환 → `GET /user`, `GET /user/emails`로 신원 확인 → 사용자 생성 또는 기존 계정 연결 → 우리 JWT 발급 → 프론트로 리다이렉트(토큰은 URL 프래그먼트)

**계정 연결 규칙**

- `github_id`가 이미 있으면 그 사용자로 로그인
- 없고 깃허브의 **검증된(verified) 기본 이메일**이 기존 사용자와 일치하면 그 계정에 연결
- 둘 다 아니면 새 사용자 생성 (`password_hash`는 비워둠 → 비밀번호 로그인 불가)

검증되지 않은 이메일로는 절대 기존 계정에 연결하지 않는다. 남의 이메일을 깃허브 프로필에 적어두고 계정을 가져가는 경로가 된다.

**기존 이메일/비밀번호 로그인은 그대로 유지한다.** 깃허브 계정이 없는 팀원도 쓸 수 있어야 한다. 이미 로그인한 사용자가 `/auth/github`를 타면 새 계정을 만드는 대신 현재 계정에 깃허브를 연결한다.

**`User` 신규 컬럼**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `github_id` | Integer, unique, nullable | 깃허브 수치 ID (login은 바뀔 수 있으므로 이걸 키로 쓴다) |
| `github_login` | String, nullable | 커밋 author 매칭용 |
| `github_token_enc` | String, nullable | 암호화된 사용자 access token |
| `github_connected_at` | DateTime, nullable | |

`password_hash`는 nullable로 바꾼다 (깃허브로만 가입한 사용자).

### 5.2 할 일 ↔ 이슈/PR 연결

**신규 테이블 `task_links`**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | Integer PK | |
| `task_id` | FK → tasks.id, cascade delete | |
| `kind` | Enum(`issue`, `pr`) | |
| `number` | Integer | 레포 내 번호 |
| `title` | String, nullable | 동기화 시 캐시 |
| `state` | Enum(`open`, `closed`, `merged`) | `merged`는 PR 전용 |
| `url` | String, nullable | |
| `last_synced_at` | DateTime, nullable | |

`UNIQUE(task_id, kind, number)`.

할 일 하나에 링크 여러 개를 허용한다 — 이슈 하나가 PR 두세 개로 갈라지는 건 흔하다. `Task`에 컬럼 두 개를 박는 대신 테이블을 따로 두는 이유다.

**엔드포인트**

- `POST /tasks/{task_id}/links` — `{"ref": "123"}` 또는 `{"ref": "https://github.com/owner/name/pull/123"}`. 번호를 팀 레포에서 조회해 종류(issue/pr)·제목·상태를 채운다. 팀에 레포가 연결돼 있지 않으면 400.
- `DELETE /tasks/{task_id}/links/{link_id}`

### 5.3 동기화 — 폴링

이미 D-1 알림 때문에 떠 있는 APScheduler에 job 하나를 더 얹는다. **공개 URL이 필요 없다**는 게 웹훅 대신 폴링을 고르는 이유다 — 사내망이든 노트북이든 올린 자리에서 그대로 돈다.

- 주기: `GITHUB_SYNC_MINUTES` (기본 5분)
- 대상: `github_repo`가 연결된 팀
- 요청: `GET /repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=100`
  - 깃허브 issues API는 PR도 함께 반환하고, PR이면 `pull_request.merged_at`이 들어 있다. **요청 한 번으로 이슈와 PR 상태를 모두 얻는다.**
  - `Team.github_etag`를 `If-None-Match`로 보내고 304면 즉시 스킵
- 반영: 응답에 들어 있는 번호 중 `task_links`에 등록된 것만 `state`/`title` 갱신. 목록에 없는 링크는 그 사이 바뀐 게 없다는 뜻이므로 건드리지 않는다.

**토큰 선택 순서:** 레포를 연결한 사람(`Team.github_connected_by`)의 토큰 → 실패하면 깃허브를 연결한 다른 팀 멤버의 토큰 → 없으면 익명 요청(공개 레포만).

레포를 연결한 사람이 팀을 떠나거나 토큰을 회수해도 동기화가 죽지 않게 하는 장치다.

**실패 처리:** 팀 단위로 예외를 격리해 한 팀의 레포 문제가 다른 팀 동기화를 막지 않는다. 결과를 `Team.github_last_sync_at` / `github_last_error`에 기록하고 대시보드 응답에 실어 보낸다 — 조용히 멈춘 동기화가 제일 나쁘다. 403/429(레이트 리밋)를 받으면 해당 팀을 다음 주기 하나 건너뛴다.

**확장 지점:** 동기화 본체는 `sync_repo(db, team) -> SyncResult` 하나로 두고, 스케줄러는 이 함수를 팀마다 부르기만 한다. 나중에 실시간이 필요해지면 `POST /webhooks/github`가 같은 함수를 부르면 된다.

### 5.4 진행률 재정의

`task_units(task)`의 우선순위를 다음으로 바꾼다.

1. `done_override`가 켜져 있으면 → `task.done` 그대로 (사람의 판단이 최우선)
2. 링크가 있으면 → 종료된 링크 / 전체 링크 (PR은 `merged`, 이슈는 `closed`가 종료)
3. 링크는 없고 로드맵 단계가 있으면 → 기존대로 완료 단계 비율
4. 둘 다 없으면 → `task.done` (0 또는 1)

**자동 완료:** 동기화 후 연결된 링크가 전부 종료 상태면 `task.done = True`, `auto_completed_at` 기록.

**되돌리기:** 사용자가 자동 완료된 할 일을 다시 미완료로 바꾸면 `done_override = True`를 세우고, 이후 동기화는 그 할 일의 `done`을 건드리지 않는다. PR은 머지됐지만 실제로는 덜 끝난 경우가 있고, 그때 시스템이 사람을 이기면 안 된다.

**`Task` 신규 컬럼:** `auto_completed_at`(DateTime, nullable), `done_override`(Boolean, 기본 False).

기존 할 일은 링크가 없으므로 3·4번 경로를 그대로 탄다 — **동작이 바뀌지 않는다.**

### 5.5 멤버 ↔ 깃허브 계정 매칭

커밋·PR의 `author.login`을 `User.github_login`과 대조해 멤버별 최근 활동(커밋 수, 열린 PR 수)을 대시보드 멤버 카드에 붙인다. 매칭되는 계정이 없으면 "깃허브 미연결"로 표시하고, 그 사람에게 연결을 유도한다.

### 5.6 운영 기반

**설정 (`app/config.py` 신규).** 환경변수를 한 곳에서 읽고 필수값을 기동 시점에 검증한다. `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `DATABASE_URL`, `ALLOWED_ORIGINS`가 없으면 **프로세스를 띄우지 않는다.** 지금의 `dev-secret-change-me` 기본값은 제거한다 — 기본값이 있으면 언젠가 그대로 배포된다.

**토큰 암호화.** 깃허브 access token은 `cryptography`의 Fernet으로 암호화해 저장한다. DB가 유출돼도 토큰 자체는 쓸 수 없어야 한다. 키는 `TOKEN_ENCRYPTION_KEY`. (신규 의존성 1개 — 직접 구현할 종류의 코드가 아니다.)

**데이터베이스.** Postgres로 전환하고 Alembic을 도입한다. `main.py`의 `PRAGMA table_info` + `ALTER TABLE` 블록을 삭제하고 초기 마이그레이션에 현재 스키마를 담는다. 테스트는 계속 인메모리 SQLite를 쓴다.

**CORS.** `allow_origin_regex=r"http://[\w.\-]+:5173"`를 `ALLOWED_ORIGINS` 환경변수 목록으로 교체한다.

**에러·로깅.** 요청 ID 미들웨어, 전역 예외 핸들러(스택 트레이스를 응답 본문에 싣지 않고 로그로만), 깃허브 호출 실패·동기화 결과에 대한 구조화 로그.

**헬스체크.** `GET /healthz` — DB에 `SELECT 1`. 컨테이너 재시작 판단용.

**배포.** `docker-compose.yml` — `api`(uvicorn), `db`(postgres, 볼륨), `web`(프론트 빌드 산출물을 nginx로 정적 서빙). `.env.example`에 필요한 변수를 전부 적는다. `docker compose up -d`로 끝난다.

**스케줄러 중복.** APScheduler가 API 프로세스 안에서 도는 구조라 인스턴스를 2개 이상 띄우면 알림과 동기화가 중복된다. 컨테이너 1개를 전제로 하고, 이 제약을 코드 주석과 README에 명시한다.

### 5.7 프론트엔드

- 로그인 화면에 **"GitHub으로 계속하기"** 버튼, 콜백 토큰 수신 처리
- 할 일 카드에서 이슈/PR 연결·해제, 링크 상태를 배지로 표시(open/closed/merged)
- 자동 완료된 할 일에 표시와 되돌리기 버튼
- 대시보드 헤더에 마지막 동기화 시각, 실패 시 사유
- 멤버 카드에 깃허브 활동, 미연결 멤버 안내

## 6. 테스트

깃허브 API는 전부 모킹한다(실제 네트워크 호출 없음).

- OAuth 콜백: 신규 가입 / 기존 계정 연결 / **검증되지 않은 이메일은 연결 거부** / `state` 위조 거부
- `sync_repo`: 이슈 닫힘·PR 머지가 링크 상태에 반영되는지, 전부 종료되면 자동 완료되는지
- `done_override`가 켜진 할 일은 동기화가 덮어쓰지 않는지
- 진행률 우선순위 4가지 경로
- 토큰 암호화 왕복, 그리고 평문이 DB에 남지 않는지
- 권한: 비회원이 링크를 만들거나 지울 수 없는지
- 한 팀의 깃허브 실패가 다른 팀 동기화를 막지 않는지
- 프론트: 진행률 계산(`dashboardMath.js`) 단위 테스트 — 현재 0개다

## 7. 구현 단계

| 단계 | 내용 | 비고 |
|---|---|---|
| 1 | 설정 일원화, Alembic + Postgres, 헬스체크, 로깅·에러 핸들러 | 이후 전부의 토대 |
| 2 | 깃허브 OAuth 로그인, 토큰 암호화 저장 | |
| 3 | `task_links`, 링크 API, `sync_repo`, 진행률 재정의, 자동 완료 | 핵심 |
| 4 | 프론트 — 깃허브 로그인, 링크 UI, 동기화 상태, 멤버 활동 | |
| 5 | Docker Compose, `.env.example`, 배포 문서 | |

각 단계는 그 자체로 동작하는 상태로 끝난다. 3단계까지만 해도 서비스는 돌아간다.

## 8. 기존 사용자 영향

- 이메일/비밀번호 로그인, 기존 할 일, 로드맵 단계, D-1 알림 — 전부 그대로 동작한다.
- 링크가 없는 할 일의 진행률 계산은 바뀌지 않는다.
- 깃허브를 연결하지 않은 팀도 지금과 똑같이 쓴다.
- 배포 담당자는 **환경변수를 채워야 한다** (§5.6). 안 채우면 기동하지 않는다. 이건 의도된 동작이다.
