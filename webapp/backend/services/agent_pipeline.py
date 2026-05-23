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

    return normalize_slots_locations(out), fixes


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


def audit_listing_copy(description: str, *, title: str, price: int, location: str) -> str:
    text = (description or "").strip()
    if not text:
        return text
    fixed, fixes = apply_rule_corrections(text)
    loc = normalize_location(location) or location
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
        "상품 설명 사실 검수. 가격·지역·제목과 맞게 다듬고 허위 인증·수치는 제거. JSON만.",
        f"제목:{title}\n가격:{price}\n지역:{loc}\n설명:{fixed}",
        schema,
    )
    if data and data.get("description"):
        return str(data["description"]).strip()
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
