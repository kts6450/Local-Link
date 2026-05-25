"""데모 체험·클래스 (kind=product, category=experience).

모든 image는 실제 사진 내용을 육안으로 확인한 Unsplash URL.
"""
from __future__ import annotations

_S = "?auto=format&fit=crop&w=1600&q=85"


def _img(pid: str) -> str:
    return f"https://images.unsplash.com/photo-{pid}{_S}"


EXPERIENCES: list[dict] = [
    {"seller": "seller-jaeyoon", "title": "[보성] 차밭 다도 클래스",
     "price": 45000, "location": "전남 보성군", "emoji": "🍵", "stock": 12,
     "image": _img("1567922045116-2a00fae2ed03"),  # 찻잎 사이 찻잔
     "desc": "보성 차밭을 거닐며 우전·황차를 우려 마시는 다도 클래스. 약 2시간."},
    {"seller": "seller-changmin", "title": "[양양] 서핑 입문 클래스 (3시간)",
     "price": 65000, "location": "강원 양양군", "emoji": "🏄", "stock": 8,
     "image": _img("1616141893496-fbc65370493e"),  # 파도
     "desc": "죽도해변 서핑 입문. 보드·슈트 대여 포함, 강사 1:3 소규모 진행."},
    {"seller": "seller-yoonseo", "title": "[담양] 대숲 산책 + 죽순밥",
     "price": 42000, "location": "전남 담양군", "emoji": "🎋", "stock": 14,
     "image": _img("1532920161727-344adb090f7f"),  # 대숲
     "desc": "죽녹원 대숲 산책 후 죽순밥 한 상. 5월엔 죽순 캐기 체험도 함께."},
]
