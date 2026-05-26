"""리뷰·평점 — 결제 완료한 구매자만 작성."""

from __future__ import annotations

import uuid
import hashlib
import logging
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from db.database import SessionLocal
from db.models import OrderRow, ReviewRow, ReviewSummaryRow
from routers.auth import get_current_user

logger = logging.getLogger("reviews_router")

KOBART_MODEL_ID = "gogamza/kobart-summarization"
_kobart_tokenizer = None
_kobart_model = None
_model_lock = threading.Lock()

def get_kobart_resources():
    global _kobart_tokenizer, _kobart_model
    if _kobart_tokenizer is None or _kobart_model is None:
        with _model_lock:
            if _kobart_tokenizer is None or _kobart_model is None:
                logger.info("[KOBART] 모델 및 토크나이저 로드 시작 (Local-only 시도)...")
                try:
                    _kobart_tokenizer = AutoTokenizer.from_pretrained(KOBART_MODEL_ID, local_files_only=True)
                    _kobart_model = AutoModelForSeq2SeqLM.from_pretrained(KOBART_MODEL_ID, local_files_only=True)
                    logger.info("[KOBART] 로컬 캐시에서 모델 로드 성공.")
                except Exception:
                    logger.info("[KOBART] 로컬 캐시 로드 실패. 온라인에서 다운로드 시작 (시간 소요)...")
                    _kobart_tokenizer = AutoTokenizer.from_pretrained(KOBART_MODEL_ID, local_files_only=False)
                    _kobart_model = AutoModelForSeq2SeqLM.from_pretrained(KOBART_MODEL_ID, local_files_only=False)
                    logger.info("[KOBART] 온라인 모델 로드 및 다운로드 완료.")
    return _kobart_tokenizer, _kobart_model

def warm_up_kobart():
    try:
        get_kobart_resources()
    except Exception as e:
        logger.error("[KOBART] 백그라운드 모델 로드 실패: %s", e)


def _get_reviews_hash(rows: list[ReviewRow]) -> str:
    sig = ",".join(f"{r.id}:{r.rating}:{len(r.body or '')}:{r.created_at}" for r in rows)
    return hashlib.md5(sig.encode("utf-8")).hexdigest()

def _local_summarize(reviews_text: str) -> str:
    tokenizer, model = get_kobart_resources()
    inputs = tokenizer(reviews_text, return_tensors="pt", max_length=512, truncation=True)
    summary_ids = model.generate(
        inputs["input_ids"],
        num_beams=4,
        max_length=128,
        min_length=10,
        eos_token_id=tokenizer.eos_token_id or 1
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()

def _llm_audit_and_polish(original_reviews: list[str], draft_summary: str) -> str:
    from services.api_keys import is_anthropic_configured, anthropic_messages_create, anthropic_response_text
    from services.llm import DEFAULT_MODEL

    if not is_anthropic_configured():
        from services.api_keys import is_gemini_configured, call_gemini_json
        if is_gemini_configured():
            logger.info("[REVIEW-SUMMARY] Gemini를 사용하여 초안 검증 및 윤문 시도")
            system = "너는 친절하고 솔직한 쇼핑몰 리뷰 분석 도우미다."
            prompt = f"""다음은 실제 구매자들의 리뷰 원본 리스트와, 로컬 AI가 작성한 1차 요약 초안입니다.
1차 요약 초안이 리뷰 원본의 내용(별점 및 의견)을 왜곡하지 않았는지 검증하고, 친근하고 부드러운 한국어 존댓말(2~3문장)로 다듬어 완성된 문장형태의 JSON으로 반환해 주세요.

[리뷰 원본 리스트]
{chr(10).join(original_reviews)}

[1차 요약 초안]
{draft_summary}

응답 형식:
{{
  "summary": "최종 요약 및 교정문"
}}
"""
            res_dict = call_gemini_json(system=system, user=prompt)
            if res_dict and "summary" in res_dict:
                return res_dict["summary"].strip()
        return draft_summary

    logger.info("[REVIEW-SUMMARY] Claude를 사용하여 초안 검증 및 윤문 시도")
    reviews_bullet = "\n".join(f"- {rev}" for rev in original_reviews)
    prompt = f"""다음은 구매자들이 작성한 실제 리뷰 원본 리스트와, 로컬 AI가 작성한 1차 요약 초안입니다.
1차 요약 초안이 리뷰 원본의 내용을 왜곡했는지 검증하고, 사실과 다른 부분(환각)이 있다면 원본 리뷰에 맞게 정정해 주세요.
그리고 전체 내용을 종합하여 고객이 읽기 편한 친근하고 부드러운 한국어 존댓말(2~3문장)로 최종 요약문을 작성해 주세요.
장식 기호(마크다운, 따옴표 등) 없이 오직 최종 완성된 요약 텍스트만 답변하세요.

[리뷰 원본 리스트]
{reviews_bullet}

[1차 요약 초안]
{draft_summary}
"""
    try:
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=512,
            system="너는 친절하고 솔직한 쇼핑몰 리뷰 분석 도우미다.",
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
        )
        return anthropic_response_text(response)
    except Exception as e:
        logger.error("[REVIEW-SUMMARY] Claude 요약 실패: %s", e)
        return draft_summary

router = APIRouter(prefix="/api/marketplace/listings", tags=["reviews"])


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=2000)
    order_id: str | None = Field(default=None, max_length=48)


def _row_to_dict(r: ReviewRow) -> dict:
    return {
        "id": r.id,
        "listing_id": r.listing_id,
        "order_id": r.order_id,
        "user_id": r.user_id,
        "user_name": r.user_name,
        "rating": r.rating,
        "body": r.body or "",
        "created_at": r.created_at,
    }


@router.get("/reviews/mine")
def get_my_reviews(user: dict = Depends(get_current_user)):
    if user.get("role") not in ("consumer", "master"):
        raise HTTPException(status_code=403, detail="구매자만 본인 리뷰를 조회할 수 있습니다.")
    from db.models import ListingRow
    with SessionLocal() as session:
        stmt = (
            select(ReviewRow, ListingRow.title, ListingRow.cover_image_url)
            .join(ListingRow, ReviewRow.listing_id == ListingRow.id)
            .where(ReviewRow.user_id == user.get("id"))
            .order_by(ReviewRow.created_at.desc())
        )
        results = session.execute(stmt).all()
        
        out = []
        for r, title, cover_image in results:
            d = _row_to_dict(r)
            d["listing_title"] = title
            d["listing_cover_image"] = cover_image
            out.append(d)
        return out


@router.get("/{listing_id}/reviews")
def get_reviews(listing_id: str):
    with SessionLocal() as session:
        rows = session.scalars(
            select(ReviewRow)
            .where(ReviewRow.listing_id == listing_id)
            .order_by(ReviewRow.created_at.desc())
        ).all()
        avg = session.scalar(
            select(func.avg(ReviewRow.rating)).where(ReviewRow.listing_id == listing_id)
        )
    return {
        "count": len(rows),
        "average": round(float(avg), 1) if avg else 0.0,
        "items": [_row_to_dict(r) for r in rows],
    }


@router.get("/{listing_id}/reviews/summary")
def get_reviews_summary(listing_id: str):
    with SessionLocal() as session:
        rows = session.scalars(
            select(ReviewRow)
            .where(ReviewRow.listing_id == listing_id)
            .order_by(ReviewRow.created_at.desc())
        ).all()

        if len(rows) < 3:
            return {
                "status": "not_enough_reviews",
                "message": "리뷰가 3개 이상 등록되어야 AI 요약이 제공됩니다.",
                "summary": "",
                "count": len(rows),
            }

        # 1. 캐시 체크 (DB 기반)
        current_hash = _get_reviews_hash(rows)
        cached = session.scalar(
            select(ReviewSummaryRow).where(ReviewSummaryRow.listing_id == listing_id)
        )
        if cached and cached.hash == current_hash:
            logger.info("[REVIEW-SUMMARY] 캐시 적중 (DB Cache Hit). 요약 즉시 반환.")
            return {
                "status": "success",
                "summary": cached.summary,
                "count": len(rows),
            }

        # 2. 로컬 초안 생성 (KoBART)
        combined_texts = []
        for r in rows:
            body = (r.body or "").strip()
            if body:
                combined_texts.append(f"★{r.rating}점: {body}")
        
        reviews_input = " ".join(combined_texts)[:1500]
        
        if not reviews_input.strip():
            return {
                "status": "empty_content",
                "message": "텍스트 내용이 있는 리뷰가 부족하여 요약을 생성할 수 없습니다.",
                "summary": "",
                "count": len(rows),
            }

        logger.info("[REVIEW-SUMMARY] 로컬 KoBART 모델로 초안 작성 시작...")
        try:
            draft = _local_summarize(reviews_input)
            logger.info("[REVIEW-SUMMARY] 로컬 초안 작성 완료: %s", draft)
        except Exception as exc:
            logger.error("[REVIEW-SUMMARY] 로컬 KoBART 초안 생성 실패: %s", exc)
            draft = "리뷰를 종합한 결과 제품 만족도가 높습니다."

        # 3. 외부 LLM 검증 및 윤문
        original_list = [f"★{r.rating}점: {(r.body or '').strip()}" for r in rows if (r.body or "").strip()]
        final_summary = _llm_audit_and_polish(original_list, draft)
        logger.info("[REVIEW-SUMMARY] 최종 요약문 확정: %s", final_summary)

        # 4. 캐시 저장 (DB 기반)
        if cached:
            cached.summary = final_summary
            cached.hash = current_hash
            cached.updated_at = datetime.utcnow().isoformat()
        else:
            new_cache = ReviewSummaryRow(
                listing_id=listing_id,
                summary=final_summary,
                hash=current_hash,
                updated_at=datetime.utcnow().isoformat()
            )
            session.add(new_cache)
        session.commit()

    return {
        "status": "success",
        "summary": final_summary,
        "count": len(rows),
    }


@router.post("/{listing_id}/reviews")
def post_review(
    listing_id: str,
    body: ReviewCreate,
    user: dict = Depends(get_current_user),
):
    if user.get("role") not in ("consumer", "master"):
        raise HTTPException(status_code=403, detail="구매자만 리뷰를 작성할 수 있습니다.")

    text = (body.body or "").strip()

    with SessionLocal() as session:
        if user.get("role") == "consumer":
            paid_orders = session.scalars(
                select(OrderRow).where(
                    OrderRow.buyer_id == user.get("id"),
                    OrderRow.payment_status == "paid",
                )
            ).all()

            owned = False
            order_match: str | None = body.order_id
            for o in paid_orders:
                try:
                    import json as _json

                    items = _json.loads(o.items_json or "[]")
                except ValueError:
                    items = []
                for it in items:
                    if it.get("listing_id") == listing_id:
                        owned = True
                        if not order_match:
                            order_match = o.id
                        break
                if owned:
                    break
            if not owned:
                raise HTTPException(
                    status_code=403,
                    detail="구매·결제한 상품에만 리뷰를 남길 수 있습니다.",
                )

            already = session.scalar(
                select(ReviewRow.id).where(
                    ReviewRow.listing_id == listing_id,
                    ReviewRow.user_id == user.get("id"),
                )
            )
            if already:
                raise HTTPException(status_code=409, detail="이미 리뷰를 작성하셨습니다.")
        else:
            order_match = body.order_id

        row = ReviewRow(
            id=f"rv-{uuid.uuid4().hex[:12]}",
            listing_id=listing_id,
            order_id=order_match,
            user_id=user.get("id") or "master",
            user_name=user.get("display_name") or "익명",
            rating=body.rating,
            body=text,
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_dict(row)
