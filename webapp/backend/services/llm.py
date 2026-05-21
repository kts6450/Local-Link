"""LLM — 구매자(주문) / 판매자(등록) 음성 비서."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache

import anthropic

from services.listings_store import listings_summary_for_llm

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


def _listing_block() -> str:
    return listings_summary_for_llm()


def _consumer_system() -> str:
    return f"""\
당신은 '로컬링크 Local Link' 쇼핑 도우미입니다. 이웃이 음성으로 상품이나 숙박을
고르고 주문할 수 있게 돕습니다. 사용자는 방언을 쓸 수 있고, 말이 짧아도 됩니다.

## 답변
- 한두 문장, 따뜻하고 쉬운 말.
- 마크다운·글머리·이모지·영어는 쓰지 마세요. 음성으로 읽힙니다.
- 인식이 어색해도 의미만 이해하고, 오타 지적은 하지 마세요.

## 채울 정보
1. listing_id — 아래 목록의 id. 사용자가 말한 물건·민박과 가장 가까운 것.
2. quantity — 수량. 기본 1.
3. contact_name — 주문하시는 분 성함.
4. contact_phone — 연락처.

비어 있는 것만 하나씩 물어보세요. 네 가지가 다 있으면 한 번에 정리해서
"이대로 주문할까요?"처럼 확인만 하세요.

## 등록된 물건·숙박
{_listing_block()}
"""


def _seller_system() -> str:
    return f"""\
당신은 '로컬링크 Local Link' 판매자 도우미입니다. 어르신이 음성만으로 상품이나
숙박(민박)을 올릴 수 있게 짧게 질문합니다. 방언·짧은 말 모두 이해합니다.

## 답변
- 한두 문장, 존댓말. 어려운 말은 쓰지 마세요.
- 마크다운·글머리·이모지·영어는 쓰지 마세요.

## 등록에 필요한 것
1. listing_type — 상품이면 product, 숙박·민박이면 lodging.
2. title — 짧은 이름 (예: 올해 쌀 20킬로, 바닷가 민박 하룻밤).
3. price — 원 단위 숫자만 (예 삼만원이면 30000).
4. description — 무엇인지, 왜 좋은지 한두 문장.
5. location — 어느 동네인지 (시·군까지).
6. stock — 상품이면 개수 정도. 모르면 비워도 됩니다. 숙박이면 비움.
7. max_guests — 숙박이면 몇 명까지인지. 상품이면 비움.

하나씩만 묻고, 다 모이면 "이대로 올릴까요?" 하고 확인하세요.

## 음성으로 화면 도우미 (intent)
- 사용자가 "AI로 글 써줘", "소개 글 만들어줘", "설명 써줘" → intent=ai_write (ready_to_confirm=false).
  답변: "네, 소개 글을 AI로 채울게요." 처럼 짧게.
- "사진 만들어줘", "대표 사진", "이미지 그려줘" → intent=ai_image (ready_to_confirm=false).
  이름(title)이 없으면 먼저 이름을 물어보세요.
- "설명만 짧게" → intent=ai_write (짧은 설명만 원함을 slots에 반영할 필요 없음).

참고로 지금 등록된 다른 물건은 다음과 같습니다.
{_listing_block()}
"""


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    if not is_configured():
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    return anthropic.Anthropic()


_CONSUMER_SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["browse", "buy", "confirm", "ask_info", "smalltalk", "other"],
        },
        "listing_id": {"type": ["string", "null"]},
        "quantity": {"type": ["integer", "null"]},
        "contact_name": {"type": ["string", "null"]},
        "contact_phone": {"type": ["string", "null"]},
        "ready_to_confirm": {"type": "boolean"},
    },
    "required": ["intent", "ready_to_confirm"],
    "additionalProperties": False,
}

_SELLER_SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["register", "confirm", "ai_write", "ai_image", "ask_help", "smalltalk", "other"],
        },
        "listing_type": {"type": ["string", "null"], "description": "product or lodging"},
        "title": {"type": ["string", "null"]},
        "price": {"type": ["integer", "null"]},
        "description": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "stock": {"type": ["integer", "null"]},
        "max_guests": {"type": ["integer", "null"]},
        "emoji": {"type": ["string", "null"]},
        "ready_to_confirm": {"type": "boolean"},
    },
    "required": ["intent", "ready_to_confirm"],
    "additionalProperties": False,
}


def _user_utterances_blob(history: list[dict], user_text: str) -> str:
    parts = [m.get("content", "") for m in history if m.get("role") == "user"]
    parts.append(user_text)
    return " ".join(parts).strip()


def _is_affirmation(user_text: str) -> bool:
    t = re.sub(r"\s+", "", (user_text or "").strip())
    if not t or len(t) > 24:
        return False
    return bool(
        re.match(
            r"^(네|네요|예|예요|응|응응|그래|그래요|맞아|맞아요|좋아요|확인|"
            r"올려요?|등록|해줘|해주세요|확정|그렇게|네그래|응그래|맞습니다)",
            t,
        )
    )


def _seller_prompted_confirm(history: list[dict]) -> bool:
    for m in reversed(history or []):
        if m.get("role") != "assistant":
            continue
        c = m.get("content", "")
        if "올릴" in c and ("까" in c or "주세요" in c):
            return True
    return False


def _extract_price_kr(text: str) -> int | None:
    t = re.sub(r"\s+", "", text or "")

    m = re.search(r"(\d+)만(\d{1,2})?천", t)
    if m:
        cheon = int(m.group(2)) * 1000 if m.group(2) else 0
        return int(m.group(1)) * 10000 + cheon

    m = re.search(r"(\d+)만(?:원)?", t)
    if m:
        return int(m.group(1)) * 10000

    if re.search(r"(?<!\d)만원", t) or "만원에" in t:
        return 10000

    m = re.search(r"(\d+)천(?:원)?", t)
    if m:
        return int(m.group(1)) * 1000

    m = re.search(r"(\d{1,9})원", t)
    if m:
        return int(m.group(1))
    return None


def _extract_location_kr(text: str) -> str | None:
    m = re.search(r"([가-힣]{2,6}(?:시|군|구))", text or "")
    if m:
        return m.group(1)

    cities = (
        ("김제", "김제시"),
        ("천안", "천안시"),
        ("강릉", "강릉시"),
        ("전주", "전주시"),
        ("목포", "목포시"),
        ("여수", "여수시"),
        ("속초", "속초시"),
        ("화성", "화성시"),
        ("수원", "수원시"),
        ("김포", "김포시"),
        ("파주", "파주시"),
        ("제주", "제주시"),
        ("포항", "포항시"),
        ("춘천", "춘천시"),
        ("원주", "원주시"),
        ("홍천", "홍천군"),
        ("평창", "평창군"),
    )
    for short, full in cities:
        if short in (text or ""):
            return full
    return None


def _seller_rule_slots_from_blob(blob: str) -> dict:
    """Claude 없이 판매 슬롯 추출 — 농어촌 말투·짧은 문장 위주."""
    slots: dict = {}
    text = (blob or "").strip()
    if not text:
        return slots

    if re.search(
        r"숙박|민박|펜션|하숙|숙소|하룻밤|방\s*빌려|방\s*내놓|숙박상품",
        text,
    ):
        slots["kind"] = "lodging"
    elif re.search(
        r"상품|팔아|팝니다|물건|키로|킬로|kg|되|말|쌀|과일|꿀|약|한우|팥|콩",
        text,
        re.I,
    ):
        slots["kind"] = "product"

    price = _extract_price_kr(text)
    if price is not None:
        slots["price"] = price

    loc = _extract_location_kr(text)
    if loc:
        slots["location"] = loc

    head = blob
    head = re.split(
        r"(?:올리고\s*싶(?:어|요)?|올릴게요?|등록\s*할게요?|팔아(?:요)?|판매\s*할게요?)",
        head,
        maxsplit=1,
    )[0].strip()
    head = re.sub(
        r"\s*(\d+만\d{1,2}천원?|\d+만(?:원)?|\d+천(?:원)?|만원)(?:에)?\s*$",
        "",
        head,
    )
    head = re.sub(r"\s+", " ", head).strip()
    if 2 <= len(head) <= 48:
        slots["title"] = head
    elif len(head) > 48:
        slots["title"] = head[:45].rstrip() + "…"

    kind = slots.get("kind")
    loc_name = slots.get("location")
    if kind == "lodging" and loc_name and not slots.get("title"):
        slots["title"] = f"{loc_name} 숙박"
    elif kind == "product" and loc_name and not slots.get("title"):
        slots["title"] = f"{loc_name} 상품"

    if len(text) >= 8:
        slots.setdefault(
            "description",
            text[:200] + ("…" if len(text) > 200 else ""),
        )

    if slots.get("kind") == "lodging":
        slots.setdefault("max_guests", 4)
    elif slots.get("kind") == "product":
        slots.setdefault("stock", 10)

    return slots


def _seller_slots_complete(slots: dict) -> bool:
    return (
        slots.get("kind") in ("product", "lodging")
        and isinstance(slots.get("price"), int)
        and slots["price"] >= 0
        and bool(str(slots.get("location", "")).strip())
        and bool(str(slots.get("title", "")).strip())
    )


def _seller_next_question(slots: dict) -> str:
    if slots.get("kind") not in ("product", "lodging"):
        return "물건을 파실 거면 상품, 민박이면 숙박이라고 짧게 말씀해 주세요."
    if not isinstance(slots.get("price"), int):
        return "얼마에 올리실지, 숫자로 말씀해 주세요. 예를 들어 만 원이면 만원이라고 하셔도 됩니다."
    if not str(slots.get("location", "")).strip():
        return "어느 동네인지, 시나 군 이름까지 말씀해 주세요."
    if not str(slots.get("title", "")).strip():
        return "이름을 한 번에 불러 주세요. 예를 들어 올해 햅쌀 십 키로, 이렇게요."
    return "조금만 더 말씀해 주세요."


def _seller_format_summary(slots: dict) -> str:
    kind_ko = "숙박" if slots.get("kind") == "lodging" else "상품"
    price = int(slots["price"])
    return (
        f"{kind_ko} «{slots['title']}», {price:,}원, {slots.get('location', '')}에 올리는 것으로"
        " 들었습니다."
    )


def _seller_voice_command(user_text: str) -> str | None:
    t = (user_text or "").strip()
    if re.search(r"AI|인공지능|글\s*써|소개\s*글|설명\s*써|설명\s*만들|한번에\s*써", t):
        return "ai_write"
    if re.search(r"사진|이미지|그림|대표\s*사진", t) and re.search(
        r"만들|그려|생성|찍|그려줘|만들어", t
    ):
        return "ai_image"
    return None


def seller_offline_turn(user_text: str, history: list[dict]) -> dict:
    """API 키 없을 때 판매자 음성만 규칙으로 처리 (Zero UI 데모 가능)."""
    cmd = _seller_voice_command(user_text)
    blob = _user_utterances_blob(history, user_text)
    slots = _seller_rule_slots_from_blob(blob)
    if cmd == "ai_write":
        return {
            "reply": "네, AI로 소개 글을 채울게요. 잠시만 기다려 주세요.",
            "slots": slots,
            "intent": "ai_write",
            "ready_to_confirm": False,
        }
    if cmd == "ai_image":
        if not str(slots.get("title", "")).strip():
            return {
                "reply": "사진을 만들려면 먼저 물건 이름을 말씀해 주세요.",
                "slots": slots,
                "intent": "register",
                "ready_to_confirm": False,
            }
        return {
            "reply": "네, 대표 사진을 AI로 만들게요. 잠시만 기다려 주세요.",
            "slots": slots,
            "intent": "ai_image",
            "ready_to_confirm": False,
        }
    complete = _seller_slots_complete(slots)
    affirm = _is_affirmation(user_text)
    prompted = _seller_prompted_confirm(history)

    if complete and affirm and prompted:
        return {
            "reply": "네, 알겠습니다. 바로 반영할게요.",
            "slots": slots,
            "intent": "confirm",
            "ready_to_confirm": True,
        }

    if complete and not prompted:
        return {
            "reply": _seller_format_summary(slots)
            + " 이대로 올릴까요? 마이크를 다시 누르시고 네 하고 말씀해 주세요.",
            "slots": slots,
            "intent": "register",
            "ready_to_confirm": False,
        }

    if complete and prompted and not affirm:
        return {
            "reply": "맞으면 네 하고, 고치실 부분 있으면 다시 말씀해 주세요.",
            "slots": slots,
            "intent": "register",
            "ready_to_confirm": False,
        }

    return {
        "reply": _seller_next_question(slots),
        "slots": slots,
        "intent": "register",
        "ready_to_confirm": False,
    }


def chat_turn_for_mode(user_text: str, history: list[dict], mode: str) -> dict:
    if mode not in ("consumer", "seller"):
        mode = "consumer"

    if not is_configured():
        if mode == "seller":
            return seller_offline_turn(user_text, list(history or []))
        return {
            "reply": "지금은 음성 도우미가 잠시 쉬고 있어요. 화면에서 눌러 주세요.",
            "slots": {},
            "intent": "error",
            "ready_to_confirm": False,
            "error": "ANTHROPIC_API_KEY missing",
        }

    system = _consumer_system() if mode == "consumer" else _seller_system()
    client = _client()
    messages = list(history) + [{"role": "user", "content": user_text}]

    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
    )
    reply = next(b.text for b in response.content if b.type == "text").strip()

    schema = _CONSUMER_SLOT_SCHEMA if mode == "consumer" else _SELLER_SLOT_SCHEMA
    slots, intent, ready = _extract_slots(
        messages + [{"role": "assistant", "content": reply}],
        schema,
        mode,
    )

    return {
        "reply": reply,
        "slots": slots,
        "intent": intent,
        "ready_to_confirm": ready,
    }


def _extract_slots(conversation: list[dict], schema: dict, mode: str) -> tuple[dict, str, bool]:
    client = _client()
    if mode == "consumer":
        extractor = """\
대화에서 주문 슬롯을 추출하세요.
- listing_id, quantity(없으면 1), contact_name, contact_phone
ready_to_confirm은 위가 모두 채워졌고 사용자가 확정 의사일 때만 true.
"""
    else:
        extractor = """\
대화에서 판매 등록 슬롯을 추출하세요.
- listing_type: product 또는 lodging
- title, price(원), description, location
- 상품이면 stock, 숙박이면 max_guests
ready_to_confirm은 필수 항목이 채워지고 확인 단계일 때만 true.
"""

    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=512,
            system=extractor,
            messages=[
                {
                    "role": "user",
                    "content": "대화:\n"
                    + "\n".join(f"[{m['role']}] {m['content']}" for m in conversation),
                }
            ],
            thinking={"type": "disabled"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        intent = data.pop("intent", "other")
        ready = data.pop("ready_to_confirm", False)
        slots = {k: v for k, v in data.items() if v is not None}
        # normalize seller listing_type → kind for API
        if mode == "seller" and "listing_type" in slots:
            lt = slots.pop("listing_type")
            if isinstance(lt, str) and lt in ("product", "lodging"):
                slots["kind"] = lt
        return slots, intent, bool(ready)
    except Exception:
        return {}, "other", False
