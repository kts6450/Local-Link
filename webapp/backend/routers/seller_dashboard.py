"""셀러 대시보드 — 매출·인기 상품·재고 알림."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from routers.auth import get_current_user
from services.listings_store import list_listings
from services.orders_store import list_orders_for_seller

router = APIRouter(prefix="/api/seller", tags=["seller-dashboard"])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    role = user.get("role")
    if role not in ("seller", "master"):
        raise HTTPException(status_code=403, detail="공급자 전용입니다.")

    seller_id = user.get("seller_id") or ""
    if role == "master":
        listings = list_listings()
        orders = []
        for l in listings:
            orders.extend([])
    else:
        listings = [l for l in list_listings() if l.get("seller_id") == seller_id]
        orders = list_orders_for_seller(seller_id)

    my_listing_ids = {l["id"] for l in listings}
    paid_orders = [o for o in orders if o.get("payment_status") == "paid"]

    revenue_total = 0
    units_total = 0
    by_listing: dict[str, dict] = defaultdict(lambda: {"units": 0, "revenue": 0})
    by_day: dict[str, int] = defaultdict(int)

    today = datetime.utcnow().date()
    days_window = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    for day in days_window:
        by_day[day] = 0

    for o in paid_orders:
        created = (o.get("created_at") or "")[:10]
        for it in o.get("items", []):
            lid = it.get("listing_id")
            if lid not in my_listing_ids:
                continue
            line = int(it.get("line_total") or (it.get("unit_price", 0) * it.get("quantity", 0)))
            qty = int(it.get("quantity") or 0)
            revenue_total += line
            units_total += qty
            by_listing[lid]["units"] += qty
            by_listing[lid]["revenue"] += line
            if created in by_day:
                by_day[created] += line

    today_str = today.isoformat()
    today_revenue = by_day.get(today_str, 0)
    today_order_count = sum(
        1 for o in orders if (o.get("created_at") or "")[:10] == today_str
    )
    pending_count = sum(
        1
        for o in orders
        if o.get("payment_status") == "paid"
        and (o.get("fulfillment_status") or "pending") in ("pending", "preparing")
    )
    by_listing_sales = {lid: v["units"] for lid, v in by_listing.items()}

    listing_index = {l["id"]: l for l in listings}
    top_items = sorted(
        [
            {
                "listing_id": lid,
                "title": listing_index.get(lid, {}).get("title", lid),
                "units": v["units"],
                "revenue": v["revenue"],
            }
            for lid, v in by_listing.items()
        ],
        key=lambda x: x["revenue"],
        reverse=True,
    )[:5]

    low_stock = [
        {
            "listing_id": l["id"],
            "title": l["title"],
            "stock": l.get("stock"),
        }
        for l in listings
        if l.get("kind") == "product"
        and l.get("stock") is not None
        and (l.get("stock") or 0) <= 5
    ]

    return {
        "listing_count": len(listings),
        "order_count": len(orders),
        "paid_count": len(paid_orders),
        "revenue_total": revenue_total,
        "units_total": units_total,
        "today_revenue": today_revenue,
        "today_order_count": today_order_count,
        "pending_count": pending_count,
        "sales_by_listing": by_listing_sales,
        "top_items": top_items,
        "low_stock": low_stock,
        "revenue_by_day": [{"date": d, "revenue": by_day[d]} for d in days_window],
    }
