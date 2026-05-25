"""데모 상품 — 농수산물·가공품·공예품 (kind=product, category!=experience).

모든 image는 실제 사진 내용을 육안으로 확인한 Unsplash URL.
새 상품을 추가할 때도 반드시 사진을 받아서 내용이 제목과 맞는지 확인할 것.
"""
from __future__ import annotations

_S = "?auto=format&fit=crop&w=1600&q=85"


def _img(pid: str) -> str:
    return f"https://images.unsplash.com/photo-{pid}{_S}"


PRODUCTS: list[dict] = [
    {"seller": "seller-jiwoo", "category": "rural", "title": "[김제] 올해 햅쌀 10kg · 직도정",
     "price": 42000, "location": "전북 김제시", "emoji": "🌾", "stock": 60,
     "image": _img("1586201375761-83865001e31c"),  # 쌀알
     "desc": "무농약에 가까운 농법으로 키운 들녘쌀. 도정 직후라 향이 살아 있어 밥맛이 다릅니다."},
    {"seller": "seller-hyeona", "category": "rural", "title": "[청송] 부사 사과 5kg 가정용",
     "price": 32000, "location": "경북 청송군", "emoji": "🍎", "stock": 80,
     "image": _img("1582927338750-66a116047612"),  # 빨간 사과 더미
     "desc": "산지 직송 청송 부사. 당도 14브릭스 이상만 골라서 보내드려요."},
    {"seller": "seller-jaeyoon", "category": "rural", "title": "[보성] 우전 녹차 100g",
     "price": 35000, "location": "전남 보성군", "emoji": "🍵", "stock": 50,
     "image": _img("1582650859079-ee63913ecb84"),  # 녹차잎
     "desc": "곡우 직전 첫 잎만 따서 만든 우전. 부드러운 첫 향이 매력입니다."},
    {"seller": "seller-suji", "category": "rural", "title": "[제주] 노지 감귤 5kg",
     "price": 26000, "location": "제주 서귀포시", "emoji": "🍊", "stock": 90,
     "image": _img("1547514701-42782101795e"),  # 감귤
     "desc": "햇살 오래 받은 노지 감귤. 새콤달콤 균형이 좋아 아이들 간식으로 인기."},
    {"seller": "seller-jiwoo", "category": "rural", "title": "[김제] 농가 포기김치 3kg",
     "price": 28000, "location": "전북 김제시", "emoji": "🥬", "stock": 30,
     "image": _img("1708388064278-707e85eaddc0"),  # 배추김치
     "desc": "직접 기른 배추로 담근 농가 포기김치. 젓갈 듬뿍, 깊은 감칠맛."},
    {"seller": "seller-minhyuk", "category": "fishing", "title": "[포항] 자반 고등어 6손",
     "price": 26000, "location": "경북 포항시", "emoji": "🐟", "stock": 60,
     "image": _img("1600699899970-b1c9fadd8f9e"),  # 구운 고등어
     "desc": "잡은 직후 염장한 자반 고등어. 굽기만 하면 반찬 한 그릇."},
    {"seller": "seller-yoonseo", "category": "craft", "title": "[담양] 대나무 도시락 통",
     "price": 45000, "location": "전남 담양군", "emoji": "🎋", "stock": 20,
     "image": _img("1633878353628-5fc8b983325c"),  # 대나무 용기 세트
     "desc": "통대나무를 다듬어 만든 도시락. 쓸수록 손때 묻으며 윤이 납니다."},
    {"seller": "seller-yoonseo", "category": "craft", "title": "[담양] 대나무 차 받침 4종",
     "price": 28000, "location": "전남 담양군", "emoji": "🍵", "stock": 35,
     "image": _img("1667060034726-6b4c4c6eb385"),  # 대나무 찻잔 받침
     "desc": "찻자리에 어울리는 대나무 받침 4종 세트. 손잡이까지 한 사람이 만듭니다."},
]
