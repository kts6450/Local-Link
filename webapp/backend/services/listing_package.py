"""루플(Loople) 스타일 상품정보 + 이용안내 JSON 생성."""

from __future__ import annotations

import json
import os

from services.agent_pipeline import audit_listing_copy
from services.listing_guide import is_experience
from services.llm import DEFAULT_MODEL, is_configured as anthropic_configured

_PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "highlights": {"type": "array", "items": {"type": "string"}},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
                "additionalProperties": False,
            },
        },
        "included": {"type": "array", "items": {"type": "string"}},
        "not_included": {"type": "array", "items": {"type": "string"}},
        "precautions": {"type": "array", "items": {"type": "string"}},
        "refund_policy": {"type": "string"},
        "meeting_place": {"type": "string"},
        "address": {"type": "string"},
        "nearby": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "hours": {"type": "string"},
                    "holiday": {"type": "string"},
                    "parking": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "description",
        "highlights",
        "steps",
        "included",
        "not_included",
        "precautions",
        "refund_policy",
        "meeting_place",
        "address",
        "nearby",
    ],
    "additionalProperties": False,
}


def _fallback_package(
    kind: str,
    title: str,
    price: int,
    location: str,
    category: str,
) -> dict:
    title = (title or "").strip() or "체험"
    loc = (location or "").strip() or "지역"
    kind_ko = "숙박" if kind == "lodging" else "체험·상품"
    desc = (
        f"«{title}»은(는) {loc}에서 만나는 {kind_ko}입니다. "
        f"판매가 {price:,}원이며, 현장에서 차근차근 안내해 드립니다. "
        "문의 사항은 메시지로 편히 연락해 주세요."
    )

    if kind == "lodging":
        return {
            "description": desc,
            "highlights": [
                "지역 호스트가 직접 안내합니다",
                "한적한 시골·바다 분위기",
                f"최대 인원은 상품 안내를 확인해 주세요",
            ],
            "steps": [],
            "included": ["숙박 1박", "기본 침구"],
            "not_included": ["개인 간식", "교통비"],
            "precautions": [
                "체크인·체크아웃 시간은 사전에 협의합니다.",
                "반려동물 동반은 문의 후 가능합니다.",
            ],
            "refund_policy": (
                "이용 3일 전까지 취소 시 전액 환불(시연). 당일 취소·노쇼는 환불이 어려울 수 있습니다."
            ),
            "meeting_place": f"{loc} 숙소 앞 (상세 주소는 예약 후 안내)",
            "address": loc,
            "nearby": [],
        }

    exp = is_experience(title, desc, category)
    if exp:
        return {
            "description": desc,
            "highlights": [
                f"{loc}에서 즐기는 {title}",
                "가족·어르신도 편한 속도로 진행",
                "현지 안내자 동행(시연)",
            ],
            "steps": [
                {
                    "time": "10:00",
                    "title": "만남 및 안내",
                    "body": "집합 장소에서 인사·오늘 일정을 안내합니다.",
                },
                {
                    "time": "10:30",
                    "title": "본 체험",
                    "body": f"{title} 본 프로그램을 진행합니다. 사진 촬영은 자유롭게 하셔도 됩니다.",
                },
                {
                    "time": "12:00",
                    "title": "마무리",
                    "body": "체험을 마치고 다음 일정·귀가 안내를 드립니다.",
                },
            ],
            "included": ["체험 프로그램", "현장 안내"],
            "not_included": ["개인 교통비", "개인 간식"],
            "precautions": [
                "우천 시 일정이 조정될 수 있습니다.",
                "편한 복장·운동화를 권장합니다.",
            ],
            "refund_policy": (
                "이용 2일 전까지 취소 시 전액 환불(시연). 당일 취소는 환불이 제한될 수 있습니다."
            ),
            "meeting_place": f"{loc} 집합 장소 (예약 후 문자 안내)",
            "address": loc,
            "nearby": [
                {
                    "name": f"{loc} 주변 산책로",
                    "address": loc,
                    "hours": "일출~일몰",
                    "holiday": "연중무휴",
                    "parking": "가능",
                }
            ],
        }

    return {
        "description": desc,
        "highlights": [
            f"{loc}에서 생산·준비한 신선한 특산",
            "직거래로 합리적인 가격",
        ],
        "steps": [],
        "included": ["상품 본품", "기본 포장"],
        "not_included": ["배송비(지역별 상이)"],
        "precautions": [
            "수령·배송 일정은 판매자와 조율합니다.",
            "신선식품은 빠른 수령을 권장합니다.",
        ],
        "refund_policy": (
            "미개봉·미훼손 시 수령 7일 이내 교환·환불 협의(시연). 신선식품은 단순 변심 환불이 제한될 수 있습니다."
        ),
        "meeting_place": f"{loc} 픽업·직거래 장소",
        "address": loc,
        "nearby": [],
    }


def generate_listing_package(
    kind: str,
    title: str,
    price: int,
    location: str,
    category: str = "rural",
) -> dict:
    """상품 설명 + 이용안내 구조(JSON). 루플 상품 페이지와 유사한 섹션."""
    title = (title or "").strip()
    if not title:
        fb = _fallback_package(kind, "", price, location, category)
        return {"description": "상품 이름을 먼저 적어 주세요.", "guide": _guide_only(fb)}

    if not anthropic_configured():
        fb = _fallback_package(kind, title, price, location, category)
        return {"description": fb["description"], "guide": _guide_only(fb)}

    kind_ko = "숙박·민박" if kind == "lodging" else "체험·특산 상품"
    prompt = f"""로컬링크 마켓 상품 페이지를 작성합니다. 참고: 루플(Loople) 체험 상품처럼
「상품 정보」에 소개글·체험 포인트·STEP 일정, 「이용 안내」에 포함·환불·만남장소·인근 관광지를 넣습니다.

- 종류: {kind_ko}
- 카테고리: {category}
- 이름: {title}
- 가격: {price:,}원
- 지역: {location or "(미입력)"}

규칙:
- 한국어만, 존댓말·쉬운 말(어르신도 읽기 쉽게).
- description: 2~4문장 소개.
- highlights: 체험 포인트 3~5개 (짧은 문장).
- steps: 체험·축제형이면 4~6단계, 각각 time(HH:MM), title, body. 특산품만 팔면 steps는 빈 배열 [].
- included / not_included / precautions: 각 2~4개.
- refund_policy: 교환·반품·환불 안내 2~3문장(시연용).
- meeting_place, address: 구체적으로.
- nearby: 인근 관광지 2~3곳(이름·주소·이용시간·휴일·주차).
- 사실에 없는 인증·수상·전화번호는 쓰지 말 것.
"""

    from services.api_keys import anthropic_messages_create, anthropic_response_text

    try:
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=2000,
            system="너는 농어촌 체험·특산 마켓의 상세 페이지 작성자다. JSON만 출력한다.",
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "disabled"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _PACKAGE_SCHEMA},
            },
        )
        text = anthropic_response_text(response)
        data = json.loads(text)
        desc = str(data.get("description", "")).strip()
        desc = audit_listing_copy(desc, title=title, price=price, location=location)
        guide = {k: data.get(k) for k in _PACKAGE_SCHEMA["properties"] if k != "description"}
        if not desc:
            fb = _fallback_package(kind, title, price, location, category)
            return {"description": fb["description"], "guide": _guide_only(fb)}
        return {"description": desc, "guide": guide}
    except Exception:
        fb = _fallback_package(kind, title, price, location, category)
        return {"description": fb["description"], "guide": _guide_only(fb)}


def _guide_only(pkg: dict) -> dict:
    return {k: v for k, v in pkg.items() if k != "description"}


