"""에이전트 파이프라인 — 슬롯 검수·등록 감사·콘텐츠·TTS A2A."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from services.asr_correction import (
    apply_rule_corrections,
    normalize_location,
    normalize_slots_locations,
)
from services.listings_store import get_listing, list_listings

_PIPELINE_MODEL = os.environ.get("TTT_AGENT_MODEL", "claude-sonnet-4-6")
_OPENAI_MODEL = os.environ.get("TTT_AGENT_OPENAI_MODEL", "gpt-4o-mini")

_PHONE_RE = re.compile(r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}")


@dataclass
class SlotPipelineResult:
    slots: dict
    intent: str
    ready_to_confirm: bool
    rule_fixes: list[str] = field(default_factory=list)
    a2a_steps: list[dict[str, Any]] = field(default_factory=list)
    pipeline: str = "rules"

    def to_meta(self) -> dict:
        return {
            "pipeline": self.pipeline,
            "rule_fixes": self.rule_fixes,
            "a2a_steps": self.a2a_steps,
        }


@dataclass
class ConfirmAuditResult:
    approved: bool
    slots: dict
    issues: list[str] = field(default_factory=list)
    a2a_steps: list[dict[str, Any]] = field(default_factory=list)


def pipeline_mode() -> str:
    from services.demo_config import effective_agent_pipeline_mode

    raw = effective_agent_pipeline_mode()
    if raw in ("off", "0", "false", "none"):
        return "off"
    if raw in ("rules", "rule"):
        return "rules"
    if raw in ("a2a", "llm"):
        return "a2a"
    return "max"


def _anthropic_configured() -> bool:
    from services.api_keys import is_anthropic_configured

    return is_anthropic_configured()


def _openai_configured() -> bool:
    from services.api_keys import is_openai_configured

    return is_openai_configured()


def _gemini_configured() -> bool:
    from services.api_keys import is_gemini_configured

    return is_gemini_configured()


def _conversation_text(conversation: list[dict]) -> str:
    return "\n".join(
        f"[{m.get('role', '?')}] {m.get('content', '')}"
        for m in (conversation or [])
        if m.get("content")
    )


def _user_blob(conversation: list[dict]) -> str:
    parts = [m.get("content", "") for m in (conversation or []) if m.get("role") == "user"]
    blob = " ".join(parts).strip()
    corrected, _ = apply_rule_corrections(blob)
    return corrected


def _extract_price_kr(text: str) -> int | None:
    t = re.sub(r"\s+", "", text or "")
    m = re.search(r"(\d+)만(\d{1,2})?천", t)
    if m:
        cheon = int(m.group(2)) * 1000 if m.group(2) else 0
        return int(m.group(1)) * 10000 + cheon
    m = re.search(r"(\d+)만(?:원)?", t)
    if m:
        return int(m.group(1)) * 10000
    m = re.search(r"(\d+)천(?:원)?", t)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r"(\d{1,9})원", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,3}),(\d{3})", t)
    if m:
        return int(m.group(1)) * 1000 + int(m.group(2))
    m = re.search(r"(\d{4,9})", t)
    if m and int(m.group(1)) >= 1000:
        return int(m.group(1))
    return None


def _normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 9:
        return str(raw).strip()
    if digits.startswith("82"):
        digits = "0" + digits[2:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return str(raw).strip()


def _rule_fix_slots(slots: dict, conversation: list[dict], mode: str) -> tuple[dict, list[str]]:
    out = dict(slots or {})
    fixes: list[str] = []
    blob = _user_blob(conversation)

    loc = normalize_location(out.get("location")) or normalize_location(blob)
    if loc:
        old = out.get("location")
        sido = next((s for s in ("경기도", "강원도", "전라북도", "전북", "제주도", "제주") if s in blob), "")
        if sido and loc and not str(loc).startswith(sido.replace("전북", "전라북도")):
            if "전북" in sido:
                full = f"전북 {loc}"
            elif sido.endswith("도"):
                full = f"{sido} {loc}"
            else:
                full = f"{sido} {loc}"
            loc = full
        if old != loc:
            out["location"] = loc
            fixes.append(f"location:{old}→{loc}")

    price = _extract_price_kr(blob)
    if price is not None and out.get("price") != price:
        old = out.get("price")
        out["price"] = price
        fixes.append(f"price:{old}→{price}")

    if mode == "consumer":
        phone = out.get("contact_phone")
        norm = _normalize_phone(str(phone) if phone else None)
        if norm and norm != phone:
            out["contact_phone"] = norm
            fixes.append("contact_phone:formatted")

        qty = out.get("quantity")
        if qty is not None:
            try:
                q = int(qty)
                if q < 1:
                    out["quantity"] = 1
                    fixes.append("quantity:min1")
                elif q > 99:
                    out["quantity"] = 99
                    fixes.append("quantity:cap99")
            except (TypeError, ValueError):
                out["quantity"] = 1
                fixes.append("quantity:default1")

        lid = out.get("listing_id")
        if lid and not get_listing(str(lid)):
            titles = {x.get("id"): x.get("title", "") for x in list_listings()}
            blob_l = blob.lower()
            for listing_id, title in titles.items():
                if title and title[:8] in blob:
                    out["listing_id"] = listing_id
                    fixes.append(f"listing_id:{lid}→{listing_id}")
                    break

    if mode == "seller":
        title = str(out.get("title") or "").strip()
        if title:
            fixed, _ = apply_rule_corrections(title)
            if fixed != title:
                out["title"] = fixed
                fixes.append("title:asr_fix")

        kind = out.get("kind")
        if kind not in ("product", "lodging"):
            if re.search(r"숙박|민박|글램핑|펜션|숙소", blob):
                out["kind"] = "lodging"
                fixes.append("kind→lodging")
            elif re.search(r"상품|팔|쌀|키로|킬로", blob):
                out["kind"] = "product"
                fixes.append("kind→product")

        # 명령형/도움 요청 발화가 슬롯에 잘못 들어간 경우 제거.
        # ("노트 사진으로 채우려고" 같은 발화가 location/title 로 들어가는 사고 방지)
        for key in ("location", "title", "description"):
            v = out.get(key)
            if isinstance(v, str) and _looks_like_command(v):
                out[key] = "" if key != "title" else None
                fixes.append(f"{key}:removed_command_phrase")

    return normalize_slots_locations(out), fixes


_COMMAND_PATTERN = re.compile(
    r"(노트\s*사진|메모\s*사진|사진(으|을|로)?\s*(채워|찍|올려|입력|보고|읽)|"
    r"OCR|글\s*(써|만들|적어)|소개\s*글|설명\s*(써|만들|채워|적어)|"
    r"AI(로|가|에게|한테)?\s*(써|만들|그려|채워|해)|"
    r"(이미지|그림|대표\s*사진)\s*(만들|그려|생성|찍)|"
    r"(채워|만들어|그려|써|적어|올려|등록(해|할게)|확인(해|할게))(\s*주(세요|시겠어요|시오)?)?|"
    r"채우(려고|려|어\s*줘|러)|적으(려고|려|어\s*줘))"
)


def _looks_like_command(text: str) -> bool:
    """노트 사진으로 채우려고 / AI로 글 써줘 같은 명령형 발화를 식별."""
    t = (text or "").strip()
    if not t:
        return False
    # 행정구역 표기가 있으면 location 일 가능성 높으므로 명령으로 판정하지 않는다.
    if re.search(r"(특별시|광역시|도|시|군|구|읍|면|동|리)$", t):
        return False
    return bool(_COMMAND_PATTERN.search(t))


# 마켓(택배·픽업) 상품에서는 "체험"류 단어가 어울리지 않으므로 자연스러운 표현으로 치환.
_EXPERIENCE_WORD_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"체험해\s*보세요"), "맛보세요"),
    (re.compile(r"체험할\s*수\s*있"), "느끼실 수 있"),
    (re.compile(r"체험을\s*하"), "직접 즐기"),
    (re.compile(r"체험하시"), "즐기시"),
    (re.compile(r"체험하"), "즐기"),
    (re.compile(r"체험을\s*"), "맛을 "),
    (re.compile(r"체험\s*프로그램"), "상품"),
    (re.compile(r"체험\s*"), "맛 "),
    (re.compile(r"체험"), "맛"),
    (re.compile(r"견학"), "방문"),
    (re.compile(r"프로그램"), "상품"),
]


def _strip_experience_words(text: str) -> str:
    """마켓 상품 본문에서 '체험'류 단어를 자연스러운 단어로 바꿔 준다."""
    out = text or ""
    for pat, rep in _EXPERIENCE_WORD_REPLACEMENTS:
        out = pat.sub(rep, out)
    return out


def strip_experience_in_package(pkg: dict) -> dict:
    """마켓 상품 패키지(JSON)에서 텍스트 필드의 '체험' 단어를 모두 정리."""
    if not isinstance(pkg, dict):
        return pkg
    for key in ("description", "refund_policy", "address", "meeting_place"):
        v = pkg.get(key)
        if isinstance(v, str):
            pkg[key] = _strip_experience_words(v)
    for key in ("highlights", "included", "not_included", "precautions"):
        v = pkg.get(key)
        if isinstance(v, list):
            pkg[key] = [
                _strip_experience_words(s) if isinstance(s, str) else s for s in v
            ]
    steps = pkg.get("steps")
    if isinstance(steps, list):
        for st in steps:
            if isinstance(st, dict):
                for sk in ("title", "body"):
                    sv = st.get(sk)
                    if isinstance(sv, str):
                        st[sk] = _strip_experience_words(sv)
    return pkg


def _claude_json(system: str, user: str, schema: dict) -> dict | None:
    from services.api_keys import anthropic_messages_create, anthropic_response_text

    if not _anthropic_configured():
        return None
    try:
        response = anthropic_messages_create(
            model=_PIPELINE_MODEL,
            max_tokens=700,
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


def _openai_json(system: str, user: str) -> dict | None:
    from services.api_keys import call_openai_json

    return call_openai_json(system, user, model=_OPENAI_MODEL)


def _gemini_json(system: str, user: str) -> dict | None:
    from services.api_keys import call_gemini_json

    return call_gemini_json(system, user)


_SLOT_VALIDATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "slots": {
            "type": "object",
            "properties": {
                "kind": {"type": ["string", "null"]},
                "listing_type": {"type": ["string", "null"]},
                "title": {"type": ["string", "null"]},
                "price": {"type": ["integer", "null"]},
                "description": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "stock": {"type": ["integer", "null"]},
                "max_guests": {"type": ["integer", "null"]},
                "listing_id": {"type": ["string", "null"]},
                "quantity": {"type": ["integer", "null"]},
                "contact_name": {"type": ["string", "null"]},
                "contact_phone": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "ready_to_confirm": {"type": "boolean"},
        "fixes": {"type": "array", "items": {"type": "string"}},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slots", "ready_to_confirm", "fixes", "issues"],
    "additionalProperties": False,
}


def run_slot_pipeline(
    conversation: list[dict],
    slots: dict,
    intent: str,
    ready_to_confirm: bool,
    mode: str,
) -> SlotPipelineResult:
    mode_val = mode if mode in ("consumer", "seller") else "consumer"
    fixed, rule_fixes = _rule_fix_slots(slots, conversation, mode_val)

    pipe = pipeline_mode()
    if pipe == "off":
        return SlotPipelineResult(
            slots=fixed,
            intent=intent,
            ready_to_confirm=ready_to_confirm,
            pipeline="off",
        )

    if pipe == "rules" or not _anthropic_configured():
        ready = _rule_ready(fixed, ready_to_confirm, mode_val, conversation)
        return SlotPipelineResult(
            slots=fixed,
            intent=intent,
            ready_to_confirm=ready,
            rule_fixes=rule_fixes,
            pipeline="rules",
        )

    steps: list[dict[str, Any]] = []
    system = """\
당신은 슬롯 검수 에이전트입니다. 대화와 추출된 슬롯을 비교해 교정합니다.

규칙:
- 사용자가 말한 가격·지명·제목·연락처만 반영. 새 정보 금지.
- 값평→가평군, 김재→김제시 등 지명 오타 교정.
- ready_to_confirm은 필수 슬롯이 대화와 일치할 때만 true.
- issues에 남은 불일치를 적으세요."""
    user = (
        f"모드: {mode_val}\n"
        f"intent: {intent}\n"
        f"대화:\n{_conversation_text(conversation)}\n\n"
        f"현재 슬롯(JSON): {json.dumps(fixed, ensure_ascii=False)}\n"
        f"ready_to_confirm 후보: {ready_to_confirm}"
    )
    data = _claude_json(system, user, _SLOT_VALIDATOR_SCHEMA)
    if data:
        steps.append({"agent": "claude_slot_validator", **data})
        merged = {**fixed, **(data.get("slots") or {})}
        merged = normalize_slots_locations(merged)
        ready = bool(data.get("ready_to_confirm", ready_to_confirm))
        if data.get("issues"):
            ready = False
        pipeline = "a2a"
    else:
        merged = fixed
        ready = _rule_ready(fixed, ready_to_confirm, mode_val, conversation)
        pipeline = "rules_fallback"

    if pipe == "max" and _openai_configured() and data:
        oai = _openai_json(
            "슬롯 검수 2차. JSON: {slots:{...}, ready_to_confirm:bool, fixes:[]}",
            f"대화:\n{_conversation_text(conversation)}\n슬롯:{json.dumps(merged, ensure_ascii=False)}",
        )
        if oai and oai.get("slots"):
            steps.append({"agent": "openai_slot_reviewer", **oai})
            merged = normalize_slots_locations({**merged, **oai["slots"]})
            if "ready_to_confirm" in oai:
                ready = bool(oai["ready_to_confirm"])
            pipeline = "max"

    if pipe == "max" and _gemini_configured() and data:
        gem = _gemini_json(
            "슬롯 검수 3차(Gemini). JSON: {slots:{...}, ready_to_confirm:bool, fixes:[]}",
            f"대화:\n{_conversation_text(conversation)}\n슬롯:{json.dumps(merged, ensure_ascii=False)}",
        )
        if gem and gem.get("slots"):
            steps.append({"agent": "gemini_slot_reviewer", **gem})
            merged = normalize_slots_locations({**merged, **gem["slots"]})
            if "ready_to_confirm" in gem:
                ready = bool(gem["ready_to_confirm"])
            pipeline = "max"

    merged, post = _rule_fix_slots(merged, conversation, mode_val)
    rule_fixes = rule_fixes + post

    return SlotPipelineResult(
        slots=merged,
        intent=intent,
        ready_to_confirm=ready,
        rule_fixes=rule_fixes,
        a2a_steps=steps,
        pipeline=pipeline,
    )


def _rule_ready(slots: dict, ready: bool, mode: str, conversation: list[dict]) -> bool:
    if not ready:
        return False
    blob = _user_blob(conversation)
    if mode == "seller":
        if slots.get("kind") not in ("product", "lodging"):
            return False
        if not str(slots.get("title") or "").strip():
            return False
        if not str(slots.get("location") or "").strip():
            return False
        if not isinstance(slots.get("price"), int) or slots["price"] < 0:
            return False
        if "값평" in str(slots.get("location", "")):
            return False
        price_in_blob = _extract_price_kr(blob)
        if price_in_blob is not None and slots.get("price") != price_in_blob:
            return False
        return True
    if mode == "consumer":
        if not slots.get("listing_id") or not get_listing(str(slots["listing_id"])):
            return False
        if not str(slots.get("contact_name") or "").strip():
            return False
        if not str(slots.get("contact_phone") or "").strip():
            return False
        return True
    return ready


def audit_seller_confirm(slots: dict, conversation: list[dict]) -> ConfirmAuditResult:
    fixed, _ = _rule_fix_slots(slots, conversation, "seller")
    issues: list[str] = []

    if "값평" in str(fixed.get("location", "")):
        issues.append("location_typo")
    price = fixed.get("price")
    if isinstance(price, int) and (price < 100 or price > 50_000_000):
        issues.append("price_out_of_range")
    if not str(fixed.get("title") or "").strip():
        issues.append("title_missing")

    if pipeline_mode() in ("off", "rules") or not _anthropic_configured():
        return ConfirmAuditResult(
            approved=not issues,
            slots=fixed,
            issues=issues,
        )

    schema = {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
            "slots": {"type": "object", "additionalProperties": True},
        },
        "required": ["approved", "issues", "slots"],
        "additionalProperties": False,
    }
    data = _claude_json(
        "판매 등록 확정 전 감사 에이전트. 허위·누락·지명 오타를 잡습니다. JSON만.",
        f"대화:\n{_conversation_text(conversation)}\n\n슬롯:{json.dumps(fixed, ensure_ascii=False)}",
        schema,
    )
    steps: list[dict] = []
    if data:
        steps.append({"agent": "claude_confirm_auditor", **data})
        fixed = normalize_slots_locations({**fixed, **(data.get("slots") or {})})
        issues = list(data.get("issues") or issues)
        approved = bool(data.get("approved")) and not issues
    else:
        approved = not issues

    return ConfirmAuditResult(
        approved=approved,
        slots=fixed,
        issues=issues,
        a2a_steps=steps,
    )


def audit_listing_copy(
    description: str,
    *,
    title: str,
    price: int,
    location: str,
    is_market_product: bool = False,
) -> str:
    text = (description or "").strip()
    if not text:
        return text
    fixed, fixes = apply_rule_corrections(text)
    loc = normalize_location(location) or location
    if is_market_product:
        fixed = _strip_experience_words(fixed)
    if pipeline_mode() == "off" or not _anthropic_configured():
        return fixed

    schema = {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "fixes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["description", "fixes"],
        "additionalProperties": False,
    }
    data = _claude_json(
        (
            "당신은 농수산·체험 마켓의 상품 설명 사실 검수자입니다. "
            "원문의 분량·문장 수·말투·정보량을 그대로 유지하면서, 가격·지역·제목과 맞지 않는 "
            "부분이나 허위 인증·과장된 수치만 살짝 수정합니다. 본문을 새로 쓰거나 짧게 요약해서는 "
            "안 됩니다. 위반 내용이 없으면 원문을 그대로 description 에 돌려주세요. "
            "fixes 에는 실제로 고친 부분만 짧게 나열합니다. 출력은 반드시 JSON 한 개입니다."
        ),
        f"제목: {title}\n가격: {price}\n지역: {loc}\n원문 설명:\n{fixed}",
        schema,
    )
    audited = str((data or {}).get("description") or "").strip()
    # LLM 이 본문을 통째로 짧은 placeholder 로 바꿔버리는 케이스가 있어
    # 결과가 원문의 절반 미만이면 원문을 그대로 사용한다.
    if audited and len(audited) >= max(40, len(fixed) // 2):
        return audited
    return fixed


def verify_image_prompt_a2a(
    prompt_en: str,
    *,
    kind: str,
    title: str,
    description: str = "",
    category: str = "rural",
) -> tuple[str, dict]:
    prompt = (prompt_en or "").strip()
    meta: dict = {"pipeline": "rules", "steps": []}
    if not prompt:
        return prompt, meta

    title_l = f"{title} {description}".lower()
    is_exp = any(h in title_l for h in ("낚시", "체험", "투어", "수확", "글램핑", "캠핑"))
    bad_food = is_exp and any(
        w in prompt.lower() for w in ("plate", "dish", "restaurant", "fine dining", "served on table")
    )
    if bad_food:
        prompt = re.sub(
            r"(?i)(plate|dish|restaurant|fine dining)[^.]*\.?",
            "",
            prompt,
        )
        meta["steps"].append({"agent": "rule_scene", "fix": "removed_food_scene"})

    if pipeline_mode() in ("off", "rules") or not _anthropic_configured():
        return prompt, meta

    schema = {
        "type": "object",
        "properties": {
            "prompt_en": {"type": "string"},
            "approved": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["prompt_en", "approved", "issues"],
        "additionalProperties": False,
    }
    data = _claude_json(
        "이미지 프롬프트 장면 검수. 체험/낚시/글램핑은 활동 장면, 특산품은 상품 사진. JSON만.",
        f"kind:{kind}\ncategory:{category}\ntitle:{title}\ndescription:{description}\nprompt:{prompt}",
        schema,
    )
    if data and data.get("prompt_en"):
        meta["steps"].append({"agent": "claude_image_auditor", **data})
        meta["pipeline"] = "a2a"
        return str(data["prompt_en"]).strip()[:3800], meta
    return prompt, meta


def audit_sns_copy(draft: dict) -> dict:
    if pipeline_mode() == "off" or not _anthropic_configured():
        out = dict(draft)
        for key in ("instagram", "facebook"):
            if key in out and isinstance(out[key], str):
                out[key], _ = apply_rule_corrections(out[key])
        return out

    schema = {
        "type": "object",
        "properties": {
            "instagram": {"type": "string"},
            "facebook": {"type": "string"},
            "hashtags": {"type": "string"},
            "fixes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["instagram", "hashtags", "fixes"],
        "additionalProperties": True,
    }
    data = _claude_json(
        "SNS 초안 검수. 과장·허위 제거, 지명 오타 교정. JSON만.",
        json.dumps(draft, ensure_ascii=False),
        schema,
    )
    if not data:
        return draft
    return {**draft, **{k: data[k] for k in ("instagram", "facebook", "hashtags") if k in data}}


def polish_tts_reply(reply: str) -> str:
    text = (reply or "").strip()
    if not text:
        return text

    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"```\w*\s*", "", text)
    cut = re.search(r"\n\s*\{", text)
    if cut:
        text = text[: cut.start()]
    cut = re.search(r'\{\s*"(?:intent|ready_to_confirm|listing_type|slots|title|price)"\s*:', text)
    if cut:
        text = text[: cut.start()]
    text = text.strip().rstrip("`").strip()
    if not text:
        return text

    if len(text) <= 120:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    short = " ".join(parts[:2]).strip()
    if len(short) >= 20:
        return short
    return text[:120].rstrip() + "…"


_OCR_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": ["string", "null"]},
        "price": {"type": ["integer", "string", "null"]},
        "quantity": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "issues": {"type": "array", "items": {"type": "string"}},
        "fixes": {"type": "array", "items": {"type": "string"}},
        "needs_review_keys": {"type": "array", "items": {"type": "string"}},
        "approved": {"type": "boolean"},
    },
    "required": ["issues", "fixes", "needs_review_keys", "approved"],
    "additionalProperties": False,
}


def _ocr_audit_value(fields: dict, key: str) -> Any:
    item = fields.get(key) if isinstance(fields, dict) else None
    if isinstance(item, dict):
        return item.get("value")
    return item


def audit_ocr_listing(
    fields: dict[str, dict],
    *,
    raw_text: str,
    listing_tab: str | None = None,
) -> tuple[dict[str, dict], list[dict[str, Any]]]:
    """OCR 1차 결과(`fields`)를 다중 에이전트로 검수·보강.

    - A2(Claude 텍스트): 행정구역·단위·일관성을 보고 수정안 제안. 적용된 항목은
      해당 field 의 needs_review=False 로 내려가며 confidence 가 살짝 올라간다.
    - A3(OpenAI gpt-4o-mini, max 모드): 행정구역 모순만 따로 한 번 더 점검.
    두 단계 모두 실패해도 원본 fields 를 그대로 돌려준다.

    반환: (검수된 fields, a2a_steps 메타데이터 배열)
    """
    steps: list[dict[str, Any]] = []
    fields = dict(fields or {})
    mode = pipeline_mode()
    if mode == "off":
        return fields, steps

    title = _ocr_audit_value(fields, "title") or ""
    price_raw = _ocr_audit_value(fields, "price")
    quantity = _ocr_audit_value(fields, "quantity") or ""
    location = _ocr_audit_value(fields, "location") or ""
    description = _ocr_audit_value(fields, "description") or ""

    # A2 — Claude 검수자
    if _anthropic_configured():
        system = (
            "당신은 한국 농어촌 셀러 메모 OCR 검수자입니다. "
            "1차 OCR 결과를 받아 행정구역·가격·단위·제목 일관성을 검증하고, "
            "오류만 최소한으로 교정합니다. 본문을 새로 쓰지 마세요. "
            "특히 location 은 시·도 + 시·군·구 + 읍·면·동 순으로 가능한 한 풍부해야 하며, "
            "「경상북도 vs 경상남도」, 「전라북도 vs 전라남도」, 「충청북도 vs 충청남도」를 "
            "절대 혼동하지 마세요. 면·동 이름이 어느 시·군·도에 속하는지로 추론하세요. "
            "예) 기계면→경상북도 포항시 북구 기계면. 가야면→경상남도 합천군 가야면. "
            "교정이 필요 없으면 approved=true 로 두고 fixes 는 비웁니다. "
            "출력은 반드시 JSON 한 개. 값을 바꾼 경우만 해당 키에 새 값을 쓰세요. "
            "fixes 배열 항목은 「어르신께 보여드릴 안내문」이라고 생각하고 작성하세요. "
            "규칙: (1) 영어 단어(price, notes, description, highlights 등)나 약어를 절대 쓰지 말고 "
            "한국어로만 적습니다. (2) 한 항목은 한 문장(20자 내외)으로 짧고 부드럽게. "
            "(3) 숫자·금액·단위는 그대로 두되, 코드 표기(`field=value`, JSON 등)는 금지. "
            "예) ‘가격을 100g 기준 13,000원으로 정리했어요.’, ‘경상북도 포항시까지 같이 적어 두었어요.’"
        )
        user = (
            f"등록 유형: {listing_tab or 'product'}\n"
            f"raw_text:\n{raw_text}\n\n"
            f"1차 결과:\n"
            f"- title: {title}\n"
            f"- price: {price_raw}\n"
            f"- quantity: {quantity}\n"
            f"- location: {location}\n"
            f"- description: {description}\n"
        )
        data = _claude_json(system, user, _OCR_AUDIT_SCHEMA)
        if data is not None:
            applied: list[str] = []
            for key in ("title", "price", "quantity", "location", "description"):
                new_val = data.get(key)
                if new_val is None:
                    continue
                if isinstance(new_val, str) and not new_val.strip():
                    continue
                if key in fields and isinstance(fields[key], dict):
                    old = fields[key].get("value")
                    if old != new_val:
                        fields[key] = {
                            **fields[key],
                            "value": new_val,
                            "confidence": min(
                                1.0, float(fields[key].get("confidence") or 0.6) + 0.1
                            ),
                            "needs_review": False,
                        }
                        applied.append(key)
                else:
                    fields[key] = {
                        "value": new_val,
                        "confidence": 0.7,
                        "needs_review": False,
                    }
                    applied.append(key)
            review_keys = [
                k for k in (data.get("needs_review_keys") or []) if isinstance(k, str)
            ]
            for k in review_keys:
                if k in fields and isinstance(fields[k], dict):
                    fields[k] = {**fields[k], "needs_review": True}
            steps.append(
                {
                    "agent": "claude_ocr_auditor",
                    "approved": bool(data.get("approved")),
                    "applied": applied,
                    "issues": [
                        s for s in (data.get("issues") or []) if isinstance(s, str)
                    ][:5],
                    "fixes": [
                        s for s in (data.get("fixes") or []) if isinstance(s, str)
                    ][:5],
                    "needs_review_keys": review_keys,
                }
            )

    # A3 — OpenAI 교차 검증 (max 모드 + 키 있을 때만)
    if mode == "max" and _openai_configured():
        loc_after = _ocr_audit_value(fields, "location") or ""
        title_after = _ocr_audit_value(fields, "title") or ""
        verifier_system = (
            "한국 행정구역 검증자. 입력된 location 표기가 실제로 존재하는지 확인하고, "
            "모순이 있으면 corrected 에 정정안을 적습니다. 출력은 JSON 한 개: "
            '{"approved": bool, "corrected": "...", "issues": ["..."]}'
        )
        verifier_user = f"title: {title_after}\nlocation: {loc_after}\nraw_text:\n{raw_text}"
        v = _openai_json(verifier_system, verifier_user)
        if v:
            corrected = str(v.get("corrected") or "").strip()
            approved = bool(v.get("approved"))
            if not approved and corrected and corrected != loc_after:
                if "location" in fields and isinstance(fields["location"], dict):
                    fields["location"] = {
                        **fields["location"],
                        "value": corrected,
                        "needs_review": False,
                        "confidence": min(
                            1.0,
                            float(fields["location"].get("confidence") or 0.7) + 0.1,
                        ),
                    }
                else:
                    fields["location"] = {
                        "value": corrected,
                        "confidence": 0.75,
                        "needs_review": False,
                    }
            steps.append(
                {
                    "agent": "openai_ocr_verifier",
                    "approved": approved,
                    "corrected_location": corrected if not approved else "",
                    "issues": [
                        s for s in (v.get("issues") or []) if isinstance(s, str)
                    ][:5],
                }
            )

    return fields, steps
