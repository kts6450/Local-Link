"""데모 판매자 회원 — 모두 비밀번호는 demo1234! (시연용)."""
from __future__ import annotations

DEMO_PASSWORD = "demo1234!"

SELLERS: list[dict] = [
    {"id": "seller-jiwoo", "email": "jiwoo@locallink.kr", "name": "김지우 (해담농장)",
     "sector": "rural", "tagline": "전북 김제 들녘에서 햅쌀과 잡곡을 키웁니다."},
    {"id": "seller-hyeona", "email": "hyeona@locallink.kr", "name": "박현아 (청송사과집)",
     "sector": "rural", "tagline": "청송 사과·곶감, 직접 따서 보내드려요."},
    {"id": "seller-jaeyoon", "email": "jaeyoon@locallink.kr", "name": "이재윤 (보성다원)",
     "sector": "rural", "tagline": "전남 보성에서 3대째 차밭을 가꿉니다."},
    {"id": "seller-suji", "email": "suji@locallink.kr", "name": "정수지 (제주귤마당)",
     "sector": "rural", "tagline": "제주 서귀포 노지 감귤·한라봉."},
    {"id": "seller-minhyuk", "email": "minhyuk@locallink.kr", "name": "조민혁 (포항물회집)",
     "sector": "fishing", "tagline": "포항 구룡포에서 잡은 활어, 당일 손질."},
    {"id": "seller-sora", "email": "sora@locallink.kr", "name": "윤소라 (남해멸치)",
     "sector": "fishing", "tagline": "남해 죽방렴 멸치, 봄볕에 말립니다."},
    {"id": "seller-taemin", "email": "taemin@locallink.kr", "name": "한태민 (태안갯벌)",
     "sector": "fishing", "tagline": "태안 갯벌에서 조개·낙지 체험."},
    {"id": "seller-yoonseo", "email": "yoonseo@locallink.kr", "name": "장윤서 (담양대나무공방)",
     "sector": "craft", "tagline": "담양 대나무로 살림 도구를 만듭니다."},
    {"id": "seller-jihoon", "email": "jihoon@locallink.kr", "name": "신지훈 (이천도예)",
     "sector": "craft", "tagline": "이천 옹기·청자 빚는 30년 도예가."},
    {"id": "seller-eunsol", "email": "eunsol@locallink.kr", "name": "오은솔 (전주한지방)",
     "sector": "craft", "tagline": "전주 한지로 등·소품을 만듭니다."},
    {"id": "seller-hansol", "email": "hansol@locallink.kr", "name": "임한솔 (강릉바다스테이)",
     "sector": "lodging", "tagline": "강릉 안목 바다 도보 3분 스테이."},
    {"id": "seller-yejin", "email": "yejin@locallink.kr", "name": "백예진 (남해돌담펜션)",
     "sector": "lodging", "tagline": "남해 돌담마을 한옥 펜션."},
    {"id": "seller-doyoon", "email": "doyoon@locallink.kr", "name": "권도윤 (평창산골스테이)",
     "sector": "lodging", "tagline": "평창 해발 700m 산골 통나무집."},
    {"id": "seller-narae", "email": "narae@locallink.kr", "name": "유나래 (제주오름하우스)",
     "sector": "lodging", "tagline": "제주 동쪽 오름 옆 단독 스테이."},
    {"id": "seller-changmin", "email": "changmin@locallink.kr", "name": "황창민 (양양서핑캠프)",
     "sector": "leisure", "tagline": "양양 죽도해변 서핑·캠핑 호스트."},
]
