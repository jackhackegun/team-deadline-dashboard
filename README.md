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

팀 대시보드 하단에서 레포(`owner/name`)를 연결하고, 할 일 카드에서 이슈/PR 번호를 연결하면
**깃허브 상태가 진행률을 만든다.** 연결된 이슈가 닫히고 PR이 머지되면 할 일이 자동 완료된다.
자동 완료가 틀렸으면 '완료 해제'로 되돌릴 수 있고, 이후 동기화는 그 할 일을 건드리지 않는다.

동기화는 5분마다 자동으로 돌고, '지금 동기화' 버튼으로 즉시 돌릴 수도 있다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `GITHUB_TOKEN` | 없음 | 비공개 레포 접근·요청 한도 완화용(선택). 없으면 공개 레포만 |
| `GITHUB_SYNC_MINUTES` | `5` | 동기화 주기(분) |

## 테스트
```bash
cd backend
pytest
```
