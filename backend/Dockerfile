FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 의존성을 먼저 복사해 레이어 캐시를 살린다 — 코드만 고치면 재설치하지 않는다
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# root로 돌리지 않는다
RUN useradd --create-home --shell /usr/sbin/nologin appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# 스케줄러가 프로세스 안에서 돌기 때문에 워커는 1개다.
# 2개 이상이면 D-1 알림과 깃허브 동기화가 중복 실행된다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
