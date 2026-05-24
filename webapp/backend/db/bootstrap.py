"""초기 스키마 생성 + 빈 DB일 때 시드/레거시 JSON 마이그레이션."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from db.database import SessionLocal, engine
from db.models import ListingRow, OrderRow

_DATA = Path(__file__).resolve().parent.parent / "data"
_RUNTIME = _DATA / "runtime"
_SEED = _DATA / "listings.seed.json"
_LEGACY_LISTINGS = _RUNTIME / "listings.json"
_LEGACY_ORDERS = _RUNTIME / "orders.json"


def init_database() -> None:
    import os

    from db.database import Base
    from db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    if os.environ.get("LOCAL_LINK_RESEED") == "1":
        _clear_listings_for_reseed()

    demo_mode = os.environ.get("LOCAL_LINK_DEMO_SEED", "1") not in ("0", "false", "False", "")
    if demo_mode:
        try:
            from db.demo_seed_runner import repair_demo_guides, repair_demo_images, seed_demo_marketplace

            force = os.environ.get("LOCAL_LINK_RESEED") == "1"
            seed_demo_marketplace(force=force)
            repaired = repair_demo_images()
            if repaired:
                print(f"[demo_seed] repaired {repaired} listing cover images")
            guides = repair_demo_guides()
            if guides:
                print(f"[demo_seed] filled {guides} listing guides")
        except Exception as e:  # noqa: BLE001
            print(f"[demo_seed] skipped: {e}")
    else:
        _seed_listings_if_empty()
    _seed_orders_if_empty()


def _clear_listings_for_reseed() -> None:
    from services.listing_events import bump_listings_version

    with SessionLocal() as session:
        session.query(ListingRow).delete()
        session.commit()
    bump_listings_version()


def _ensure_sqlite_columns() -> None:
    """기존 SQLite DB에 컬럼만 추가 (create_all은 새 컬럼을 ALTER 하지 않음)."""
    from sqlalchemy import text

    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(listings)")).fetchall()
        cols = {r[1] for r in rows}
        if "cover_image_url" not in cols:
            conn.execute(text("ALTER TABLE listings ADD COLUMN cover_image_url VARCHAR(2000)"))
        if "category" not in cols:
            conn.execute(text("ALTER TABLE listings ADD COLUMN category VARCHAR(24) DEFAULT 'rural'"))
            conn.execute(text("UPDATE listings SET category = 'lodging' WHERE kind = 'lodging' AND (category IS NULL OR category = 'rural')"))
            conn.execute(text("UPDATE listings SET category = 'rural' WHERE category IS NULL OR category = ''"))
        if "guide_json" not in cols:
            conn.execute(text("ALTER TABLE listings ADD COLUMN guide_json TEXT"))

        order_rows = conn.execute(text("PRAGMA table_info(orders)")).fetchall()
        order_cols = {r[1] for r in order_rows}
        if "fulfillment_status" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN fulfillment_status VARCHAR(24) DEFAULT 'pending'"))
            conn.execute(text("UPDATE orders SET fulfillment_status='preparing' WHERE payment_status='paid' AND (fulfillment_status IS NULL OR fulfillment_status='pending')"))
        if "buyer_id" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN buyer_id VARCHAR(48)"))
        if "stay_start" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN stay_start VARCHAR(10)"))
        if "stay_end" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN stay_end VARCHAR(10)"))


def _seed_listings_if_empty() -> None:
    from services.listing_events import bump_listings_version

    with SessionLocal() as session:
        n = session.scalar(select(func.count()).select_from(ListingRow))
        if n and n > 0:
            return

        raw: list[dict] = []
        if _LEGACY_LISTINGS_exists_with_data():
            raw = json.loads(_LEGACY_LISTINGS.read_text(encoding="utf-8"))
        elif _SEED.exists():
            raw = json.loads(_SEED.read_text(encoding="utf-8"))

        if not raw:
            return

        from datetime import datetime

        for e in raw:
            session.add(
                ListingRow(
                    id=e["id"],
                    seller_id=e.get("seller_id") or "seller-local",
                    kind=e.get("kind") or "product",
                    category=_seed_category(e),
                    title=e.get("title") or "이름 없음",
                    description=e.get("description") or "",
                    price=int(e.get("price") or 0),
                    emoji=e.get("emoji") or "🏷️",
                    location=e.get("location") or "",
                    stock=e.get("stock"),
                    max_guests=e.get("max_guests"),
                    created_at=e.get("created_at") or datetime.utcnow().isoformat(),
                    cover_image_url=e.get("cover_image_url"),
                    guide_json=_seed_guide_json(e),
                )
            )
        session.commit()
    bump_listings_version()


def _seed_guide_json(e: dict) -> str | None:
    g = e.get("guide")
    if isinstance(g, dict):
        import json

        return json.dumps(g, ensure_ascii=False)
    raw = e.get("guide_json")
    if raw and str(raw).strip():
        return str(raw)
    return None


def _seed_category(e: dict) -> str:
    c = (e.get("category") or "").strip()
    if c in ("experience", "rural", "fishing", "craft", "leisure", "lodging"):
        return c
    if e.get("kind") == "lodging":
        return "lodging"
    sid = e.get("seller_id") or ""
    if "fishing" in sid:
        return "fishing"
    if "craft" in sid:
        return "craft"
    if "leisure" in sid or "lodging" in sid:
        return "leisure"
    if "experience" in sid:
        return "experience"
    return "rural"


def _LEGACY_LISTINGS_exists_with_data() -> bool:
    if not _LEGACY_LISTINGS.exists():
        return False
    try:
        data = json.loads(_LEGACY_LISTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(data, list) and len(data) > 0


def _seed_orders_if_empty() -> None:
    with SessionLocal() as session:
        n = session.scalar(select(func.count()).select_from(OrderRow))
        if n and n > 0:
            return
        if not _LEGACY_ORDERS.exists():
            return
        try:
            raw = json.loads(_LEGACY_ORDERS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(raw, list):
            return
        for o in raw:
            pay = o.get("payment")
            session.add(
                OrderRow(
                    id=o["id"],
                    created_at=o.get("created_at") or "",
                    buyer_name=o.get("buyer_name") or "",
                    buyer_phone=o.get("buyer_phone") or "",
                    items_json=json.dumps(o.get("items") or [], ensure_ascii=False),
                    total=int(o.get("total") or 0),
                    payment_status=o.get("payment_status") or "pending",
                    payment_json=json.dumps(pay, ensure_ascii=False) if pay else None,
                )
            )
        session.commit()
