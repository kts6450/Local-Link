"""상품·숙박 목록 — SQLite (단일 DB, 소비자·공급자 동시 연동)."""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from db.database import SessionLocal
from db.models import ListingRow, ReviewRow
from services.listing_events import bump_listings_version
from services.listing_guide import guide_to_json, parse_guide_json

_RUNTIME = Path(__file__).resolve().parent.parent / "data" / "runtime"
_COVERS_DIR = _RUNTIME / "listing_covers"


def cover_file_path(listing_id: str) -> Path:
    return _COVERS_DIR / f"{listing_id}.png"


def _decode_cover_b64(raw: str | None) -> bytes | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if s.startswith("data:"):
        try:
            s = s.split(",", 1)[1]
        except IndexError:
            return None
    try:
        data = base64.b64decode(s, validate=False)
    except (ValueError, binascii.Error):
        return None
    if len(data) > 6_500_000:
        return None
    return data


def _row_to_dict(row: ListingRow, *, rating: float = 0.0, review_count: int = 0) -> dict:
    from services.listing_photos import list_photos

    return {
        "id": row.id,
        "seller_id": row.seller_id,
        "kind": row.kind,
        "category": getattr(row, "category", None) or ("lodging" if row.kind == "lodging" else "rural"),
        "title": row.title,
        "description": row.description,
        "price": row.price,
        "emoji": row.emoji,
        "location": row.location,
        "stock": row.stock,
        "max_guests": row.max_guests,
        "created_at": row.created_at,
        "cover_image_url": row.cover_image_url,
        "guide": parse_guide_json(getattr(row, "guide_json", None)),
        "photos": list_photos(row.id),
        "rating": round(rating, 1) if rating else 0.0,
        "review_count": int(review_count or 0),
    }


def _review_aggregates(session, listing_ids: list[str]) -> dict[str, tuple[float, int]]:
    if not listing_ids:
        return {}
    rows = session.execute(
        select(
            ReviewRow.listing_id,
            func.avg(ReviewRow.rating),
            func.count(ReviewRow.id),
        )
        .where(ReviewRow.listing_id.in_(listing_ids))
        .group_by(ReviewRow.listing_id)
    ).all()
    return {row[0]: (float(row[1] or 0.0), int(row[2] or 0)) for row in rows}


def list_listings() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(ListingRow).order_by(ListingRow.created_at.desc())
        ).all()
        agg = _review_aggregates(session, [r.id for r in rows])
        out = []
        for r in rows:
            avg, cnt = agg.get(r.id, (0.0, 0))
            out.append(_row_to_dict(r, rating=avg, review_count=cnt))
        return out


def list_best_listings(limit: int = 12) -> list[dict]:
    """리뷰 평점·건수 기반 베스트 — 최소 5건 이상 받은 listing 우선."""
    with SessionLocal() as session:
        rows = session.execute(
            select(
                ReviewRow.listing_id,
                func.avg(ReviewRow.rating).label("avg_rating"),
                func.count(ReviewRow.id).label("cnt"),
            )
            .group_by(ReviewRow.listing_id)
            .having(func.count(ReviewRow.id) >= 5)
        ).all()
        ranked = sorted(
            rows,
            key=lambda r: (float(r[1] or 0), int(r[2] or 0)),
            reverse=True,
        )[: max(limit, 1)]
        if not ranked:
            return []
        ids = [r[0] for r in ranked]
        listings = session.scalars(
            select(ListingRow).where(ListingRow.id.in_(ids))
        ).all()
        agg = {r[0]: (float(r[1] or 0), int(r[2] or 0)) for r in ranked}
        items = []
        for row in listings:
            avg, cnt = agg.get(row.id, (0.0, 0))
            items.append(_row_to_dict(row, rating=avg, review_count=cnt))
        items.sort(key=lambda d: (d["rating"], d["review_count"]), reverse=True)
        return items


def listings_summary_for_llm() -> str:
    lines = []
    for e in list_listings():
        k = "상품" if e.get("kind") == "product" else "숙박"
        loc = e.get("location", "")
        price = e.get("price", 0)
        lines.append(
            f"- [{k}] {e.get('title', '')} (id: {e.get('id')}) — {price:,}원, {loc}"
        )
    return "\n".join(lines) if lines else "(등록된 물건이 아직 없습니다.)"


def get_listing(listing_id: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(ListingRow, listing_id)
        if row is None:
            return None
        agg = _review_aggregates(session, [listing_id])
        avg, cnt = agg.get(listing_id, (0.0, 0))
        return _row_to_dict(row, rating=avg, review_count=cnt)


def create_listing(record: dict) -> dict:
    record = dict(record)
    cover_b64 = record.pop("cover_image_base64", None)
    guide_raw = record.pop("guide", None)
    guide_json = guide_to_json(guide_raw if isinstance(guide_raw, dict) else None)

    now = datetime.utcnow().isoformat()
    lid = record.get("id") or f"L-{uuid.uuid4().hex[:10]}"
    kind = record.get("kind") or "product"
    category = (record.get("category") or "").strip()
    if category not in ("experience", "rural", "fishing", "craft", "leisure", "lodging"):
        category = "lodging" if kind == "lodging" else "rural"
    item = {
        "id": lid,
        "seller_id": record.get("seller_id") or "seller-local",
        "kind": kind,
        "category": category,
        "title": (record.get("title") or "").strip() or "이름 없음",
        "description": (record.get("description") or "").strip(),
        "price": int(record.get("price") or 0),
        "emoji": record.get("emoji") or ("🏷️" if kind == "product" else "🏠"),
        "location": (record.get("location") or "").strip(),
        "stock": record.get("stock"),
        "max_guests": record.get("max_guests"),
        "created_at": now,
        "cover_image_url": None,
        "guide_json": guide_json,
    }
    if item["kind"] not in ("product", "lodging"):
        item["kind"] = "product"
    if item["kind"] == "product" and item["stock"] is None:
        item["stock"] = 99
    if item["kind"] == "lodging":
        item["stock"] = None
        if item["max_guests"] is None:
            item["max_guests"] = 4

    row = ListingRow(**{k: v for k, v in item.items() if k != "guide"})
    with SessionLocal() as session:
        session.add(row)
        session.commit()

    cover_bytes = _decode_cover_b64(cover_b64)
    if cover_bytes:
        _COVERS_DIR.mkdir(parents=True, exist_ok=True)
        cover_file_path(lid).write_bytes(cover_bytes)
        rel = f"/api/marketplace/covers/{lid}"
        with SessionLocal() as session:
            row2 = session.get(ListingRow, lid)
            if row2 is not None:
                row2.cover_image_url = rel
                session.commit()
        item["cover_image_url"] = rel

    bump_listings_version()
    return item


def update_listing(listing_id: str, record: dict) -> dict | None:
    """기존 listing 수정. 전달된 필드만 반영하며, 새 커버 이미지가 없으면 기존 유지."""
    record = dict(record)
    cover_b64 = record.pop("cover_image_base64", None)
    has_guide = "guide" in record
    guide_raw = record.pop("guide", None)

    with SessionLocal() as session:
        row = session.get(ListingRow, listing_id)
        if row is None:
            return None

        if record.get("kind") in ("product", "lodging"):
            row.kind = record["kind"]
        if "category" in record:
            cat = (record.get("category") or "").strip()
            if cat in ("experience", "rural", "fishing", "craft", "leisure", "lodging"):
                row.category = cat
        if record.get("title") is not None and str(record["title"]).strip():
            row.title = str(record["title"]).strip()
        if record.get("description") is not None:
            row.description = str(record["description"]).strip()
        if record.get("price") is not None:
            row.price = int(record["price"] or 0)
        if record.get("emoji"):
            row.emoji = record["emoji"]
        if record.get("location") is not None:
            row.location = str(record["location"]).strip()

        # kind 에 맞춰 재고/정원 정리
        if row.kind == "lodging":
            row.stock = None
            if record.get("max_guests") is not None:
                row.max_guests = int(record["max_guests"])
            elif row.max_guests is None:
                row.max_guests = 4
        else:
            row.max_guests = None
            if record.get("stock") is not None:
                row.stock = int(record["stock"])

        if has_guide:
            row.guide_json = guide_to_json(guide_raw if isinstance(guide_raw, dict) else None)

        cover_bytes = _decode_cover_b64(cover_b64)
        if cover_bytes:
            _COVERS_DIR.mkdir(parents=True, exist_ok=True)
            cover_file_path(listing_id).write_bytes(cover_bytes)
            row.cover_image_url = f"/api/marketplace/covers/{listing_id}"

        session.commit()
        agg = _review_aggregates(session, [listing_id])
        avg, cnt = agg.get(listing_id, (0.0, 0))
        result = _row_to_dict(row, rating=avg, review_count=cnt)

    bump_listings_version()
    return result


def delete_listing(listing_id: str) -> bool:
    with SessionLocal() as session:
        row = session.get(ListingRow, listing_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
    p = cover_file_path(listing_id)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass
    bump_listings_version()
    return True
