"""마스터(운영자) 전용 — 회원·상품·통계·음성·OCR 어드민."""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from db.database import SessionLocal
from db.models import ListingRow, OcrLogRow, OrderRow, ReviewRow, UserRow, VoiceLogRow
from routers.auth import get_current_user
from services.listings_store import delete_listing

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_master(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "master":
        raise HTTPException(status_code=403, detail="운영자(마스터) 전용입니다.")
    return user


@router.get("/users")
def list_users(_: dict = Depends(require_master)):
    with SessionLocal() as session:
        rows = session.scalars(select(UserRow).order_by(UserRow.created_at.desc())).all()
        return [
            {
                "id": r.id,
                "email": r.email,
                "role": r.role,
                "display_name": r.display_name,
                "seller_sector": r.seller_sector,
                "seller_id": r.seller_id,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.delete("/users/{user_id}")
def remove_user(user_id: str, _: dict = Depends(require_master)):
    with SessionLocal() as session:
        row = session.get(UserRow, user_id)
        if row is None:
            raise HTTPException(status_code=404, detail="user not found")
        session.delete(row)
        session.commit()
    return {"ok": True}


@router.get("/listings")
def list_all_listings(_: dict = Depends(require_master)):
    """모든 셀러의 상품 — 셀러 이메일까지 조인."""
    with SessionLocal() as session:
        listings = session.scalars(
            select(ListingRow).order_by(ListingRow.created_at.desc())
        ).all()
        sellers = {
            u.seller_id: u
            for u in session.scalars(
                select(UserRow).where(UserRow.role == "seller")
            ).all()
            if u.seller_id
        }
        return [
            {
                "id": l.id,
                "title": l.title,
                "kind": l.kind,
                "category": l.category,
                "price": l.price,
                "location": l.location,
                "seller_id": l.seller_id,
                "seller_email": sellers.get(l.seller_id).email if sellers.get(l.seller_id) else None,
                "created_at": l.created_at,
            }
            for l in listings
        ]


@router.delete("/listings/{listing_id}")
def admin_delete_listing(listing_id: str, _: dict = Depends(require_master)):
    if not delete_listing(listing_id):
        raise HTTPException(status_code=404, detail="listing not found")
    return {"ok": True}


@router.get("/stats")
def stats(_: dict = Depends(require_master)):
    with SessionLocal() as session:
        users_n = session.scalar(select(func.count()).select_from(UserRow)) or 0
        consumers_n = session.scalar(
            select(func.count()).select_from(UserRow).where(UserRow.role == "consumer")
        ) or 0
        sellers_n = session.scalar(
            select(func.count()).select_from(UserRow).where(UserRow.role == "seller")
        ) or 0
        listings_n = session.scalar(select(func.count()).select_from(ListingRow)) or 0
        orders_n = session.scalar(select(func.count()).select_from(OrderRow)) or 0
        paid_n = session.scalar(
            select(func.count()).select_from(OrderRow).where(OrderRow.payment_status == "paid")
        ) or 0
        revenue = session.scalar(
            select(func.coalesce(func.sum(OrderRow.total), 0)).where(OrderRow.payment_status == "paid")
        ) or 0
        reviews_n = session.scalar(select(func.count()).select_from(ReviewRow)) or 0
    return {
        "users": users_n,
        "consumers": consumers_n,
        "sellers": sellers_n,
        "listings": listings_n,
        "orders": orders_n,
        "paid_orders": paid_n,
        "revenue": int(revenue),
        "reviews": reviews_n,
    }


# ─────────────────── 공통 헬퍼 ───────────────────

def _safe(text: str) -> str:
    """파일명에 안전하게 쓸 수 있도록 특수문자 제거."""
    return re.sub(r'[\\/*?:"<>|]', "", text).strip() or "unknown"


def _voice_filename(email_prefix: str, created_at: str, log_id: str) -> str:
    ts = created_at[:16].replace("T", "_").replace(":", "-")
    return f"voice_{_safe(email_prefix)}_{ts}_{log_id}.wav"


def _ocr_filename(email_prefix: str, created_at: str, log_id: str, n: int) -> str:
    ts = created_at[:16].replace("T", "_").replace(":", "-")
    return f"ocr_{_safe(email_prefix)}_{ts}_{log_id}_{n + 1}.jpg"


def _seller_email_map(session, rows) -> dict[str, str]:
    """seller_id → email 매핑 헬퍼."""
    seller_ids = {r.seller_id for r in rows if r.seller_id}
    if not seller_ids:
        return {}
    users = session.scalars(
        select(UserRow).where(UserRow.seller_id.in_(seller_ids))
    ).all()
    return {u.seller_id: u.email for u in users if u.seller_id}


# ─────────────────────────── 음성 로그 ───────────────────────────

@router.get("/voice-logs")
def list_voice_logs(
    page: int = 1,
    limit: int = 20,
    _: dict = Depends(require_master),
):
    """음성 로그 목록 — 최신순, 페이지네이션."""
    page = max(1, page)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit
    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(VoiceLogRow)) or 0
        rows = session.scalars(
            select(VoiceLogRow)
            .order_by(VoiceLogRow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        seller_emails = _seller_email_map(session, rows)

        items = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "seller_id": r.seller_id,
                "seller_email": seller_emails.get(r.seller_id) if r.seller_id else None,
                "source": r.source,
                "has_audio": bool(r.audio_path and Path(r.audio_path).is_file()),
                "raw_text": r.raw_text,
                "corrected_text": r.corrected_text,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    return {"items": items, "total": total, "page": page, "limit": limit}


# ★ ZIP 엔드포인트를 /{log_id} 패턴 **앞**에 배치 — FastAPI 라우트 충돌 방지
@router.get("/voice-logs/zip")
def download_voice_logs_zip(_: dict = Depends(require_master)):
    """모든 음성 로그 오디오를 ZIP으로 일괄 다운로드."""
    buf = io.BytesIO()
    with SessionLocal() as session:
        rows = session.scalars(
            select(VoiceLogRow).order_by(VoiceLogRow.created_at.desc())
        ).all()

        seller_emails = _seller_email_map(session, rows)

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in rows:
                if not r.audio_path:
                    continue
                p = Path(r.audio_path)
                if not p.is_file():
                    continue
                email = seller_emails.get(r.seller_id, "guest") if r.seller_id else "guest"
                email_prefix = email.split("@")[0]
                arcname = _voice_filename(email_prefix, r.created_at or "", r.id)
                zf.write(p, arcname)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=voice_logs_all.zip"},
    )


# ★ CSV 엔드포인트를 /{log_id} 패턴 **앞**에 배치 — FastAPI 라우트 충돌 방지
@router.get("/voice-logs/csv")
def download_voice_logs_csv(_: dict = Depends(require_master)):
    """모든 음성 로그를 CSV로 일괄 다운로드 (UTF-8 BOM)."""
    def generate():
        # UTF-8 BOM
        yield b"\xef\xbb\xbf"
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["로그ID", "판매자", "소스", "ASR 인식 원문", "AI 보정 텍스트", "음성 파일 매핑명", "등록일시"])
        yield output.getvalue().encode("utf-8")
        
        with SessionLocal() as session:
            rows = session.scalars(
                select(VoiceLogRow).order_by(VoiceLogRow.created_at.desc())
            ).all()
            seller_emails = _seller_email_map(session, rows)
            
            for r in rows:
                output = io.StringIO()
                writer = csv.writer(output)
                email = seller_emails.get(r.seller_id, "guest") if r.seller_id else "guest"
                email_prefix = email.split("@")[0]
                mapping_name = _voice_filename(email_prefix, r.created_at or "", r.id)
                writer.writerow([
                    r.id,
                    email,
                    r.source,
                    r.raw_text or "",
                    r.corrected_text or "",
                    mapping_name,
                    r.created_at
                ])
                yield output.getvalue().encode("utf-8")

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=voice_logs_all.csv"},
    )


@router.delete("/voice-logs/{log_id}")
def delete_voice_log(log_id: str, _: dict = Depends(require_master)):
    with SessionLocal() as session:
        row = session.get(VoiceLogRow, log_id)
        if row is None:
            raise HTTPException(status_code=404, detail="voice log not found")
        # 파일 삭제
        if row.audio_path:
            try:
                Path(row.audio_path).unlink(missing_ok=True)
            except Exception:
                pass
        session.delete(row)
        session.commit()
    return {"ok": True}


@router.get("/voice-logs/{log_id}/audio")
def get_voice_log_audio(log_id: str, _: dict = Depends(require_master)):
    """오디오 파일 스트리밍."""
    with SessionLocal() as session:
        row = session.get(VoiceLogRow, log_id)
        if row is None:
            raise HTTPException(status_code=404, detail="voice log not found")
        if not row.audio_path:
            raise HTTPException(status_code=404, detail="audio not recorded")
        path = Path(row.audio_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="audio file missing")
    return FileResponse(path, media_type="audio/wav")


# ─────────────────────────── OCR 로그 ───────────────────────────

@router.get("/ocr-logs")
def list_ocr_logs(
    page: int = 1,
    limit: int = 20,
    _: dict = Depends(require_master),
):
    """OCR 로그 목록 — 최신순, 페이지네이션."""
    page = max(1, page)
    limit = max(1, min(limit, 100))
    offset = (page - 1) * limit
    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(OcrLogRow)) or 0
        rows = session.scalars(
            select(OcrLogRow)
            .order_by(OcrLogRow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        seller_emails = _seller_email_map(session, rows)

        items = []
        for r in rows:
            paths = [p for p in (r.image_paths or "").split(",") if p]
            image_count = len(paths)
            has_images = any(Path(p).is_file() for p in paths)

            # parsed_json에서 fields 요약 추출
            parsed: dict = {}
            if r.parsed_json:
                try:
                    parsed = json.loads(r.parsed_json)
                except Exception:
                    pass

            items.append({
                "id": r.id,
                "user_id": r.user_id,
                "seller_id": r.seller_id,
                "seller_email": seller_emails.get(r.seller_id) if r.seller_id else None,
                "image_count": image_count,
                "has_images": has_images,
                "ocr_raw_text": r.ocr_raw_text,
                "confidence": r.confidence,
                "listing_tab": parsed.get("listing_tab"),
                "fields_summary": {
                    k: (v.get("value") if isinstance(v, dict) else v)
                    for k, v in (parsed.get("fields") or {}).items()
                    if k in ("title", "price", "location", "quantity")
                },
                "warnings": parsed.get("warnings") or [],
                "created_at": r.created_at,
            })
    return {"items": items, "total": total, "page": page, "limit": limit}


# ★ ZIP 엔드포인트를 /{log_id} 패턴 **앞**에 배치 — FastAPI 라우트 충돌 방지
@router.get("/ocr-logs/zip")
def download_ocr_logs_zip(_: dict = Depends(require_master)):
    """모든 OCR 로그 이미지를 ZIP으로 일괄 다운로드."""
    buf = io.BytesIO()
    with SessionLocal() as session:
        rows = session.scalars(
            select(OcrLogRow).order_by(OcrLogRow.created_at.desc())
        ).all()

        seller_emails = _seller_email_map(session, rows)

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in rows:
                paths = [p for p in (r.image_paths or "").split(",") if p]
                email = seller_emails.get(r.seller_id, "guest") if r.seller_id else "guest"
                email_prefix = email.split("@")[0]
                for i, img_path in enumerate(paths):
                    p = Path(img_path)
                    if not p.is_file():
                        continue
                    arcname = _ocr_filename(email_prefix, r.created_at or "", r.id, i)
                    zf.write(p, arcname)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=ocr_logs_all.zip"},
    )


# ★ CSV 엔드포인트를 /{log_id} 패턴 **앞**에 배치 — FastAPI 라우트 충돌 방지
@router.get("/ocr-logs/csv")
def download_ocr_logs_csv(_: dict = Depends(require_master)):
    """모든 OCR 로그를 CSV로 일괄 다운로드 (UTF-8 BOM)."""
    def generate():
        # UTF-8 BOM
        yield b"\xef\xbb\xbf"
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["로그ID", "판매자", "OCR 추출 원본 텍스트", "상품명", "가격", "수량", "지역", "이미지 파일 매핑명", "신뢰도", "등록일시"])
        yield output.getvalue().encode("utf-8")
        
        with SessionLocal() as session:
            rows = session.scalars(
                select(OcrLogRow).order_by(OcrLogRow.created_at.desc())
            ).all()
            seller_emails = _seller_email_map(session, rows)
            
            for r in rows:
                output = io.StringIO()
                writer = csv.writer(output)
                email = seller_emails.get(r.seller_id, "guest") if r.seller_id else "guest"
                email_prefix = email.split("@")[0]
                
                paths = [p for p in (r.image_paths or "").split(",") if p]
                img_names = " | ".join(_ocr_filename(email_prefix, r.created_at or "", r.id, i) for i in range(len(paths)))
                
                parsed: dict = {}
                if r.parsed_json:
                    try:
                        parsed = json.loads(r.parsed_json)
                    except Exception:
                        pass
                f = {
                    k: (v.get("value") if isinstance(v, dict) else v)
                    for k, v in (parsed.get("fields") or {}).items()
                    if k in ("title", "price", "location", "quantity")
                }
                confidence_str = f"{(r.confidence * 100):.0f}%" if r.confidence is not None else ""
                
                writer.writerow([
                    r.id,
                    email,
                    r.ocr_raw_text or "",
                    f.get("title") or "",
                    f.get("price") or "",
                    f.get("quantity") or "",
                    f.get("location") or "",
                    img_names,
                    confidence_str,
                    r.created_at
                ])
                yield output.getvalue().encode("utf-8")

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ocr_logs_all.csv"},
    )


@router.delete("/ocr-logs/{log_id}")
def delete_ocr_log(log_id: str, _: dict = Depends(require_master)):
    with SessionLocal() as session:
        row = session.get(OcrLogRow, log_id)
        if row is None:
            raise HTTPException(status_code=404, detail="ocr log not found")
        # 이미지 파일 삭제
        for p in (row.image_paths or "").split(","):
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
        session.delete(row)
        session.commit()
    return {"ok": True}


@router.get("/ocr-logs/{log_id}/image/{n}")
def get_ocr_log_image(log_id: str, n: int, _: dict = Depends(require_master)):
    """OCR 원본 이미지 파일 반환."""
    with SessionLocal() as session:
        row = session.get(OcrLogRow, log_id)
        if row is None:
            raise HTTPException(status_code=404, detail="ocr log not found")
        paths = [p for p in (row.image_paths or "").split(",") if p]
        if n >= len(paths):
            raise HTTPException(status_code=404, detail="image index out of range")
        path = Path(paths[n])
        if not path.is_file():
            raise HTTPException(status_code=404, detail="image file missing")
    return FileResponse(path, media_type="image/jpeg")
