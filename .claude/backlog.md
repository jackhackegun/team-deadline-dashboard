# 개선 백로그

- [x] 1. D-1 이메일 알림 — 설계문서에 명시된 기능(APScheduler 매일 1회 훑어서 마감 D-1인 담당자에게 메일). `requirements.txt`에 `apscheduler`가 이미 있고 `Task.notified_at` 컬럼도 있는데 스케줄러 코드가 없다 · backend/app/ (새 scheduler.py) · 큼
- [x] 2. 대시보드 자동 폴링 — 설계문서 §5.2에 "60초 폴링 갱신"이 명시돼 있는데 지금은 내가 직접 조작할 때만 새로고침된다. 다른 팀원이 바꾼 내용이 안 보인다 · frontend/src/Dashboard.jsx · 작음
- [x] 3. 토큰 만료 시 자동 로그아웃 — 지금은 401을 받아도 대시보드에 에러 문구만 뜨고 로그인 화면으로 안 돌아간다 · frontend/src/api.js, App.jsx · 작음
- [x] 4. 팀 나가기 / 팀 삭제 — 합류·생성만 있고 되돌릴 방법이 없다. 잘못 만든 팀이나 잘못 합류한 팀을 정리할 수 없음 · backend/app/routers/teams.py, frontend/src/Teams.jsx · 보통
- [x] 5. 회원가입 서버 검증 강화 — 이메일 형식만 검사하고 비밀번호 최소 길이 등은 검사하지 않는다 · backend/app/schemas.py · 작음
- [x] 6. task/step 엔드포인트 비회원 차단 테스트 — 현재 팀 대시보드 403은 테스트했지만, task 생성·수정·삭제·step 엔드포인트에 대한 비회원 접근 테스트가 없다 · backend/tests/test_teams.py · 작음
