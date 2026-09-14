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

## 테스트
```bash
cd backend
pytest
```
