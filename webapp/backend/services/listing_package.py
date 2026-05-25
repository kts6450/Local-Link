"""루플(Loople) 스타일 상품정보 + 이용안내 JSON 생성."""

from __future__ import annotations

import json
import os

from services.agent_pipeline import audit_listing_copy, strip_experience_in_package
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
    title = (title or "").strip() or "상품"
    loc = (location or "").strip() or "지역"
    is_market = kind != "lodging" and not is_experience(title, "", category)
    if kind == "lodging":
        kind_ko = "숙박"
        desc = (
            f"«{title}»은(는) {loc}에서 만나는 {kind_ko}입니다. "
            f"하룻밤 가격은 {price:,}원이며, 현장에서 차근차근 안내해 드립니다. "
            "문의 사항은 메시지로 편히 연락해 주세요."
        )
    elif is_market:
        desc = (
            f"«{title}»은(는) {loc}에서 정성껏 준비한 신선한 상품입니다. "
            f"판매가는 {price:,}원이며, 빠르게 포장해 곱게 보내 드립니다. "
            "문의 사항은 메시지로 편히 연락해 주세요."
        )
    else:
        desc = (
            f"«{title}»은(는) {loc}에서 만나는 즐길 거리입니다. "
            f"참여비는 {price:,}원이며, 현장에서 차근차근 안내해 드립니다. "
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

    # desc 에는 "체험·상품" 문구가 들어가므로 is_experience 에 넘기면 모든 상품이
    # 체험으로 오분류된다. 카테고리·제목으로만 판정한다.
    exp = is_experience(title, "", category)
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
            f"{loc}에서 정성껏 준비한 신선한 특산",
            "산지 직접 발송으로 합리적인 가격",
            "받자마자 그대로 드실 수 있게 깔끔하게 포장",
        ],
        "steps": [],
        "included": ["상품 본품", "기본 포장"],
        "not_included": ["배송비(지역별 상이)"],
        "precautions": [
            "수령 후에는 서늘한 곳에 두고 가급적 빨리 드세요.",
            "신선식품 특성상 무르거나 색이 약간 다를 수 있어요.",
        ],
        "refund_policy": (
            "미개봉·미훼손 시 수령 7일 이내 교환·환불 협의(시연). "
            "신선식품은 단순 변심 환불이 제한될 수 있습니다."
        ),
        "meeting_place": "",
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

    is_exp = is_experience(title, "", category) if kind != "lodging" else False
    if kind == "lodging":
        kind_ko = "숙박·민박"
    elif is_exp:
        kind_ko = "체험·축제 프로그램"
    else:
        kind_ko = "특산·마켓 상품 (택배·픽업 판매)"

    if is_exp or kind == "lodging":
        format_rules = (
            "- highlights: 체험·이용 포인트 3~5개 (짧은 문장).\n"
            "- steps: 4~6단계, 각각 time(HH:MM), title, body 로 일정을 적습니다.\n"
            "- included / not_included / precautions: 각 2~4개.\n"
            "- refund_policy: 환불 안내 2~3문장.\n"
            "- meeting_place, address: 만남 장소·주소를 구체적으로.\n"
            "- nearby: 인근 관광지 2~3곳(이름·주소·이용시간·휴일·주차).\n"
        )
    else:
        format_rules = (
            "- highlights: 상품 특징 3~5개 (짧은 문장, 산지·신선도·보관·맛 위주).\n"
            "- steps: **반드시 빈 배열 [] 로 두세요.** 마켓 상품은 시간표가 필요 없습니다.\n"
            "- included: 본품·기본 포장 등 함께 가는 것 2~4개.\n"
            "- not_included: 배송비·아이스팩 등 빠지는 것 2~3개.\n"
            "- precautions: 보관 방법·신선식품 주의·알레르기 등 2~4개.\n"
            "- refund_policy: 교환·반품 안내 2~3문장(신선식품 단순 변심 환불 제한 가능 등).\n"
            "- meeting_place: **빈 문자열 \"\" 로 두세요.** (대면 만남 없음)\n"
            "- address: 발송지·산지 정도만 짧게.\n"
            "- nearby: **반드시 빈 배열 [] 로 두세요.** 마켓 상품은 관광지 추천이 필요 없습니다.\n"
            "- 단어 사용 금지: '체험', '체험하다', '체험 프로그램', '견학', '프로그램', '일정',\n"
            "  '진행 순서', '만남' 같은 체험 전용 표현은 description·highlights·included\n"
            "  ·not_included·precautions 등 어디에도 절대 쓰지 마세요. 대신 '맛보기',\n"
            "  '직접 받아보기', '드셔보기', '느껴보기' 처럼 마켓 상품에 어울리는 말을 사용합니다.\n"
        )

    prompt = f"""로컬링크 마켓 상품 페이지를 작성합니다.

- 종류: {kind_ko}
- 카테고리: {category}
- 이름: {title}
- 가격: {price:,}원
- 지역: {location or "(미입력)"}

규칙:
- 한국어만, 존댓말·쉬운 말(어르신도 읽기 쉽게).
- description: 2~4문장 소개.
{format_rules}- 사실에 없는 인증·수상·전화번호는 쓰지 말 것.
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
        is_market_product = kind != "lodging" and not is_exp
        desc = str(data.get("description", "")).strip()
        desc = audit_listing_copy(
            desc,
            title=title,
            price=price,
            location=location,
            is_market_product=is_market_product,
        )
        guide = {k: data.get(k) for k in _PACKAGE_SCHEMA["properties"] if k != "description"}
        # 마켓 상품(택배·픽업 판매)에는 체험 일정·만남장소·관광지가 들어가지
        # 않도록 안전장치. LLM 이 규칙을 무시한 케이스를 마지막에 정리한다.
        if is_market_product:
            guide["steps"] = []
            guide["meeting_place"] = ""
            guide["nearby"] = []
            guide = strip_experience_in_package(guide)
        if not desc:
            fb = _fallback_package(kind, title, price, location, category)
            return {"description": fb["description"], "guide": _guide_only(fb)}
        return {"description": desc, "guide": guide}
    except Exception:
        fb = _fallback_package(kind, title, price, location, category)
        return {"description": fb["description"], "guide": _guide_only(fb)}


def _guide_only(pkg: dict) -> dict:
    return {k: v for k, v in pkg.items() if k != "description"}


