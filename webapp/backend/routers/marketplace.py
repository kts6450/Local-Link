"""마켓플레이스 — 브랜드, 상품·숙박 목록, 판매자 등록."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from routers.auth import get_current_user
from services.listing_events import get_listings_version
from services.listing_ai import (
    enhance_image_prompt,
    generate_listing_cover_png,
    generate_listing_description,
    image_models_to_try,
    is_openai_configured,
)
from services.listing_package import generate_listing_package
from services.note_ocr import parse_note_images
from services.listing_photos import (
    add_photo,
    delete_photo,
    get_photo_listing_id,
    list_photos,
    photo_file_path,
)
from services.listings_store import (
    cover_file_path,
    create_listing,
    delete_listing,
    get_listing,
    list_best_listings,
    list_listings,
)
from services.llm import is_configured as anthropic_configured
from services.seller_extras import (
    agent_suggestions,
    alimtalk_draft,
    generate_sns_draft,
    tourism_tips,
    weather_season_tips,
)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

_BRAND_PATH = Path(__file__).resolve().parent.parent / "data" / "brand.json"


@router.get("/brand")
def brand():
    with open(_BRAND_PATH, encoding="utf-8") as f:
        return json.load(f)


@router.get("/listings")
def get_listings(kind: str | None = None):
    items = list_listings()
    if kind in ("product", "lodging"):
        items = [x for x in items if x.get("kind") == kind]
    return items


@router.get("/best-listings")
def get_best_listings(limit: int = 12):
    """리뷰 평점·건수 기반 베스트 상품·숙박·체험."""
    return {"items": list_best_listings(limit=max(1, min(int(limit), 24)))}


@router.get("/listings/events")
async def listings_events():
    """목록 변경 시 SSE — 소비자·공급자 화면 실시간 갱신."""

    async def event_gen():
        last = get_listings_version()
        yield f"data: {json.dumps({'type': 'hello', 'v': last})}\n\n"
        while True:
            await asyncio.sleep(0.35)
            cur = get_listings_version()
            if cur != last:
                last = cur
                yield f"data: {json.dumps({'type': 'listings', 'v': cur})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/listings/{listing_id}")
def get_one(listing_id: str):
    e = get_listing(listing_id)
    if e is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return e


@router.get("/listings/{listing_id}/local-guide")
def get_listing_local_guide(listing_id: str):
    """소비자 상세 — 지역 관광·시즌 안내 (쇼핑몰 «이용 안내» 탭)."""
    e = get_listing(listing_id)
    if e is None:
        raise HTTPException(status_code=404, detail="listing not found")
    loc = e.get("location") or ""
    title = e.get("title") or ""
    stored = e.get("guide") if isinstance(e.get("guide"), dict) else None
    tourism = tourism_tips(loc, title, use_llm=False)
    if stored and stored.get("nearby"):
        tourism = {
            **tourism,
            "location": loc,
            "highlights": stored.get("highlights") or tourism.get("highlights", []),
            "nearby_spots": stored.get("nearby"),
            "seller_tip": stored.get("meeting_place") or tourism.get("seller_tip", ""),
        }
    return {
        "listing_id": listing_id,
        "tourism": tourism,
        "weather": weather_season_tips(loc),
        "guide": stored,
    }


@router.get("/features")
def feature_flags():
    """과금·외부 API 연동 기능 — 일부는 키가 있으면 활성화."""
    claude = anthropic_configured()
    openai_ok = is_openai_configured()
    return {
        "items": [
            {
                "id": "ai_copywriting",
                "enabled": True,
                "label": "AI 설명·대표 이미지 초안",
                "message": (
                    "판매자 화면에서 설명·이미지를 자동 생성할 수 있습니다. "
                    + (
                        "Claude·OpenAI 키를 넣으면 품질이 좋아집니다."
                        if not (claude and openai_ok)
                        else "Claude·OpenAI 키가 설정되어 있습니다."
                    )
                ),
            },
            {
                "id": "sns_marketing",
                "enabled": True,
                "label": "SNS·키워드 자동 초안",
                "message": "인스타·페이스북 문구와 해시태그를 자동 작성합니다.",
            },
            {
                "id": "tourism_api",
                "enabled": True,
                "label": "관광·지역 정보 연동",
                "message": "지역명 기준 관광·판매 팁을 제안합니다.",
            },
            {
                "id": "weather_api",
                "enabled": True,
                "label": "기상청 날씨·시즌 안내",
                "message": "현재 시즌·지역별 판매·홍보 시기를 안내합니다.",
            },
            {
                "id": "alimtalk",
                "enabled": True,
                "label": "알림톡·메시지 발송",
                "message": "주문·배송 알림 문구 초안을 만듭니다. (실발송 연동은 별도)",
            },
            {
                "id": "real_payment",
                "enabled": True,
                "label": "실결제(카드·간편결제)",
                "message": "결제 화면에서 카드·간편결제 시연 API를 사용합니다. 실제 청구 없음.",
            },
            {
                "id": "agent_automation",
                "enabled": True,
                "label": "재고·행사 연동 자동 제안(에이전트)",
                "message": "등록 상품·재고·시즌 기준 운영 제안을 표시합니다.",
            },
        ]
    }


@router.get("/ai/capabilities")
def ai_capabilities():
    """프론트에서 AI 버튼 노출 여부."""
    return {
        "description_ai": True,
        "description_claude": anthropic_configured(),
        "image_openai": is_openai_configured(),
        "image_models": image_models_to_try() if is_openai_configured() else [],
        "package_ai": True,
        "package_claude": anthropic_configured(),
    }


class DraftDescriptionBody(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=200)
    price: int = Field(ge=0, le=100_000_000)
    location: str = Field(default="", max_length=500)

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in ("product", "lodging"):
            raise ValueError("kind must be product or lodging")
        return v


class DraftPackageBody(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=200)
    price: int = Field(ge=0, le=100_000_000)
    location: str = Field(default="", max_length=500)
    category: str = Field(default="rural", max_length=24)

    @field_validator("kind")
    @classmethod
    def _kind_ok_pkg(cls, v: str) -> str:
        if v not in ("product", "lodging"):
            raise ValueError("kind must be product or lodging")
        return v


class DraftImageBody(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=500)
    category: str = Field(default="rural", max_length=24)
    description: str = Field(default="", max_length=4000)
    prompt_en: str | None = Field(default=None, max_length=4000)

    @field_validator("kind")
    @classmethod
    def _kind_ok_image(cls, v: str) -> str:
        if v not in ("product", "lodging"):
            raise ValueError("kind must be product or lodging")
        return v


class EnhanceImagePromptBody(BaseModel):
    kind: str = "product"
    title: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=500)
    category: str = Field(default="rural", max_length=24)
    description: str = Field(default="", max_length=4000)
    user_hint: str = Field(default="", max_length=1000)


@router.post("/ai/draft-package")
def post_draft_package(body: DraftPackageBody):
    """루플형 상품정보 + 이용안내(JSON) 한 번에 생성."""
    try:
        return generate_listing_package(
            body.kind,
            body.title,
            body.price,
            body.location,
            category=body.category,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"상품 패키지 생성 실패: {e}") from e


@router.post("/ai/draft-description")
def post_draft_description(body: DraftDescriptionBody):
    try:
        text = generate_listing_description(
            body.kind, body.title, body.price, body.location
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"설명 생성 실패: {e}",
        ) from e
    return {"description": text}


@router.post("/ai/enhance-image-prompt")
def post_enhance_image_prompt(body: EnhanceImagePromptBody):
    try:
        return enhance_image_prompt(
            body.kind,
            body.title,
            body.location,
            category=body.category,
            description=body.description,
            user_hint=body.user_hint,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"프롬프트 강화 실패: {e}",
        ) from e


@router.post("/ai/draft-image")
def post_draft_image(body: DraftImageBody):
    if not is_openai_configured():
        raise HTTPException(
            status_code=503,
            detail="이미지 생성은 OPENAI_API_KEY 가 필요합니다.",
        )
    try:
        png, prompt_used = generate_listing_cover_png(
            body.kind,
            body.title,
            body.location,
            category=body.category,
            description=body.description,
            prompt_en=body.prompt_en,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"이미지 생성 실패: {e}",
        ) from e
    return {
        "image_base64": base64.b64encode(png).decode("ascii"),
        "mime_type": "image/png",
        "prompt_used": prompt_used,
    }


class OcrListingDraftBody(BaseModel):
    images_base64: list[str] = Field(min_length=1, max_length=5)
    hint_tab: str | None = Field(
        default=None,
        description="product | lodging | experience — 셀러가 선택한 탭 힌트",
    )

    @field_validator("hint_tab")
    @classmethod
    def _hint_ok(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in ("product", "lodging", "experience"):
            raise ValueError("hint_tab must be product, lodging, or experience")
        return v


@router.post("/ocr/listing-draft")
def post_ocr_listing_draft(
    body: OcrListingDraftBody,
    user: dict = Depends(get_current_user),
):
    """수기 메모 사진 OCR → 상품·숙박·체험 등록 폼 초안."""
    if user.get("role") not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 로그인이 필요합니다.")
    try:
        return parse_note_images(body.images_base64, hint_tab=body.hint_tab)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OCR 실패: {e}") from e


@router.get("/covers/{listing_id}")
def get_listing_cover(listing_id: str):
    path = cover_file_path(listing_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="cover not found")
    return FileResponse(path, media_type="image/png")


class ListingCreate(BaseModel):
    kind: str
    category: str = Field(default="rural", max_length=24)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    price: int = Field(ge=0, le=100_000_000)
    location: str = Field(default="", max_length=500)
    emoji: str | None = Field(default=None, max_length=8)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    max_guests: int | None = Field(default=None, ge=1, le=100)
    seller_id: str = Field(default="seller-local", max_length=80)
    cover_image_base64: str | None = Field(
        default=None,
        max_length=9_000_000,
        description="선택. PNG 등 바이너리의 base64 또는 data URL",
    )
    guide: dict | None = Field(default=None, description="이용안내·체험 STEP 등 JSON")

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in ("product", "lodging"):
            raise ValueError("kind must be product or lodging")
        return v

    @field_validator("category")
    @classmethod
    def _category_ok(cls, v: str) -> str:
        allowed = ("experience", "rural", "fishing", "craft", "leisure", "lodging")
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}")
        return v


@router.post("/listings")
def post_listing(body: ListingCreate, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 로그인이 필요합니다.")
    data = body.model_dump()
    if user.get("role") == "seller":
        # 셀러는 항상 본인 ID 로 강제 — 다른 ID 로 위장 등록 차단
        data["seller_id"] = user.get("seller_id") or data.get("seller_id")
    return create_listing(data)


class ListingPhotoBody(BaseModel):
    image_base64: str | None = Field(default=None, max_length=9_000_000)
    url: str | None = Field(default=None, max_length=2000)


@router.get("/listings/{listing_id}/photos")
def get_listing_photos(listing_id: str):
    return {"items": list_photos(listing_id)}


@router.post("/listings/{listing_id}/photos")
def add_listing_photo(
    listing_id: str,
    body: ListingPhotoBody,
    user: dict = Depends(get_current_user),
):
    role = user.get("role")
    if role not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 로그인이 필요합니다.")
    existing = get_listing(listing_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    if role == "seller" and existing.get("seller_id") != user.get("seller_id"):
        raise HTTPException(status_code=403, detail="본인 상품만 사진을 추가할 수 있습니다.")
    try:
        return add_photo(listing_id, image_base64=body.image_base64, url=body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/listings/{listing_id}/photos/{photo_id}")
def get_listing_photo_file(listing_id: str, photo_id: str):
    pid = photo_id.split(".", 1)[0]
    owner = get_photo_listing_id(pid)
    if owner != listing_id:
        raise HTTPException(status_code=404, detail="photo not found")
    path = photo_file_path(pid)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo file missing")
    return FileResponse(path, media_type="image/png")


@router.delete("/listings/{listing_id}/photos/{photo_id}")
def remove_listing_photo(
    listing_id: str,
    photo_id: str,
    user: dict = Depends(get_current_user),
):
    role = user.get("role")
    if role not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 로그인이 필요합니다.")
    existing = get_listing(listing_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    if role == "seller" and existing.get("seller_id") != user.get("seller_id"):
        raise HTTPException(status_code=403, detail="본인 상품만 수정할 수 있습니다.")
    if not delete_photo(photo_id):
        raise HTTPException(status_code=404, detail="photo not found")
    return {"ok": True}


@router.get("/listings/{listing_id}/bookings")
def get_listing_bookings(listing_id: str):
    """예약된 날짜 목록 (체크인 포함, 체크아웃 제외). 숙박만."""
    existing = get_listing(listing_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    if existing.get("kind") != "lodging":
        return {"booked_dates": []}
    from datetime import date

    from db.database import SessionLocal as _S
    from db.models import OrderRow as _OR
    from sqlalchemy import select as _select

    booked: set[str] = set()
    today = date.today().isoformat()
    with _S() as session:
        orders = session.scalars(
            _select(_OR).where(_OR.fulfillment_status.in_(("preparing", "shipping", "completed")))
        ).all()
        for o in orders:
            if not o.stay_start or not o.stay_end:
                continue
            if o.stay_end < today:
                continue
            try:
                import json as _json

                items = _json.loads(o.items_json or "[]")
            except ValueError:
                items = []
            if not any(it.get("listing_id") == listing_id for it in items):
                continue
            cur = date.fromisoformat(o.stay_start)
            end = date.fromisoformat(o.stay_end)
            while cur < end:
                booked.add(cur.isoformat())
                cur = date.fromordinal(cur.toordinal() + 1)
    return {"booked_dates": sorted(booked)}


@router.delete("/listings/{listing_id}")
def remove_listing(listing_id: str, user: dict = Depends(get_current_user)):
    role = user.get("role")
    if role not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 로그인이 필요합니다.")
    if role == "seller":
        existing = get_listing(listing_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="listing not found")
        if existing.get("seller_id") != user.get("seller_id"):
            raise HTTPException(status_code=403, detail="본인 상품만 내릴 수 있습니다.")
    if not delete_listing(listing_id):
        raise HTTPException(status_code=404, detail="listing not found")
    return {"ok": True}


class SellerContextBody(BaseModel):
    kind: str = "product"
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    price: int = Field(default=0, ge=0, le=100_000_000)
    location: str = Field(default="", max_length=500)
    buyer_name: str = Field(default="고객", max_length=100)
    order_id: str = Field(default="주문예시", max_length=80)


@router.post("/seller/sns-draft")
def post_sns_draft(body: SellerContextBody):
    if body.kind not in ("product", "lodging"):
        body.kind = "product"
    return generate_sns_draft(
        body.kind, body.title, body.description, body.location, body.price
    )


@router.post("/seller/tourism")
def post_tourism(body: SellerContextBody):
    return tourism_tips(body.location, body.title)


@router.post("/seller/weather-season")
def post_weather(body: SellerContextBody):
    return weather_season_tips(body.location)


@router.post("/seller/alimtalk-draft")
def post_alimtalk(body: SellerContextBody):
    return alimtalk_draft(body.title, body.buyer_name, body.order_id)


@router.get("/seller/agent-suggestions")
def get_agent_suggestions(seller_id: str = "seller-local"):
    return agent_suggestions(seller_id)
