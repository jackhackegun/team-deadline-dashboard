# 팀 프로젝트 데드라인 대시보드 — API 명세서

설계문서(`team-deadline-dashboard-design-doc.md`) 6장 API 명세를 요청/응답 스키마 수준으로 구체화한 문서.

## 공통 사항

- Base URL: `http://localhost:8000` (배포 시 도메인으로 대체)
- 인증: `POST /auth/signup`, `/auth/login` 을 제외한 모든 엔드포인트는 `Authorization: Bearer <JWT>` 헤더 필요. 토큰 만료 7일.
- Content-Type: `application/json`
- 에러 응답 공통 포맷 (FastAPI 기본):
  ```json
  { "detail": "에러 메시지" }
  ```
- 날짜/시간: ISO 8601 (`2026-09-10T00:00:00`), UTC 기준.
- 진행률(`progress_pct`)은 반올림한 정수(0~100).
- **구현 상태**: 인증(`/auth/*`)만 구현 완료. 팀/할 일/대시보드는 본 명세대로 설계됨(미구현).

---

## 1. 인증

### POST `/auth/signup` — 회원가입
인증 불필요.

Request body:
```json
{ "email": "user@test.com", "password": "secret123", "name": "홍길동" }
```

Response `200`:
```json
{ "access_token": "<JWT>", "token_type": "bearer" }
```

에러: `400` 이메일 중복 (`"Email already registered"`)

### POST `/auth/login` — 로그인
인증 불필요.

Request body:
```json
{ "email": "user@test.com", "password": "secret123" }
```

Response `200`: signup과 동일한 `TokenResponse`

에러: `401` 이메일/비밀번호 불일치 (`"Invalid credentials"`)

---

## 2. 팀

### GET `/teams` — 내가 속한 팀 목록

Response `200`:
```json
[
  { "id": 1, "name": "캡스톤", "invite_code": "a1b2c3d4", "role": "leader" }
]
```

### POST `/teams` — 팀 생성 (생성자 = leader)

Request body:
```json
{ "name": "캡스톤" }
```

Response `200`: `TeamOut` (위와 동일 형태, `role: "leader"`). `invite_code`는 서버가 생성.

### POST `/teams/{team_id}/join` — 초대코드로 팀 합류

Request body:
```json
{ "invite_code": "a1b2c3d4" }
```

Response `200`: `TeamOut` (`role: "member"`)

에러: `404` 팀 없음/코드 불일치, `400` 이미 소속된 팀 (`"Already member"`)

---

## 3. 대시보드

### GET `/teams/{team_id}/dashboard` — 팀 게이지 + 멤버별 진행률 + task 목록 일괄 조회

Response `200`:
```json
{
  "team_id": 1,
  "team_name": "캡스톤",
  "progress_pct": 67,
  "members": [
    { "user_id": 1, "name": "홍길동", "role": "leader", "progress_pct": 50, "overdue_count": 1 }
  ],
  "tasks": [
    {
      "id": 1, "team_id": 1, "title": "발표자료 준비", "assignee_id": 1,
      "deadline": "2026-09-10T00:00:00", "done": false, "created_by": 1,
      "steps": [{ "id": 1, "title": "자료조사", "done": true }]
    }
  ]
}
```

집계 규칙: Task에 로드맵 단계가 있으면 (완료 단계 수 ÷ 전체 단계 수), 없으면 `done` 자체가 1단위. `overdue_count`는 해당 멤버가 담당한, 아직 끝나지 않았고 마감이 지난 Task 수.

에러: `404` 팀 없음, `403` 팀원이 아님 (`"Not a team member"`)

---

## 4. 할 일 (Task)

### POST `/teams/{team_id}/tasks` — 할 일 생성

Request body:
```json
{ "title": "회의록 정리", "assignee_id": 1, "deadline": "2026-09-12T00:00:00" }
```

Response `200`: `TaskOut` (`done: false`, `steps: []`)

에러: `403` 팀원이 아님

### PATCH `/tasks/{task_id}` — 담당자·마감일 수정, (로드맵 단계 없을 때만) done 토글

Request body (모든 필드 선택):
```json
{ "title": "회의록 정리", "assignee_id": 2, "deadline": "2026-09-13T00:00:00", "done": true }
```

Response `200`: `TaskOut`

에러: `403` 팀원이 아님, `400` 로드맵 단계가 있는 Task의 `done`을 직접 토글 시도

### DELETE `/tasks/{task_id}` — 할 일 삭제
연결된 RoadmapStep도 함께 삭제(cascade).

Response `200`: 빈 본문

에러: `403` 팀원이 아님, `404` Task 없음

### POST `/tasks/{task_id}/steps` — 로드맵 단계 추가

Request body:
```json
{ "title": "디자인" }
```

Response `200`: `TaskOut` (갱신된 `steps` 포함). 새 단계 추가 시 Task의 `done`은 `false`로 리셋.

### PATCH `/tasks/{task_id}/steps/{step_id}` — 로드맵 단계 완료 토글

Request body:
```json
{ "done": true }
```

Response `200`: `TaskOut`. 모든 단계가 완료되면 Task의 `done`이 자동으로 `true`가 됨.

에러: `404` Step 없음

---

## 5. 스키마 요약

| 스키마 | 필드 |
|--------|------|
| `TokenResponse` | access_token: str, token_type: str = "bearer" |
| `TeamOut` | id, name, invite_code, role |
| `MemberProgress` | user_id, name, role, progress_pct, overdue_count |
| `TaskOut` | id, team_id, title, assignee_id, deadline, done, created_by, steps: StepOut[] |
| `StepOut` | id, title, done |
| `DashboardOut` | team_id, team_name, progress_pct, members: MemberProgress[], tasks: TaskOut[] |

## 6. 노출하지 않는 기능

D-1 이메일 알림은 API 엔드포인트가 없음 — 서버 내부 APScheduler가 매일 1회 전체 Task를 훑어 처리.
