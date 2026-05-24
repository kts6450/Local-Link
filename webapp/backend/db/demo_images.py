"""검증된 커버 이미지 URL — HEAD 200 확인된 Unsplash만 사용."""
from __future__ import annotations

from sqlalchemy import select

from db.models import ListingRow

_SUFFIX = "?auto=format&fit=crop&w=1600&q=85"

# 특산·농수산·공예 (kind=product, category!=experience)
PRODUCT_POOL: list[str] = [
    f"https://images.unsplash.com/photo-1586201375761-83865001e31c{_SUFFIX}",  # rice
    f"https://images.unsplash.com/photo-1568702846914-96b305d2aaeb{_SUFFIX}",  # apple
    f"https://images.unsplash.com/photo-1606851094291-6efae152bb87{_SUFFIX}",  # persimmon
    f"https://images.unsplash.com/photo-1576092768241-dec231879fc3{_SUFFIX}",  # tea
    f"https://images.unsplash.com/photo-1597481499750-3e6b22637e12{_SUFFIX}",  # tea cup
    f"https://images.unsplash.com/photo-1547514701-42782101795e{_SUFFIX}",  # citrus
    f"https://images.unsplash.com/photo-1544025162-d76694265947{_SUFFIX}",  # fish dish
    f"https://images.unsplash.com/photo-1562967914-608f82629710{_SUFFIX}",  # seafood
    f"https://images.unsplash.com/photo-1631452180519-c014fe946bc7{_SUFFIX}",  # sauce
    f"https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6{_SUFFIX}",  # juice
    f"https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9{_SUFFIX}",  # matcha
    f"https://images.unsplash.com/photo-1559339352-11d035aa65de{_SUFFIX}",  # seafood market
    f"https://images.unsplash.com/photo-1504674900247-0877df9cc836{_SUFFIX}",  # food
    f"https://images.unsplash.com/photo-1455390582262-044cdead277a{_SUFFIX}",  # letter/craft
    f"https://images.unsplash.com/photo-1521478706270-f2e33c203d95{_SUFFIX}",  # lamp/craft
    f"https://images.unsplash.com/photo-1543589077-47d81606c1bf{_SUFFIX}",  # fan/craft
]

LODGING_POOL: list[str] = [
    f"https://images.unsplash.com/photo-1568084680786-a84f91d1153c{_SUFFIX}",  # ocean view
    f"https://images.unsplash.com/photo-1505691938895-1758d7feb511{_SUFFIX}",  # living room
    f"https://images.unsplash.com/photo-1600585154340-be6161a56a0c{_SUFFIX}",  # hanok
    f"https://images.unsplash.com/photo-1582719478250-c89cae4dc85b{_SUFFIX}",  # terrace view
    f"https://images.unsplash.com/photo-1520250497591-112f2f40a3f4{_SUFFIX}",  # cabin
    f"https://images.unsplash.com/photo-1487730116645-74489c95b41b{_SUFFIX}",  # glamping
    f"https://images.unsplash.com/photo-1564013799919-ab600027ffc6{_SUFFIX}",  # beach condo
    f"https://images.unsplash.com/photo-1566073771259-6a8506099945{_SUFFIX}",  # hotel room
    f"https://images.unsplash.com/photo-1571896349842-33c89424de2d{_SUFFIX}",  # pool villa
    f"https://images.unsplash.com/photo-1582719508461-905c673771fd{_SUFFIX}",  # resort
    f"https://images.unsplash.com/photo-1611892440504-42a792e24d32{_SUFFIX}",  # guesthouse
    f"https://images.unsplash.com/photo-1568605114967-8130f3a36994{_SUFFIX}",  # rooftop
    f"https://images.unsplash.com/photo-1602002418082-a4443e081dd1{_SUFFIX}",  # harbor
    f"https://images.unsplash.com/photo-1551918120-9739cb430c6d{_SUFFIX}",  # beach house
    f"https://images.unsplash.com/photo-1505873242700-f289a29e1e0f{_SUFFIX}",  # sunset stay
    f"https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9{_SUFFIX}",  # pool
]

EXPERIENCE_POOL: list[str] = [
    f"https://images.unsplash.com/photo-1500382017468-9049fed747ef{_SUFFIX}",  # farm field
    f"https://images.unsplash.com/photo-1466692476868-aef1dfb1e735{_SUFFIX}",  # bamboo forest
    f"https://images.unsplash.com/photo-1500380804539-4e1e8c1e7118{_SUFFIX}",  # coastal walk
    f"https://images.unsplash.com/photo-1500916434205-0c77489c6cf7{_SUFFIX}",  # surfing
    f"https://images.unsplash.com/photo-1502680390469-be75c86b636f{_SUFFIX}",  # surf lesson
    f"https://images.unsplash.com/photo-1530549387789-4c1017266635{_SUFFIX}",  # paddleboard
    f"https://images.unsplash.com/photo-1559827260-dc66d52bef19{_SUFFIX}",  # diving/sea
    f"https://images.unsplash.com/photo-1551776235-dde6d482980b{_SUFFIX}",  # beach activity
    f"https://images.unsplash.com/photo-1469854523086-cc02fe5d8800{_SUFFIX}",  # road trip
    f"https://images.unsplash.com/photo-1564501049412-61c2a3083791{_SUFFIX}",  # harbor tour
    f"https://images.unsplash.com/photo-1532339142463-fd0a8979791a{_SUFFIX}",  # camping
    f"https://images.unsplash.com/photo-1582719508461-905c673771fd{_SUFFIX}",  # farm animals
]


def _hash_key(key: str) -> int:
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def cover_image_for(*, category: str, kind: str, key: str) -> str:
    """카테고리별 검증된 풀에서 결정적으로 URL 선택."""
    if kind == "lodging":
        pool = LODGING_POOL
    elif category == "experience":
        pool = EXPERIENCE_POOL
    else:
        pool = PRODUCT_POOL
    return pool[_hash_key(key) % len(pool)]


def repair_all_listing_images(session) -> int:
    """DB에 저장된 깨진 cover URL을 검증 풀로 일괄 교체."""
    rows = session.scalars(select(ListingRow)).all()
    n = 0
    for row in rows:
        cat = getattr(row, "category", None) or ("lodging" if row.kind == "lodging" else "rural")
        new_url = cover_image_for(category=cat, kind=row.kind, key=row.id)
        if row.cover_image_url != new_url:
            row.cover_image_url = new_url
            n += 1
    return n
