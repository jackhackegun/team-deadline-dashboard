# 팀 프로젝트 데드라인 대시보드

학교 팀플/사이드 프로젝트의 할 일과 마감을 한 화면에 모아, 멤버별 진행률(게이지)과 마감 임박 항목을 보여주는 대시보드.

## 문서
- [설계문서](docs/team-deadline-dashboard-design-doc.md)
- [API 명세서](docs/team-deadline-dashboard-api-spec.md)
- [목업](mockup/index.html)

## 배포 (Docker)

```bash
cp .env.example .env
openssl rand -hex 32          # JWT_SECRET에 붙여넣기
openssl rand -hex 24          # POSTGRES_PASSWORD에 붙여넣기
docker compose up -d --build
```

`http://localhost:8080` 에서 뜬다. 구성은 세 컨테이너다.

| 서비스 | 역할 | 포트 |
|---|---|---|
| `web` | nginx — 정적 파일 서빙 + `/api`를 백엔드로 프록시 | 8080 (외부 공개) |
| `api` | FastAPI + 스케줄러 | 내부 전용 |
| `db` | PostgreSQL 16, 볼륨에 영속 | 내부 전용 |

`/api` 프록시로 프론트와 API가 같은 출처가 되므로 브라우저 CORS 문제가 없다.
`api`와 `db`는 포트를 밖으로 열지 않는다 — 외부에서 직접 붙을 수 없다.

시크릿이 비어 있으면 컨테이너가 **뜨지 않는다.** 개발용 기본값이 운영에 올라가는 사고를 막기 위한 것이다.

### 개발용 SQLite 데이터를 배포본으로 옮기기

`dashboard.db`에 있던 계정·팀·할 일을 컨테이너의 Postgres로 옮긴다.
기존 행을 지우지 않고 덧붙이며, 이미 있는 이메일은 건너뛴다.

```bash
docker compose cp backend/dashboard.db api:/tmp/dashboard.db
docker compose cp backend/scripts/migrate_sqlite_to_postgres.py api:/tmp/migrate.py
docker compose exec api python /tmp/migrate.py
```

```bash
docker compose logs -f api     # 로그
docker compose ps              # 상태 (api는 /healthz로 헬스체크)
docker compose down            # 중지 (데이터는 볼륨에 남는다)
docker compose down -v         # 데이터까지 삭제
```

## 실행 (백엔드)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DEV_MODE=1 uvicorn app.main:app --reload
```

`DEV_MODE=1`은 임시 시크릿을 만들어 주는 개발 전용 스위치다. 배포에서는 켜지 않는다.
`http://localhost:8000` 에서 뜬다.

## 실행 (프론트엔드)
```bash
cd frontend
npm install
npm run dev
```
`http://localhost:5173` 에서 뜬다. 백엔드가 먼저 떠 있어야 로그인/회원가입이 동작한다.

## 깃허브 연동

1. **팀장이 오가니제이션을 등록**하고, 그 안에서 이 팀이 쓸 레포를 고른다.
2. **팀원이 일을 끝내고 커밋**한다. 커밋 메시지에 `[#3]`처럼 할 일 번호를 적으면 그 할 일에 붙는다.
   규칙을 깜빡했으면 커밋 해시로 직접 붙일 수 있다.
3. **팀장이 대시보드에서 그 커밋을 확인**한다. 할 일마다 어떤 커밋이 올라왔는지, 누가 올렸는지 보인다.
4. **팀장이 승인을 누르면 진행도가 오른다.** 커밋이 붙었다고 저절로 오르지 않는다.

팀원이 올리는 건 '완료 요청'까지고, 진행도를 움직이는 건 팀장뿐이다.
각자 `깃허브 아이디`를 등록해야 자기 커밋이 자기 것으로 표시된다.

커밋은 5분마다 자동으로 확인하고, '커밋 새로 확인' 버튼으로 즉시 볼 수도 있다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `GITHUB_TOKEN` | 없음 | 비공개 레포 접근·요청 한도 완화용(선택). 없으면 공개 레포만 |
| `GITHUB_SYNC_MINUTES` | `5` | 커밋 확인 주기(분) |
| `GITHUB_COMMIT_LOOKBACK_DAYS` | `30` | 며칠 전 커밋까지 훑을지 |

## 테스트
```bash
cd backend
pytest
```
