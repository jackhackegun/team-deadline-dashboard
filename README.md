# 팀 프로젝트 데드라인 대시보드

학교 팀플/사이드 프로젝트의 할 일과 마감을 한 화면에 모아, 멤버별 진행률(게이지)과 마감 임박 항목을 보여주는 대시보드.

## 문서
- [설계문서](docs/team-deadline-dashboard-design-doc.md)
- [API 명세서](docs/team-deadline-dashboard-api-spec.md)
- [목업](mockup/index.html)

## 실행 (백엔드)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
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
