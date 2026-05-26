"""로컬링크 백엔드 — FastAPI (마켓플레이스 + 음성).

실행:
    cd webapp/backend
    uvicorn main:app --reload --port 8088

프로젝트 루트의 .env 파일을 자동으로 로드한다 (ANTHROPIC_API_KEY,
TTT_ASR_BACKEND, TTT_MODEL_PATH 등). 환경변수가 이미 셸에 있으면
.env 값보다 우선.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# listing_ai 이미지 프롬프트 로그를 콘솔에서 확인할 수 있도록 INFO 레벨로 설정
_listing_ai_logger = logging.getLogger("listing_ai")
_listing_ai_logger.setLevel(logging.INFO)
if not _listing_ai_logger.handlers:
    _listing_ai_handler = logging.StreamHandler()
    _listing_ai_handler.setLevel(logging.INFO)
    _listing_ai_handler.setFormatter(
        logging.Formatter("[%(name)s] %(levelname)s - %(message)s")
    )
    _listing_ai_logger.addHandler(_listing_ai_handler)
    _listing_ai_logger.propagate = False  # uvicorn 루트 로거와 중복 출력 방지

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# OPENAI_BASE_URL= 처럼 빈 값이 있으면 SDK 가 잘못된 URL('')을 써 Connection error 발생
if not (os.environ.get("OPENAI_BASE_URL") or "").strip():
    os.environ.pop("OPENAI_BASE_URL", None)

from routers import (  # noqa: E402
    admin,
    assistant,
    auth,
    marketplace,
    orders,
    reviews,
    seller_dashboard,
    voice,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import threading
    from db.bootstrap import init_database
    from routers.reviews import warm_up_kobart

    init_database()
    # KoBART 모델을 서버 시작 시 백그라운드에서 미리 로드 (최초 API 호출 지연 방지)
    t = threading.Thread(target=warm_up_kobart, daemon=True)
    t.start()
    yield


app = FastAPI(title="로컬링크 Local Link — API", lifespan=lifespan)

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

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(marketplace.router)
app.include_router(reviews.router)
app.include_router(seller_dashboard.router)
app.include_router(orders.router)
app.include_router(voice.router)
app.include_router(assistant.router)


@app.get("/health")
def health():
    return {"status": "ok"}
