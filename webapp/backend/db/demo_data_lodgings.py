"""데모 숙박 (kind=lodging, category=lodging).

모든 image는 실제 사진 내용을 육안으로 확인한 Unsplash URL.
"""
from __future__ import annotations

_S = "?auto=format&fit=crop&w=1600&q=85"


def _img(pid: str) -> str:
    return f"https://images.unsplash.com/photo-{pid}{_S}"


LODGINGS: list[dict] = [
    {"seller": "seller-hansol", "title": "[강릉] 안목 바다뷰 단독 스테이",
     "price": 185000, "location": "강원 강릉시", "emoji": "🌊", "max_guests": 4,
     "image": _img("1609602126247-4ab7188b4aa1"),  # 바다뷰 객실
     "desc": "통창 너머로 바다가 펼쳐지는 단독 스테이. 안목 카페거리 도보 3분."},
    {"seller": "seller-yejin", "title": "[남해] 돌담마을 한옥 펜션",
     "price": 220000, "location": "경남 남해군", "emoji": "🏯", "max_guests": 5,
     "image": _img("1601721826401-c5e789be0be6"),  # 한옥 단청 지붕
     "desc": "돌담길 끝의 작은 한옥. 마당에서 별을 보며 차를 마실 수 있어요."},
    {"seller": "seller-doyoon", "title": "[평창] 해발 700m 숲속 통나무집",
     "price": 195000, "location": "강원 평창군", "emoji": "🪵", "max_guests": 6,
     "image": _img("1570793005386-840846445fed"),  # 숲속 통나무집
     "desc": "전나무 숲에 둘러싸인 통나무집. 마당 모닥불·계곡 물놀이 가능."},
]
