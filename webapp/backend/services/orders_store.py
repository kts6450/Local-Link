"""주문 + 결제 — SQLite (목록과 동일 DB).

운영 규칙:
- 가용성(재고·예약)은 «결제 완료(미취소)» 주문 기준으로 계산한다.
- 상품: stock 컬럼이 실재고 → 결제 시 원자적 조건부 차감, 취소 시 복구.
- 숙박: 1박 단위 단독 예약 → 날짜 구간 겹침 금지.
- 체험: stock = «날짜별 정원» → 그 날짜의 확정 예약 합이 정원을 넘으면 거부(차감 안 함).
- 검증·확보는 결제 시점에 수행해 초과판매·중복예약을 막는다(주문 생성은 사전 검증만).
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import date, datetime

from sqlalchemy import select, update

from db.database import SessionLocal
from db.models import ListingRow, OrderRow
from services.listing_events import bump_listings_version
from services.listings_store import get_listing

_VALID_FULFILLMENT = ("pending", "preparing", "shipping", "completed", "cancelled")


def _row_to_order_dict(row: OrderRow) -> dict:
    items = json.loads(row.items_json) if row.items_json else []
    payment = json.loads(row.payment_json) if row.payment_json else None
    return {
        "id": row.id,
        "created_at": row.created_at,
        "buyer_id": row.buyer_id,
        "buyer_name": row.buyer_name,
        "buyer_phone": row.buyer_phone,
        "items": items,
        "total": row.total,
        "payment_status": row.payment_status,
        "fulfillment_status": row.fulfillment_status or "pending",
        "stay_start": row.stay_start,
        "stay_end": row.stay_end,
        "payment": payment,
    }


def list_orders() -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(select(OrderRow).order_by(OrderRow.created_at.desc())).all()
        return [_row_to_order_dict(r) for r in rows]


def list_orders_for_buyer(buyer_id: str) -> list[dict]:
    if not buyer_id:
        return []
    with SessionLocal() as session:
        rows = session.scalars(
            select(OrderRow)
            .where(OrderRow.buyer_id == buyer_id)
            .order_by(OrderRow.created_at.desc())
        ).all()
        return [_row_to_order_dict(r) for r in rows]


def list_orders_for_seller(seller_id: str) -> list[dict]:
    """주문 라인 중 하나라도 해당 셀러 상품이 있으면 포함."""
    if not seller_id:
        return []

    out: list[dict] = []
    for o in list_orders():
        for it in o.get("items", []):
            lid = it.get("listing_id")
            listing = get_listing(lid) if lid else None
            if listing and listing.get("seller_id") == seller_id:
                out.append(o)
                break
    return out


def get_order(order_id: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(OrderRow, order_id)
        return _row_to_order_dict(row) if row else None


# ---------------------------------------------------------------------------
# 가용성 계산 — 결제 완료(미취소) 주문 기준
# ---------------------------------------------------------------------------
def _active_items(session) -> list[dict]:
    """결제 완료·미취소 주문의 라인 (라인별 날짜 포함, 없으면 주문 날짜로 폴백)."""
    rows = session.scalars(
        select(OrderRow).where(OrderRow.payment_status == "paid")
    ).all()
    out: list[dict] = []
    for r in rows:
        if (r.fulfillment_status or "") == "cancelled":
            continue
        try:
            items = json.loads(r.items_json or "[]")
        except ValueError:
            items = []
        for it in items:
            out.append(
                {
                    "listing_id": it.get("listing_id"),
                    "quantity": int(it.get("quantity") or 0),
                    "stay_start": it.get("stay_start") or r.stay_start,
                    "stay_end": it.get("stay_end") or r.stay_end,
                }
            )
    return out


def _ranges_overlap(s1: str, e1: str, s2: str, e2: str) -> bool:
    # 반-열림 구간 [start, end) 겹침
    return not (e1 <= s2 or s1 >= e2)


def _lodging_conflict(session, listing_id: str, stay_start: str, stay_end: str) -> bool:
    if not (stay_start and stay_end and stay_start < stay_end):
        return False
    for it in _active_items(session):
        if it["listing_id"] != listing_id:
            continue
        s, e = it["stay_start"], it["stay_end"]
        if s and e and _ranges_overlap(stay_start, stay_end, s, e):
            return True
    return False


def _experience_booked_qty(session, listing_id: str, day: str) -> int:
    if not day:
        return 0
    n = 0
    for it in _active_items(session):
        if it["listing_id"] == listing_id and it["stay_start"] == day:
            n += it["quantity"]
    return n


def _check_item_available(session, listing: dict, qty: int, stay_start, stay_end) -> None:
    """예약/재고 가용성 검증 — 부족하면 ValueError. (차감은 하지 않음)"""
    kind = listing.get("kind")
    cat = listing.get("category")
    title = listing.get("title") or "상품"
    if kind == "lodging":
        if not (stay_start and stay_end):
            raise ValueError(f"숙박은 체크인·체크아웃 날짜가 필요합니다: {title}")
        if _lodging_conflict(session, listing["id"], stay_start, stay_end):
            raise ValueError(f"이미 예약된 날짜입니다: {title}")
    elif cat == "experience":
        if not stay_start:
            raise ValueError(f"체험은 예약 날짜가 필요합니다: {title}")
        cap = listing.get("stock")
        if cap is not None:
            booked = _experience_booked_qty(session, listing["id"], stay_start)
            if booked + qty > cap:
                remain = max(0, cap - booked)
                raise ValueError(f"해당 날짜 정원이 부족합니다(남은 자리 {remain}명): {title}")
    else:  # product
        stock = listing.get("stock")
        if stock is not None and qty > stock:
            raise ValueError(f"재고가 부족합니다(남은 수량 {stock}개): {title}")


def listing_availability(listing: dict) -> dict:
    """캘린더용 — 예약 불가 날짜 + (체험) 정원·날짜별 예약수."""
    lid = listing["id"]
    kind = listing.get("kind")
    cat = listing.get("category")
    today = date.today().isoformat()
    with SessionLocal() as session:
        acts = _active_items(session)

    if kind == "lodging":
        booked: set[str] = set()
        for it in acts:
            if it["listing_id"] != lid:
                continue
            s, e = it["stay_start"], it["stay_end"]
            if not (s and e) or e < today:
                continue
            cur = date.fromisoformat(s)
            end = date.fromisoformat(e)
            while cur < end:
                booked.add(cur.isoformat())
                cur = date.fromordinal(cur.toordinal() + 1)
        return {"booked_dates": sorted(booked), "capacity": None, "booked_counts": {}}

    if cat == "experience":
        cap = listing.get("stock")
        counts: dict[str, int] = {}
        for it in acts:
            if it["listing_id"] != lid:
                continue
            d = it["stay_start"]
            if not d or d < today:
                continue
            counts[d] = counts.get(d, 0) + it["quantity"]
        full = (
            sorted([d for d, c in counts.items() if c >= cap]) if cap is not None else []
        )
        return {"booked_dates": full, "capacity": cap, "booked_counts": counts}

    return {"booked_dates": [], "capacity": None, "booked_counts": {}}


def set_fulfillment_status(order_id: str, status: str) -> dict:
    if status not in _VALID_FULFILLMENT:
        raise ValueError(f"invalid status: {status}")
    restored = False
    with SessionLocal() as session:
        row = session.get(OrderRow, order_id)
        if row is None:
            raise KeyError(order_id)
        prev = row.fulfillment_status or "pending"
        # 결제 완료 주문을 취소로 전환할 때만 상품 재고를 1회 복구.
        if status == "cancelled" and prev != "cancelled" and row.payment_status == "paid":
            try:
                items = json.loads(row.items_json or "[]")
            except ValueError:
                items = []
            for it in items:
                lid = it.get("listing_id")
                qty = int(it.get("quantity") or 0)
                listing = get_listing(lid) if lid else None
                if (
                    listing
                    and listing.get("kind") == "product"
                    and listing.get("stock") is not None
                    and qty > 0
                ):
                    session.execute(
                        update(ListingRow)
                        .where(ListingRow.id == lid)
                        .values(stock=ListingRow.stock + qty)
                    )
                    restored = True
        row.fulfillment_status = status
        session.commit()
        result = _row_to_order_dict(row)
    if restored:
        bump_listings_version()
    return result


def create_order(
    *,
    items: list[dict],
    buyer_name: str,
    buyer_phone: str,
    buyer_id: str | None = None,
    stay_start: str | None = None,
    stay_end: str | None = None,
) -> dict:
    """주문 생성 — 라인별 예약일 저장 + 사전 가용성 검증(확정은 결제 시)."""
    lines: list[dict] = []
    total = 0
    with SessionLocal() as session:
        for it in items:
            lid = it.get("listing_id")
            qty = int(it.get("quantity") or 1)
            i_start = it.get("stay_start") or stay_start
            i_end = it.get("stay_end") or stay_end
            listing = get_listing(lid) if lid else None
            if not listing:
                raise ValueError(f"상품을 찾을 수 없습니다: {lid}")
            _check_item_available(session, listing, qty, i_start, i_end)
            unit = int(listing.get("price") or 0)
            sub = unit * qty
            total += sub
            lines.append(
                {
                    "listing_id": lid,
                    "title": listing.get("title"),
                    "kind": listing.get("kind"),
                    "category": listing.get("category"),
                    "quantity": qty,
                    "unit_price": unit,
                    "line_total": sub,
                    "stay_start": i_start,
                    "stay_end": i_end,
                }
            )

        # 주문 단위 날짜 = 첫 예약 라인 (구버전 표시 호환).
        first_dated = next((l for l in lines if l["stay_start"]), None)
        o_start = first_dated["stay_start"] if first_dated else stay_start
        o_end = first_dated["stay_end"] if first_dated else stay_end

        oid = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        row = OrderRow(
            id=oid,
            created_at=datetime.utcnow().isoformat(),
            buyer_id=buyer_id,
            buyer_name=buyer_name.strip(),
            buyer_phone=buyer_phone.strip(),
            items_json=json.dumps(lines, ensure_ascii=False),
            total=total,
            payment_status="pending",
            fulfillment_status="pending",
            stay_start=o_start,
            stay_end=o_end,
            payment_json=None,
        )
        session.add(row)
        session.commit()
        return _row_to_order_dict(row)


def _complete_pay(order_id: str, method: str, message: str, txn_prefix: str) -> dict:
    """결제 확정 — 재고/예약을 원자적으로 검증·확보 후 paid 처리."""
    with SessionLocal() as session:
        row = session.get(OrderRow, order_id)
        if row is None:
            raise KeyError(order_id)
        if row.payment_status == "paid":
            return _row_to_order_dict(row)  # 멱등

        try:
            items = json.loads(row.items_json or "[]")
        except ValueError:
            items = []

        stock_changed = False
        for it in items:
            lid = it.get("listing_id")
            qty = int(it.get("quantity") or 0)
            listing = get_listing(lid) if lid else None
            if not listing:
                raise ValueError(f"상품을 찾을 수 없습니다: {lid}")
            kind = listing.get("kind")
            cat = listing.get("category")
            i_start = it.get("stay_start") or row.stay_start
            i_end = it.get("stay_end") or row.stay_end
            title = listing.get("title") or "상품"

            if kind == "lodging":
                if not (i_start and i_end):
                    raise ValueError(f"예약 날짜가 없습니다: {title}")
                if _lodging_conflict(session, lid, i_start, i_end):
                    raise ValueError(f"결제 중 다른 예약이 확정됐습니다: {title}")
            elif cat == "experience":
                cap = listing.get("stock")
                if cap is not None:
                    booked = _experience_booked_qty(session, lid, i_start)
                    if booked + qty > cap:
                        raise ValueError(f"결제 중 정원이 찼습니다: {title}")
            else:  # product — 조건부 원자적 차감
                stock = listing.get("stock")
                if stock is not None:
                    res = session.execute(
                        update(ListingRow)
                        .where(ListingRow.id == lid, ListingRow.stock >= qty)
                        .values(stock=ListingRow.stock - qty)
                    )
                    if res.rowcount == 0:
                        raise ValueError(f"재고가 부족합니다: {title}")
                    stock_changed = True

        txn = f"{txn_prefix}-{secrets.token_hex(6).upper()}"
        row.payment_status = "paid"
        if row.fulfillment_status in (None, "pending"):
            row.fulfillment_status = "preparing"
        row.payment_json = json.dumps(
            {
                "method": method,
                "transaction_id": txn,
                "paid_at": datetime.utcnow().isoformat(),
                "message": message,
            },
            ensure_ascii=False,
        )
        session.commit()
        result = _row_to_order_dict(row)
    if stock_changed:
        bump_listings_version()
    return result


def mock_pay(order_id: str) -> dict:
    return _complete_pay(
        order_id,
        "mock_card",
        "(데모) 실제 결제는 이루어지지 않았습니다.",
        "MOCK-TXN",
    )


def card_pay_demo(order_id: str) -> dict:
    return _complete_pay(
        order_id,
        "card",
        "(시연) 카드·간편결제 승인 시뮬레이션입니다. 실제 청구는 없습니다.",
        "CARD-TXN",
    )
