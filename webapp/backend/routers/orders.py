"""주문 + 모의 결제 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from routers.auth import get_current_user
from services.orders_store import (
    card_pay_demo,
    create_order,
    get_order,
    list_orders,
    list_orders_for_buyer,
    list_orders_for_seller,
    mock_pay,
    set_fulfillment_status,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderItemIn(BaseModel):
    listing_id: str
    quantity: int = Field(ge=1, le=999)
    stay_start: str | None = Field(default=None, max_length=10)
    stay_end: str | None = Field(default=None, max_length=10)


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)
    buyer_name: str = Field(min_length=1, max_length=100)
    buyer_phone: str = Field(min_length=5, max_length=30)
    stay_start: str | None = Field(default=None, max_length=10)
    stay_end: str | None = Field(default=None, max_length=10)


class FulfillmentUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in ("preparing", "shipping", "completed", "cancelled"):
            raise ValueError("invalid status")
        return v


@router.get("/recent")
def recent_orders(limit: int = 8, user: dict = Depends(get_current_user)):
    """최근 주문 — 셀러: 본인 상품 주문, 마스터: 전체, 구매자: 본인."""
    n = max(1, min(limit, 50))
    role = user.get("role")
    if role == "master":
        return list_orders()[:n]
    if role == "seller":
        return list_orders_for_seller(user.get("seller_id") or "")[:n]
    return list_orders_for_buyer(user.get("id") or "")[:n]


@router.get("/mine")
def my_orders(user: dict = Depends(get_current_user)):
    """구매자: 본인 주문 내역."""
    if user.get("role") not in ("consumer", "master"):
        raise HTTPException(status_code=403, detail="구매자만 조회할 수 있습니다.")
    return list_orders_for_buyer(user.get("id") or "")


@router.get("/seller")
def seller_orders(user: dict = Depends(get_current_user)):
    """셀러: 본인 상품 주문."""
    if user.get("role") == "master":
        return list_orders()
    if user.get("role") != "seller":
        raise HTTPException(status_code=403, detail="공급자 전용입니다.")
    return list_orders_for_seller(user.get("seller_id") or "")


@router.post("")
def post_order(body: OrderCreate, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("consumer", "master"):
        raise HTTPException(status_code=403, detail="구매자 로그인이 필요합니다.")
    try:
        return create_order(
            items=[i.model_dump() for i in body.items],
            buyer_name=body.buyer_name,
            buyer_phone=body.buyer_phone,
            buyer_id=user.get("id"),
            stay_start=body.stay_start,
            stay_end=body.stay_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{order_id}/mock-pay")
def pay_mock(order_id: str, user: dict = Depends(get_current_user)):
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if user.get("role") == "consumer" and order.get("buyer_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="본인 주문만 결제할 수 있습니다.")
    try:
        return mock_pay(order_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{order_id}/card-pay")
def pay_card_demo(order_id: str, user: dict = Depends(get_current_user)):
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    if user.get("role") == "consumer" and order.get("buyer_id") != user.get("id"):
        raise HTTPException(status_code=403, detail="본인 주문만 결제할 수 있습니다.")
    try:
        return card_pay_demo(order_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{order_id}/fulfillment")
def update_fulfillment(
    order_id: str,
    body: FulfillmentUpdate,
    user: dict = Depends(get_current_user),
):
    """셀러가 본인 상품이 포함된 주문의 진행 상태를 바꿉니다."""
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    role = user.get("role")
    if role == "master":
        pass
    elif role == "seller":
        seller_id = user.get("seller_id") or ""
        from services.listings_store import get_listing

        owns_any = False
        for it in order.get("items", []):
            listing = get_listing(it.get("listing_id"))
            if listing and listing.get("seller_id") == seller_id:
                owns_any = True
                break
        if not owns_any:
            raise HTTPException(status_code=403, detail="이 주문의 셀러가 아닙니다.")
    else:
        raise HTTPException(status_code=403, detail="공급자만 상태를 바꿀 수 있습니다.")
    try:
        return set_fulfillment_status(order_id, body.status)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
