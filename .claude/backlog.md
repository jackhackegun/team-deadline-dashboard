# 개선 백로그

- [x] 1. D-1 이메일 알림 — 설계문서에 명시된 기능(APScheduler 매일 1회 훑어서 마감 D-1인 담당자에게 메일). `requirements.txt`에 `apscheduler`가 이미 있고 `Task.notified_at` 컬럼도 있는데 스케줄러 코드가 없다 · backend/app/ (새 scheduler.py) · 큼
- [x] 2. 대시보드 자동 폴링 — 설계문서 §5.2에 "60초 폴링 갱신"이 명시돼 있는데 지금은 내가 직접 조작할 때만 새로고침된다. 다른 팀원이 바꾼 내용이 안 보인다 · frontend/src/Dashboard.jsx · 작음
- [x] 3. 토큰 만료 시 자동 로그아웃 — 지금은 401을 받아도 대시보드에 에러 문구만 뜨고 로그인 화면으로 안 돌아간다 · frontend/src/api.js, App.jsx · 작음
- [x] 4. 팀 나가기 / 팀 삭제 — 합류·생성만 있고 되돌릴 방법이 없다. 잘못 만든 팀이나 잘못 합류한 팀을 정리할 수 없음 · backend/app/routers/teams.py, frontend/src/Teams.jsx · 보통
- [x] 5. 회원가입 서버 검증 강화 — 이메일 형식만 검사하고 비밀번호 최소 길이 등은 검사하지 않는다 · backend/app/schemas.py · 작음
- [x] 6. task/step 엔드포인트 비회원 차단 테스트 — 현재 팀 대시보드 403은 테스트했지만, task 생성·수정·삭제·step 엔드포인트에 대한 비회원 접근 테스트가 없다 · backend/tests/test_teams.py · 작음
- [x] 7. 깃허브 연동: org 등록 → 레포 선택 → 커밋을 할 일에 연결(`[#N]` 규칙) → 팀장 승인으로 진행도 상승 · backend/app/github_api.py, routers/{github,tasks}.py, frontend/src/{Github,TaskCard,Dashboard}.jsx · 큼
- [ ] 8. 깃허브 OAuth 로그인 — 지금은 깃허브 아이디를 본인이 타이핑해서 등록한다(오타·사칭 가능). 비공개 org 레포도 서버 전역 `GITHUB_TOKEN` 하나에 의존한다. 깃허브에서 OAuth 앱 등록(Client ID/Secret) 필요 · 설계문서 §5.1 · 큼
- [ ] 9. Alembic 도입 — Postgres로는 전환했으나 스키마는 여전히 `create_all`로 만든다. 운영 중 컬럼 변경이 생기면 수동 작업이 필요하다 · backend/app/main.py · 보통
- [x] 10. 배포 준비 — `JWT_SECRET` 기본값 제거(미설정 시 기동 실패), CORS 화이트리스트, `/healthz`, Postgres, docker-compose 3개 서비스 · 설계문서 §5.6 · 보통
