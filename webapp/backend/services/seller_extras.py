"""판매자 추가 기능 — SNS·관광·날씨·알림·에이전트 (데모·Claude 보강)."""

from __future__ import annotations

import json
from datetime import datetime

from services.agent_pipeline import audit_sns_copy
from services.listings_store import list_listings
from services.llm import DEFAULT_MODEL, is_configured as anthropic_configured

# 지역 키워드 → 시연용 관광·시즌 힌트
_REGION_HINTS: dict[str, dict[str, str]] = {
    "김제": {
        "tourism": "김제 지평선축제·금산사· 벽골제 일대가 유명합니다. 논밭 풍경과 함께 지역 특산 쌀·콩을 연계하면 좋습니다.",
        "season": "가을 수확·김장철 전후가 특산 판매 피크입니다.",
    },
    "양평": {
        "tourism": "두물머리·세미원·용문산 등 레저·한옥 숙박 수요가 많습니다.",
        "season": "봄 벚꽃·가을 단풍 시즌 숙박 문의가 늘어납니다.",
    },
    "제주": {
        "tourism": "올레·성산일출봉·감귤 체험과 연계한 체류형 상품이 잘 팔립니다.",
        "season": "겨울 감귤·여름 휴가철이 성수기입니다.",
    },
    "산청": {
        "tourism": "지리산·한방·꿀·약초 체험과 연계한 건강 테마가 어울립니다.",
        "season": "봄 산나물·가을 꿀 채밀 시즌을 강조하세요.",
    },
}


def _region_key(location: str) -> str | None:
    loc = (location or "").strip()
    for key in _REGION_HINTS:
        if key in loc:
            return key
    return None


def _claude_json(system: str, user: str, schema: dict) -> dict | None:
    if not anthropic_configured():
        return None
    from services.api_keys import anthropic_messages_create, anthropic_response_text

    try:
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "disabled"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        text = anthropic_response_text(response)
        return json.loads(text)
    except Exception:
        return None


def generate_sns_draft(
    kind: str, title: str, description: str, location: str, price: int
) -> dict:
    title = (title or "").strip() or "우리 마을 특산"
    loc = (location or "").strip() or "지역"
    desc = (description or "").strip()[:300]
    schema = {
        "type": "object",
        "properties": {
            "instagram": {"type": "string"},
            "facebook": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "hashtags": {"type": "string"},
        },
        "required": ["instagram", "keywords", "hashtags"],
        "additionalProperties": False,
    }
    data = _claude_json(
        "로컬 마켓 SNS 카피라이터. JSON만.",
        f"종류:{kind}, 제목:{title}, 가격:{price:,}원, 지역:{loc}, 설명:{desc}",
        schema,
    )
    if data:
        return audit_sns_copy(data)

    tags = f"#로컬링크 #{loc.replace(' ', '')} #{title[:12]}"
    return {
        "instagram": (
            f"🌾 {title}\n{loc}에서 올라온 {('숙소' if kind == 'lodging' else '특산')}입니다. "
            f"{price:,}원 · {desc[:80] or '정성껏 준비했습니다.'}\n{tags}"
        ),
        "facebook": f"[{loc}] {title} — {price:,}원. 로컬링크에서 만나보세요.",
        "keywords": [title, loc, "농어촌직거래", "특산품", "로컬푸드"][:6],
        "hashtags": tags,
    }


def tourism_tips(location: str, title: str = "", *, use_llm: bool = True) -> dict:
    loc = (location or "").strip() or "우리 지역"
    key = _region_key(loc)
    base = _REGION_HINTS.get(key or "", {})

    highlights = [
        base.get("tourism") or f"{loc} 주변 명소·축제·체험 마을을 상품 설명에 한 줄 넣어 보세요.",
        "배송·픽업·현장 수령 중 가능한 방식을 적어 두면 신뢰가 높아집니다.",
    ]
    fallback = {
        "location": loc,
        "highlights": highlights,
        "seller_tip": "지역 사진·수확 시기·생산자 한 마디를 함께 올리면 전환율이 좋아집니다.",
    }

    if not use_llm:
        return fallback

    schema = {
        "type": "object",
        "properties": {
            "highlights": {"type": "array", "items": {"type": "string"}},
            "seller_tip": {"type": "string"},
        },
        "required": ["highlights", "seller_tip"],
        "additionalProperties": False,
    }
    data = _claude_json(
        "한국 농어촌 관광 안내. JSON만.",
        f"지역:{loc}, 상품:{title or '(일반)'}",
        schema,
    )
    if data:
        return {"location": loc, **data}

    return fallback


def weather_season_tips(location: str) -> dict:
    loc = (location or "").strip() or "우리 지역"
    month = datetime.now().month
    season = (
        "봄"
        if month in (3, 4, 5)
        else "여름"
        if month in (6, 7, 8)
        else "가을"
        if month in (9, 10, 11)
        else "겨울"
    )
    key = _region_key(loc)
    regional = (_REGION_HINTS.get(key or {}) or {}).get("season", "")

    season_lines = {
        "봄": "봄철에는 새싹·봄나물·입춘 행사와 연계한 프로모션이 효과적입니다.",
        "여름": "여름에는 신선도·냉장 배송·숙박·피서 수요를 강조하세요.",
        "가을": "가을 수확·추석·김장철 특산 홍보 시기입니다.",
        "겨울": "겨울에는 보관법·건조·발효 식품·연말 선물 세트가 잘 팔립니다.",
    }

    return {
        "location": loc,
        "season": season,
        "month": month,
        "summary": f"지금은 {season}({month}월)입니다. {season_lines[season]}",
        "regional_note": regional or f"{loc} 지역 특성에 맞는 수확·행사 일정을 안내에 넣어 보세요.",
        "caution": "실시간 기상은 기상청 앱·날씨 위젯과 함께 안내하는 것을 권장합니다. (시연용 요약)",
    }


def alimtalk_draft(
    title: str,
    buyer_name: str = "고객",
    order_id: str = "주문예시",
) -> dict:
    title = (title or "").strip() or "주문 상품"
    buyer = (buyer_name or "").strip() or "고객"
    schema = {
        "type": "object",
        "properties": {
            "buyer_message": {"type": "string"},
            "seller_reminder": {"type": "string"},
        },
        "required": ["buyer_message", "seller_reminder"],
        "additionalProperties": False,
    }
    data = _claude_json(
        "알림톡/SMS 초안 작성. 2~3문장, 존댓말. JSON만.",
        f"구매자:{buyer}, 상품:{title}, 주문번호:{order_id}",
        schema,
    )
    if data:
        return {"order_id": order_id, **data}

    return {
        "order_id": order_id,
        "buyer_message": (
            f"[로컬링크] {buyer}님, '{title}' 주문이 접수되었습니다(주문 {order_id}). "
            "생산자가 확인 후 연락드릴 예정입니다. 감사합니다."
        ),
        "seller_reminder": (
            f"신규 주문: {title} — {buyer}님. 앱에서 재고·픽업 일정을 확인해 주세요."
        ),
    }


def agent_suggestions(seller_id: str = "seller-local") -> dict:
    items = [x for x in list_listings() if x.get("seller_id") == seller_id]
    tips: list[str] = []

    for e in items:
        t = e.get("title", "")
        if e.get("kind") == "product":
            stock = e.get("stock")
            if stock is not None and stock <= 3:
                tips.append(f"「{t}」 재고가 {stock}개뿐입니다. 품절 전 보충하거나 '매진 임박'을 표시해 보세요.")
            elif stock is not None and stock > 50:
                tips.append(f"「{t}」 재고가 넉넉합니다. 묶음 할인·2+1 문구를 SNS에 올려 보세요.")
        if e.get("kind") == "lodging" and not (e.get("description") or "").strip():
            tips.append(f"「{t}」 숙박 설명이 비어 있습니다. 체크인·조식·주차 안내를 추가하세요.")

    if not items:
        tips.append("아직 등록한 글이 없습니다. 음성 또는 손 입력으로 첫 상품을 올려 보세요.")

    month = datetime.now().month
    if month in (9, 10):
        tips.append("추석·수확철입니다. 선물 포장·배송 마감일을 상세 페이지에 적어 두세요.")
    elif month in (7, 8):
        tips.append("휴가철입니다. 숙박·냉장 배송 상품의 문의가 늘 수 있습니다.")

    if anthropic_configured() and items:
        summary = "\n".join(
            f"- {x.get('title')} ({x.get('kind')}) {x.get('price', 0):,}원 재고={x.get('stock')}"
            for x in items[:12]
        )
        schema = {
            "type": "object",
            "properties": {
                "suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            },
            "required": ["suggestions"],
            "additionalProperties": False,
        }
        data = _claude_json(
            "농어촌 마켓 운영 코치. 짧은 실행 제안 3~5개. JSON만.",
            f"판매 목록:\n{summary}",
            schema,
        )
        if data and data.get("suggestions"):
            tips = list(data["suggestions"]) + tips[:2]

    return {"suggestions": tips[:8]}
