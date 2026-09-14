# 팀 프로젝트 데드라인 대시보드 — 설계

## 목적
학교 팀플/사이드 프로젝트에서 각자 할 일과 마감을 한 화면에 모아, 누가 뭘 안 했는지 한눈에 보이게 하는 웹 대시보드. 진행률은 게이지(원형 %)로 표시.

## 범위 (MVP)
- 웹 앱, 로그인/회원가입 기반 (계정 있음)
- 한 사용자가 여러 팀에 동시 소속 가능, 팀 전환 가능
- 역할(팀장/팀원) 구분은 있으나, 할 일 생성·배정은 누구나 가능 (생성 권한 제한 없음)
- 진행률 게이지: 완료율(전체/멤버별) + 마감 임박 경고를 함께 표시
- 마감 D-1 이메일 알림 포함

## 기술 스택
- 백엔드: FastAPI + SQLAlchemy + PostgreSQL
- 프론트: React (Vite)
- 인증: JWT
- 알림: 서버 내장 APScheduler + smtplib (별도 인프라 없이 단일 프로세스)

## 아키텍처 결정
단일 FastAPI 서버 + 단일 React 프론트로 구성하는 모놀리스 방식을 채택. 알림은 별도 워커나 외부 크론 없이 API 프로세스 내 스케줄러가 매일 1회 처리. 실시간(WebSocket) 갱신은 도입하지 않고 대시보드 진입 시 fetch + 60초 폴링으로 대체 — 소규모 팀 인원 규모에서는 체감 차이가 없고, 연결 관리 복잡도를 피할 수 있음. 알림/실시간을 분리하거나 강화하는 것은 이후 확장 시점에 재검토.

## 데이터 모델
```
User         (id, email, password_hash, name)
Team         (id, name, invite_code)
TeamMember   (user_id, team_id, role: leader|member)   # N:M + 역할
Task         (id, team_id, title, assignee_id, deadline,
              done: bool,                              # 로드맵 단계가 없을 때만 직접 토글
              created_by, created_at, notified_at)      # notified_at: D-1 알림 중복 발송 방지용
RoadmapStep  (id, task_id, title, done: bool)           # 할 일 하위 체크리스트, 선택적(0개 이상)
```
- 로드맵 단계는 선택 사항: 있으면 그 단계들의 완료 여부로 진행률을 계산하고, 없으면 Task 자체의 `done`을 하나의 단위로 취급한다.
  - `total_units(task) = len(steps) if steps else 1`
  - `completed_units(task) = sum(step.done) if steps else (1 if task.done else 0)`
- 진행률(팀 전체 / 멤버별) = `completed_units 합 ÷ total_units 합` — 저장하지 않고 조회 시 계산.
- Task에 로드맵 단계가 하나 이상 있으면 모든 단계가 완료됐을 때 자동으로 완료 처리되고, 그 상태에서는 `done`을 직접 토글할 수 없다(단계를 통해서만 변경).
- 마감 임박/초과 여부도 저장값이 아니라 조회 시 `deadline - now`로 계산.

## API 엔드포인트
```
POST /auth/signup, /auth/login              → JWT 발급
GET  /teams                                  # 내가 속한 팀 목록 (팀 전환용)
POST /teams                                  # 팀 생성 (생성자가 leader)
POST /teams/{id}/join  {invite_code}         # 초대코드로 합류
GET  /teams/{id}/dashboard                   # 팀 게이지 + 멤버별 진행률 + task(+로드맵 단계) 목록 한번에
POST /teams/{id}/tasks                       # 할 일 생성(담당자 지정)
PATCH /tasks/{id}                            # 담당자·마감일 수정, (로드맵 단계 없을 때만) done 토글
DELETE /tasks/{id}
POST /tasks/{id}/steps                       # 로드맵 단계 추가 {title}
PATCH /tasks/{id}/steps/{step_id}             # 단계 완료 토글 {done}
```
- `/dashboard`는 프론트 요청 한 번으로 팀 전체 %, 멤버별 %+overdue count, task+로드맵 단계 목록을 모두 집계해 반환.
- 알림은 API로 노출하지 않고 내부 스케줄러가 매일 팀 전체를 훑으며 D-1이고 `notified_at`이 오늘이 아닌 task(완전히 끝나지 않은 것만)에 대해 담당자에게 메일 발송.

## 프론트엔드 화면 구성
```
/login, /signup
/teams              — 내가 속한 팀 목록, 팀 전환 드롭다운, "팀 만들기/합류하기"
/teams/:id          — 메인 대시보드
    ├─ 팀 전체 진행률 게이지 (원형, %)
    ├─ 멤버별 카드 리스트 — 이름, 개인 진행률 게이지, "안 한 일 N개(D-1↓ 빨강)" 배지
    ├─ 할 일 추가 폼 — 제목/담당자/마감일
    └─ Task 목록 — 각 Task 아래 로드맵 단계 체크리스트(단계 추가 입력창 + 체크박스),
                   단계 없는 Task는 자체 완료 체크박스, 마감 임박·초과는 행 색상 강조
```
- 페이지는 로그인/팀목록/대시보드 3개로 한정. task 상세 페이지나 모달 없이 대시보드 내 인라인 처리.
- 갱신: 대시보드 진입 시 fetch + 60초 폴링.

## 제외한 것 (YAGNI)
- 실시간 WebSocket 갱신 — 폴링으로 대체, 팀 규모상 불필요
- 알림 워커 분리(외부 크론) — 단일 프로세스 스케줄러로 충분, 스케일 필요해지면 재검토
- Task 상세 페이지/댓글/첨부파일 — MVP 범위 밖
