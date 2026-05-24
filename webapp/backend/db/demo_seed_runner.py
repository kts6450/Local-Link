"""대규모 데모 시드 — 판매자 + 상품/숙박/체험 + 리뷰를 한 번에."""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from db.database import SessionLocal
from db.models import ListingRow, ReviewRow, UserRow
from services.auth_password import hash_password
from services.listing_events import bump_listings_version
from services.listing_package import _fallback_package, _guide_only

from .demo_data_experiences import EXPERIENCES
from .demo_data_lodgings import LODGINGS
from .demo_data_products import PRODUCTS
from .demo_data_reviews import (
    EXPERIENCE_REVIEWS_4,
    EXPERIENCE_REVIEWS_5,
    LODGING_REVIEWS_4,
    LODGING_REVIEWS_5,
    PRODUCT_REVIEWS_4,
    PRODUCT_REVIEWS_5,
    REVIEWER_NAMES,
)
from .demo_data_sellers import DEMO_PASSWORD, SELLERS
from .demo_images import cover_image_for, repair_all_listing_images


def _ensure_sellers(session) -> None:
    pwd_hash = hash_password(DEMO_PASSWORD)
    now = datetime.utcnow().isoformat()
    for s in SELLERS:
        exists = session.scalar(select(UserRow.id).where(UserRow.email == s["email"]))
        if exists:
            continue
        session.add(
            UserRow(
                id=s["id"],
                email=s["email"],
                password_hash=pwd_hash,
                role="seller",
                display_name=s["name"],
                seller_sector=s["sector"],
                seller_id=s["id"],
                created_at=now,
            )
        )
    session.commit()


def _add_listing(
    session,
    *,
    seller: str,
    kind: str,
    category: str,
    title: str,
    description: str,
    price: int,
    location: str,
    emoji: str,
    image: str,
    stock: int | None,
    max_guests: int | None,
    created_at: str,
    guide_json: str | None = None,
) -> str:
    lid = f"demo-{uuid.uuid4().hex[:10]}"
    session.add(
        ListingRow(
            id=lid,
            seller_id=seller,
            kind=kind,
            category=category,
            title=title,
            description=description,
            price=price,
            emoji=emoji,
            location=location,
            stock=stock,
            max_guests=max_guests,
            created_at=created_at,
            cover_image_url=image,
            guide_json=guide_json,
        )
    )
    return lid


def _demo_guide_json(
    *,
    kind: str,
    category: str,
    title: str,
    price: int,
    location: str,
) -> str:
    pkg = _fallback_package(kind, title, price, location, category)
    return json.dumps(_guide_only(pkg), ensure_ascii=False)


def _add_reviews(
    session,
    listing_id: str,
    pool_5: list[str],
    pool_4: list[str],
    *,
    base_dt: datetime,
    rng: random.Random,
) -> int:
    n = rng.randint(6, 22)
    fives = max(1, int(n * rng.uniform(0.7, 0.92)))
    fours = n - fives
    used_names: set[str] = set()
    for i in range(n):
        rating = 5 if i < fives else 4
        body = rng.choice(pool_5 if rating == 5 else pool_4)
        name = rng.choice(REVIEWER_NAMES)
        salt = 0
        while name in used_names and salt < 5:
            name = rng.choice(REVIEWER_NAMES)
            salt += 1
        used_names.add(name)
        days_ago = rng.randint(2, 220)
        created = base_dt - timedelta(days=days_ago, hours=rng.randint(0, 23))
        session.add(
            ReviewRow(
                id=f"rv-{uuid.uuid4().hex[:12]}",
                listing_id=listing_id,
                order_id=None,
                user_id=f"demo-buyer-{uuid.uuid4().hex[:8]}",
                user_name=name,
                rating=rating,
                body=body,
                created_at=created.isoformat(),
            )
        )
    return n


def seed_demo_marketplace(*, force: bool = False) -> dict[str, int]:
    """전체 마켓플레이스 데모 데이터 시드.

    force=False: listings 가 비어있을 때만.
    force=True: 기존 데모 회원의 listing/review 만 삭제 후 다시 시드.
    """
    rng = random.Random(20260524)
    counts = {"sellers": 0, "listings": 0, "reviews": 0}

    with SessionLocal() as session:
        existing = session.scalar(select(func.count()).select_from(ListingRow)) or 0
        if existing > 0 and not force:
            return counts

        if force and existing > 0:
            demo_seller_ids = [s["id"] for s in SELLERS]
            demo_listing_ids = [
                row.id for row in session.scalars(
                    select(ListingRow).where(ListingRow.seller_id.in_(demo_seller_ids))
                ).all()
            ]
            if demo_listing_ids:
                session.query(ReviewRow).filter(
                    ReviewRow.listing_id.in_(demo_listing_ids)
                ).delete(synchronize_session=False)
                session.query(ListingRow).filter(
                    ListingRow.id.in_(demo_listing_ids)
                ).delete(synchronize_session=False)
                session.commit()

        _ensure_sellers(session)
        counts["sellers"] = len(SELLERS)

        base_dt = datetime.utcnow()

        for offset, item in enumerate(PRODUCTS):
            created = (base_dt - timedelta(days=rng.randint(7, 240), hours=offset)).isoformat()
            cat = item.get("category") or "rural"
            title = item["title"]
            price = int(item["price"])
            location = item["location"]
            lid = _add_listing(
                session,
                seller=item["seller"],
                kind="product",
                category=cat,
                title=title,
                description=item["desc"],
                price=price,
                location=location,
                emoji=item.get("emoji") or "🛒",
                image=cover_image_for(
                    category=cat,
                    kind="product",
                    key=f"{item['seller']}-{title}",
                ),
                stock=int(item["stock"]),
                max_guests=None,
                created_at=created,
                guide_json=_demo_guide_json(
                    kind="product", category=cat, title=title, price=price, location=location
                ),
            )
            counts["listings"] += 1
            counts["reviews"] += _add_reviews(
                session, lid, PRODUCT_REVIEWS_5, PRODUCT_REVIEWS_4, base_dt=base_dt, rng=rng,
            )

        for offset, item in enumerate(LODGINGS):
            created = (base_dt - timedelta(days=rng.randint(7, 240), hours=offset)).isoformat()
            title = item["title"]
            price = int(item["price"])
            location = item["location"]
            lid = _add_listing(
                session,
                seller=item["seller"],
                kind="lodging",
                category="lodging",
                title=title,
                description=item["desc"],
                price=price,
                location=location,
                emoji=item.get("emoji") or "🏠",
                image=cover_image_for(
                    category="lodging",
                    kind="lodging",
                    key=f"{item['seller']}-{title}",
                ),
                stock=None,
                max_guests=int(item.get("max_guests") or 4),
                created_at=created,
                guide_json=_demo_guide_json(
                    kind="lodging", category="lodging", title=title, price=price, location=location
                ),
            )
            counts["listings"] += 1
            counts["reviews"] += _add_reviews(
                session, lid, LODGING_REVIEWS_5, LODGING_REVIEWS_4, base_dt=base_dt, rng=rng,
            )

        for offset, item in enumerate(EXPERIENCES):
            created = (base_dt - timedelta(days=rng.randint(7, 240), hours=offset)).isoformat()
            title = item["title"]
            price = int(item["price"])
            location = item["location"]
            lid = _add_listing(
                session,
                seller=item["seller"],
                kind="product",
                category="experience",
                title=title,
                description=item["desc"],
                price=price,
                location=location,
                emoji=item.get("emoji") or "🎒",
                image=cover_image_for(
                    category="experience",
                    kind="product",
                    key=f"{item['seller']}-{title}",
                ),
                stock=int(item["stock"]),
                max_guests=None,
                created_at=created,
                guide_json=_demo_guide_json(
                    kind="product",
                    category="experience",
                    title=title,
                    price=price,
                    location=location,
                ),
            )
            counts["listings"] += 1
            counts["reviews"] += _add_reviews(
                session, lid, EXPERIENCE_REVIEWS_5, EXPERIENCE_REVIEWS_4, base_dt=base_dt, rng=rng,
            )

        session.commit()

    bump_listings_version()
    return counts


def repair_demo_guides() -> int:
    """guide_json이 비어 있는 데모 listing에 이용안내 템플릿 채우기."""
    from services.listing_events import bump_listings_version

    n = 0
    with SessionLocal() as session:
        rows = session.scalars(
            select(ListingRow).where(ListingRow.id.like("demo-%"))
        ).all()
        for row in rows:
            if row.guide_json and str(row.guide_json).strip():
                continue
            cat = getattr(row, "category", None) or ("lodging" if row.kind == "lodging" else "rural")
            row.guide_json = _demo_guide_json(
                kind=row.kind,
                category=cat,
                title=row.title or "",
                price=int(row.price or 0),
                location=row.location or "",
            )
            n += 1
        session.commit()
    if n:
        bump_listings_version()
    return n


def repair_demo_images() -> int:
    """기존 DB listing cover URL을 검증 풀로 교체 (재시드 없이)."""
    from services.listing_events import bump_listings_version

    with SessionLocal() as session:
        n = repair_all_listing_images(session)
        session.commit()
    if n:
        bump_listings_version()
    return n


__all__ = ["seed_demo_marketplace", "repair_demo_images", "repair_demo_guides"]
