from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class ListingRow(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    seller_id: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    # experience | rural | fishing | craft | leisure | lodging
    category: Mapped[str] = mapped_column(String(24), index=True, default="rural")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)
    emoji: Mapped[str] = mapped_column(String(8), default="🏷️")
    location: Mapped[str] = mapped_column(String(500), default="")
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_guests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    # 저장 경로 또는 URL — 비어 있으면 프론트가 Unsplash 풀 사용
    cover_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # 루플형 상품정보·이용안내 (highlights, steps, nearby, refund 등)
    guide_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 가격·용량 옵션 (예: [{"label":"100g","price":13000}, ...]). 없으면 단일가.
    variants_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 상세 정보 (단위·원산지·생산자·유통기한·보관방법 등 자유 키-값). JSON 객체.
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), index=True)  # consumer | seller
    display_name: Mapped[str] = mapped_column(String(100))
    seller_sector: Mapped[str | None] = mapped_column(String(24), nullable=True)
    seller_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    buyer_id: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    buyer_name: Mapped[str] = mapped_column(String(100))
    buyer_phone: Mapped[str] = mapped_column(String(30))
    items_json: Mapped[str] = mapped_column(Text)
    total: Mapped[int] = mapped_column(Integer)
    payment_status: Mapped[str] = mapped_column(String(20))
    # 주문 상태: pending(결제전) | preparing(준비중) | shipping(배송중) | completed(완료) | cancelled(취소)
    fulfillment_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    # 숙박 예약: YYYY-MM-DD (체크인 포함, 체크아웃 제외)
    stay_start: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    stay_end: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    payment_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class ListingPhotoRow(Base):
    __tablename__ = "listing_photos"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(48), index=True)
    url: Mapped[str] = mapped_column(String(2000))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))


class ReviewRow(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    listing_id: Mapped[str] = mapped_column(String(48), index=True)
    order_id: Mapped[str | None] = mapped_column(String(48), index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String(48), index=True)
    user_name: Mapped[str] = mapped_column(String(100))
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(40), index=True)
