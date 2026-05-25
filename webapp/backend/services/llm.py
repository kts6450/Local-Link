"""LLM — 구매자(주문) / 판매자(등록) 음성 비서."""

from __future__ import annotations

import json
import os
import re

from services.agent_pipeline import (
    audit_seller_confirm,
    pipeline_mode,
    polish_tts_reply,
    run_slot_pipeline,
)
from services.asr_correction import normalize_location, normalize_slots_locations
from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured
from services.demo_config import is_demo_mode
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
- 사용자 발화는 Whisper→규칙→AI 검수(A2A)로 이미 교정된 텍스트입니다. 지명·숫자를 그대로 신뢰하세요.

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

## 음성 인식
- 입력은 Whisper 후 A2A(규칙+Claude+검수)로 교정된 문장입니다.
- 값평→가평 같은 지명 교정은 이미 반영되었을 수 있습니다. location·title을 그대로 채우세요.

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
- "노트 사진으로 채워줘", "메모 사진으로 적어줘", "사진 보고 채워줘",
  "수첩 사진 읽어줘", "사진으로 입력할게" 등 → intent=ocr_note (ready_to_confirm=false).
  답변: "네, 왼쪽 '노트 사진으로 채우기' 칸에서 사진을 골라 주세요." 처럼 짧게.
- "설명만 짧게" → intent=ai_write (짧은 설명만 원함을 slots에 반영할 필요 없음).

## 슬롯 추출 시 절대 규칙 — 매우 중요
- "사진", "글", "AI", "노트", "메모", "채워", "써줘", "만들어", "그려", "올려",
  "등록", "확인" 같은 **명령·도움 요청 단어**가 들어간 발화 전체를
  title·description·location 슬롯에 **절대 넣지 마세요.**
- 이런 발화는 intent(ai_write/ai_image/ocr_note)로만 처리하고, 슬롯은 비워 두세요.
- location 은 「○○도 ○○시 ○○면」 같은 행정구역 표현일 때만 채웁니다.
  문장 전체나 명령 문구를 그대로 location 으로 넣으면 안 됩니다.
- 한 turn 안에 정보(이름·가격 등)와 명령이 섞여 있어도, 명령 부분은 슬롯에서 빼세요.

참고로 지금 등록된 다른 물건은 다음과 같습니다.
{_listing_block()}
"""


def is_configured() -> bool:
    return is_anthropic_configured()


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
            "enum": [
                "register",
                "confirm",
                "ai_write",
                "ai_image",
                "ocr_note",
                "ask_help",
                "smalltalk",
                "other",
            ],
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


def _form_state_to_seller_slots(form_state: dict) -> dict:
    """프론트가 보낸 form_state(폼 입력값)를 판매자 슬롯 형식으로 정규화."""
    out: dict = {}
    if not isinstance(form_state, dict):
        return out
    title = (form_state.get("title") or "").strip() if isinstance(form_state.get("title"), str) else ""
    if title:
        out["title"] = title
    description = (
        form_state.get("description") or ""
    ).strip() if isinstance(form_state.get("description"), str) else ""
    if description:
        out["description"] = description
    location = (
        form_state.get("location") or ""
    ).strip() if isinstance(form_state.get("location"), str) else ""
    if location:
        out["location"] = location
    price_v = form_state.get("price")
    if isinstance(price_v, (int, float)) and price_v >= 0:
        out["price"] = int(price_v)
    elif isinstance(price_v, str) and price_v.strip().isdigit():
        out["price"] = int(price_v.strip())
    listing_tab = form_state.get("listing_tab") or form_state.get("kind")
    if listing_tab in ("product", "lodging", "experience"):
        out["kind"] = "lodging" if listing_tab == "lodging" else "product"
    stock_v = form_state.get("stock")
    if isinstance(stock_v, (int, float)):
        out["stock"] = int(stock_v)
    elif isinstance(stock_v, str) and stock_v.strip().isdigit():
        out["stock"] = int(stock_v.strip())
    max_g = form_state.get("max_guests")
    if isinstance(max_g, (int, float)):
        out["max_guests"] = int(max_g)
    return out


def _augment_system_with_form_state(
    system: str, form_state: dict, mode: str
) -> str:
    """현재 폼에 채워진 값을 시스템 프롬프트 끝에 컨텍스트로 붙여 준다."""
    if mode != "seller" or not form_state:
        return system
    pieces: list[str] = []
    title = str(form_state.get("title") or "").strip()
    if title:
        pieces.append(f"- 이름(title): {title}")
    price = form_state.get("price")
    if isinstance(price, (int, float)) and price >= 0:
        pieces.append(f"- 가격(price): {int(price):,}원")
    elif isinstance(price, str) and price.strip().isdigit():
        pieces.append(f"- 가격(price): {int(price.strip()):,}원")
    location = str(form_state.get("location") or "").strip()
    if location:
        pieces.append(f"- 지역(location): {location}")
    description = str(form_state.get("description") or "").strip()
    if description:
        pieces.append(f"- 소개(description): {description[:200]}")
    listing_tab = form_state.get("listing_tab") or form_state.get("kind")
    if listing_tab:
        pieces.append(f"- 종류(listing_type/kind): {listing_tab}")
    if not pieces:
        return system
    addendum = (
        "\n\n## 화면 폼에 이미 채워진 값 — 매우 중요\n"
        "사용자가 OCR(노트 사진), 직접 입력, 이전 음성 등으로 다음 정보를 이미 채웠습니다.\n"
        "이 값들은 **기존 정보로 인정**하고, 사용자에게 다시 묻지 마세요. 슬롯에도 그대로 보전하세요.\n"
        "사용자가 이 정보를 명시적으로 바꾸겠다고 말한 경우에만 새 값으로 교체합니다.\n"
        + "\n".join(pieces)
        + "\n"
    )
    return system + addendum


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
    return normalize_location(text)


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


def seller_offline_turn(
    user_text: str,
    history: list[dict],
    *,
    form_state: dict | None = None,
) -> dict:
    """API 키 없을 때 판매자 음성만 규칙으로 처리 (Zero UI 데모 가능)."""
    cmd = _seller_voice_command(user_text)
    blob = _user_utterances_blob(history, user_text)
    slots = _seller_rule_slots_from_blob(blob)
    # 폼에 이미 채워진 값을 보전한다.
    baseline = _form_state_to_seller_slots(form_state or {})
    slots = {**baseline, **{k: v for k, v in slots.items() if v not in (None, "")}}
    slots = normalize_slots_locations(slots)
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
        audit = audit_seller_confirm(slots, list(history or []) + [{"role": "user", "content": user_text}])
        slots = audit.slots
        if not audit.approved:
            return {
                "reply": _seller_format_summary(slots)
                + " 한 번 더 확인해 주세요. 맞으면 네 하고 말씀해 주세요.",
                "slots": slots,
                "intent": "register",
                "ready_to_confirm": False,
            }
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


def chat_turn_for_mode(
    user_text: str,
    history: list[dict],
    mode: str,
    *,
    form_state: dict | None = None,
) -> dict:
    if mode not in ("consumer", "seller"):
        mode = "consumer"

    form_state = form_state or {}

    if not is_configured():
        if mode == "seller":
            return seller_offline_turn(
                user_text, list(history or []), form_state=form_state
            )
        return {
            "reply": "지금은 음성 도우미가 잠시 쉬고 있어요. 화면에서 눌러 주세요.",
            "slots": {},
            "intent": "error",
            "ready_to_confirm": False,
            "error": "ANTHROPIC_API_KEY missing",
        }

    messages = list(history) + [{"role": "user", "content": user_text}]

    try:
        base_system = (
            _consumer_system() if mode == "consumer" else _seller_system()
        )
        system = _augment_system_with_form_state(base_system, form_state, mode)

        response = anthropic_messages_create(
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
        reply = anthropic_response_text(response)
    except Exception:
        if mode == "seller":
            return seller_offline_turn(
                user_text, list(history or []), form_state=form_state
            )
        return {
            "reply": "잠시 연결이 불안정해요. 다시 한번 말씀해 주시겠어요?",
            "slots": {},
            "intent": "error",
            "ready_to_confirm": False,
        }

    schema = _CONSUMER_SLOT_SCHEMA if mode == "consumer" else _SELLER_SLOT_SCHEMA
    try:
        slots, intent, ready = _extract_slots(
            messages + [{"role": "assistant", "content": reply}],
            schema,
            mode,
        )
        # 폼에 이미 채워져 있던 값(OCR/직접 입력)을 LLM 결과에 보완해서
        # "처음부터 다시 묻는" 현상을 막는다. LLM 이 같은 키에 새 값을 채웠다면
        # 그 값을 우선시한다 (사용자가 방금 말로 바꾼 것일 수 있음).
        baseline = _form_state_to_seller_slots(form_state) if mode == "seller" else {}
        merged_slots = {**baseline, **{k: v for k, v in slots.items() if v not in (None, "")}}
        slots = merged_slots
        slot_pipe = run_slot_pipeline(
            messages + [{"role": "assistant", "content": reply}],
            slots,
            intent,
            ready,
            mode,
        )
        slots = slot_pipe.slots
        intent = slot_pipe.intent
        ready = slot_pipe.ready_to_confirm
    except Exception:
        slot_pipe = None
        slots = normalize_slots_locations(
            _seller_rule_slots_from_blob(_user_utterances_blob(history, user_text))
            if mode == "seller"
            else {}
        )
        intent = "register" if mode == "seller" else "other"
        ready = False

    affirm = _is_affirmation(user_text)
    prompted = _seller_prompted_confirm(history)

    if mode == "seller" and ready:
        if not (affirm and prompted):
            ready = False
            if intent == "confirm":
                intent = "register"

    confirm_audit = None
    if mode == "seller" and ready:
        try:
            confirm_audit = audit_seller_confirm(slots, messages)
            slots = confirm_audit.slots
            if not confirm_audit.approved:
                ready = False
                intent = "register"
                reply = (
                    "잠깐만요. "
                    + _seller_format_summary(slots)
                    + " 맞는지 다시 확인해 주세요. 틀린 부분 있으면 다시 말씀해 주세요."
                )
        except Exception:
            ready = False
            intent = "register"

    if mode == "seller" and ready and affirm and prompted:
        intent = "confirm"

    reply = polish_tts_reply(reply)

    return {
        "reply": reply,
        "slots": slots,
        "intent": intent,
        "ready_to_confirm": ready,
        "slot_pipeline": slot_pipe.to_meta() if slot_pipe else None,
        "confirm_audit": (
            {
                "approved": confirm_audit.approved,
                "issues": confirm_audit.issues,
                "a2a_steps": confirm_audit.a2a_steps,
            }
            if confirm_audit
            else None
        ),
        "agent_pipeline_mode": pipeline_mode(),
        "demo_mode": is_demo_mode(),
    }


def _extract_slots(conversation: list[dict], schema: dict, mode: str) -> tuple[dict, str, bool]:
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
        response = anthropic_messages_create(
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
        text = anthropic_response_text(response)
        data = json.loads(text)
        intent = data.pop("intent", "other")
        ready = data.pop("ready_to_confirm", False)
        slots = {k: v for k, v in data.items() if v is not None}
        # normalize seller listing_type → kind for API
        if mode == "seller" and "listing_type" in slots:
            lt = slots.pop("listing_type")
            if isinstance(lt, str) and lt in ("product", "lodging"):
                slots["kind"] = lt
        slots = normalize_slots_locations(slots)
        return slots, intent, bool(ready)
    except Exception:
        return {}, "other", False
