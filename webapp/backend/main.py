"""Hades 백엔드 — FastAPI 진입점.

실행:
    cd webapp/backend
    uvicorn main:app --reload --port 18088

프로젝트 루트의 .env 파일을 자동으로 로드한다 (ANTHROPIC_API_KEY,
TTT_ASR_BACKEND, TTT_MODEL_PATH 등). 환경변수가 이미 셸에 있으면
.env 값보다 우선.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# webapp/backend/main.py → 위로 두 단계가 프로젝트 루트
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from routers import catalog, reservation, voice  # noqa: E402  (after load_dotenv)

app = FastAPI(title="Hades — 어르신 음성 체험 예약")

# 개발 중 Vite (5173) → FastAPI (8088) 크로스 오리진 허용
# Vite dev server가 5173 점유 시 5174, 5175... 로 fallback 하므로 정규식으로 허용
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51[0-9]{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(reservation.router)
app.include_router(voice.router)


@app.get("/health")
def health():
    return {"status": "ok"}
