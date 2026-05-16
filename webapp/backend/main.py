"""로컬링크 백엔드 — FastAPI (마켓플레이스 + 음성).

실행:
    cd webapp/backend
    uvicorn main:app --reload --port 8088

프로젝트 루트의 .env 파일을 자동으로 로드한다 (ANTHROPIC_API_KEY,
TTT_ASR_BACKEND, TTT_MODEL_PATH 등). 환경변수가 이미 셸에 있으면
.env 값보다 우선.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from routers import marketplace, orders, voice  # noqa: E402

app = FastAPI(title="로컬링크 Local Link — API")

_default_cors = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
_extra = os.environ.get("CORS_EXTRA_ORIGINS", "")
_origins = [
    *_default_cors,
    *[o.strip() for o in _extra.split(",") if o.strip()],
]

# Vite dev server가 5173 점유 시 5174, 5175… 로 내려가므로 정규식으로 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51[0-9]{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marketplace.router)
app.include_router(orders.router)
app.include_router(voice.router)


@app.get("/health")
def health():
    return {"status": "ok"}
