"""ASR 후처리 — 규칙 보정 + A2A(에이전트 협업)로 Whisper 오타·지명 오인식 교정."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import anthropic

# Whisper가 자주 틀리는 지명·표기 (발음 유사 / 한자 혼동)
_PLACE_TYPO_MAP: dict[str, str] = {
    "값평": "가평",
    "갑평": "가평",
    "가평군": "가평군",
    "김제": "김제",
    "김재": "김제",
    "강릉": "강릉",
    "강능": "강릉",
    "속초": "속초",
    "속초시": "속초",
    "춘천": "춘천",
    "홍천": "홍천",
    "평창": "평창",
    "여수": "여수",
    "목포": "목포",
    "전주": "전주",
    "군산": "군산",
    "익산": "익산",
    "남원": "남원",
    "순천": "순천",
    "포항": "포항",
    "경주": "경주",
    "안동": "안동",
    "제주": "제주",
    "서귀포": "서귀포",
    "수원": "수원",
    "용인": "용인",
    "화성": "화성",
    "평택": "평택",
    "안산": "안산",
    "파주": "파주",
    "김포": "김포",
    "양평": "양평",
    "양평군": "양평군",
    "천안": "천안",
    "아산": "아산",
    "당진": "당진",
    "보령": "보령",
    "태안": "태안",
}

# 시·도 접두
_SIDO = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "경기도",
    "강원",
    "강원도",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
    "제주도",
)

# 짧은 이름 → 공식 행정구역 (시·군)
_PLACE_CANONICAL: dict[str, str] = {
    "가평": "가평군",
    "양평": "양평군",
    "김제": "김제시",
    "강릉": "강릉시",
    "속초": "속초시",
    "춘천": "춘천시",
    "원주": "원주시",
    "홍천": "홍천군",
    "평창": "평창군",
    "여수": "여수시",
    "목포": "목포시",
    "전주": "전주시",
    "군산": "군산시",
    "익산": "익산시",
    "순천": "순천시",
    "포항": "포항시",
    "경주": "경주시",
    "안동": "안동시",
    "제주": "제주시",
    "서귀포": "서귀포시",
    "수원": "수원시",
    "용인": "용인시",
    "화성": "화성시",
    "평택": "평택시",
    "안산": "안산시",
    "파주": "파주시",
    "김포": "김포시",
    "천안": "천안시",
    "아산": "아산시",
    "당진": "당진시",
    "보령": "보령시",
    "태안": "태안군",
}

_ASR_PHRASE_FIXES: tuple[tuple[str, str], ...] = (
    (r"글램\s*핑", "글램핑"),
    (r"민\s*박", "민박"),
    (r"펜\s*션", "펜션"),
    (r"(\d+)\s*,\s*(\d+)원", r"\1\2원"),
    (r"(\d{1,3})\s*,\s*(\d{3})원", r"\1\2원"),
)

_CORRECTOR_MODEL = os.environ.get("TTT_ASR_CORRECTOR_MODEL", "claude-sonnet-4-6")
_AUDITOR_MODEL = os.environ.get("TTT_ASR_AUDITOR_MODEL", "claude-sonnet-4-6")
_OPENAI_VERIFY_MODEL = os.environ.get("TTT_ASR_OPENAI_MODEL", "gpt-4o-mini")


@dataclass
class CorrectionResult:
    raw: str
    text: str
    rule_fixes: list[str] = field(default_factory=list)
    a2a_steps: list[dict[str, Any]] = field(default_factory=list)
    pipeline: str = "rules"


def correction_mode() -> str:
    from services.demo_config import effective_asr_correction_mode

    raw = effective_asr_correction_mode()
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


@lru_cache(maxsize=1)
def _anthropic_client() -> anthropic.Anthropic:
    from services.api_keys import anthropic_client

    return anthropic_client()


def apply_rule_corrections(text: str) -> tuple[str, list[str]]:
    out = (text or "").strip()
    fixes: list[str] = []
    if not out:
        return out, fixes

    for pattern, repl in _ASR_PHRASE_FIXES:
        new_out = re.sub(pattern, repl, out)
        if new_out != out:
            fixes.append(f"phrase:{pattern}")
            out = new_out

    for typo, canonical in _PLACE_TYPO_MAP.items():
        if typo in out and typo != canonical:
            new_out = out.replace(typo, canonical)
            if new_out != out:
                fixes.append(f"{typo}→{canonical}")
                out = new_out

    # "경기도 가평" → 행정구역 표기 보강 (값평 교정 후)
    m = re.search(r"(경기(?:도)?)\s*([가-힣]{2,4})(?:군|시)?", out)
    if m:
        sido, place = m.group(1), m.group(2)
        canon = _PLACE_CANONICAL.get(place)
        if canon:
            replacement = f"{sido} {canon}"
            old = m.group(0)
            if old != replacement and place in out:
                out = out.replace(old, replacement, 1)
                fixes.append(f"loc:{old}→{replacement}")

    for short, full in _PLACE_CANONICAL.items():
        if full in out:
            continue
        if re.search(rf"(?<![가-힣]){re.escape(short)}(?![가-힣])", out):
            new_out = re.sub(rf"(?<![가-힣]){re.escape(short)}(?![가-힣])", full, out, count=1)
            if new_out != out:
                fixes.append(f"{short}→{full}")
                out = new_out
                break

    return out, fixes


def normalize_location(location: str | None) -> str | None:
    loc = (location or "").strip()
    if not loc:
        return None

    for typo, canonical in _PLACE_TYPO_MAP.items():
        loc = loc.replace(typo, canonical)

    m = re.search(r"([가-힣]{2,6}(?:시|군|구))", loc)
    if m:
        return m.group(1)

    for short, full in _PLACE_CANONICAL.items():
        if short in loc:
            sido = next((s for s in _SIDO if s in loc), "")
            if sido and sido.endswith("도"):
                return f"{sido} {full}"
            if sido:
                return f"{sido} {full}"
            return full

    if len(loc) > 24 or (" " in loc and len(loc) > 12):
        return None
    return loc


def normalize_slots_locations(slots: dict) -> dict:
    if not slots:
        return slots
    loc = slots.get("location")
    if isinstance(loc, str) and loc.strip():
        fixed = normalize_location(loc)
        if fixed:
            slots = {**slots, "location": fixed}
    return slots


def _history_snippet(history: list[dict], limit: int = 4) -> str:
    lines: list[str] = []
    for m in (history or [])[-limit:]:
        role = m.get("role", "?")
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def _claude_json(*, model: str, system: str, user: str) -> dict:
    from services.api_keys import anthropic_messages_create, anthropic_response_text

    response = anthropic_messages_create(
        model=model,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}],
        thinking={"type": "disabled"},
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "changes": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["text", "changes", "confidence"],
                    "additionalProperties": False,
                },
            },
        },
    )
    raw = anthropic_response_text(response)
    return json.loads(raw)


def _openai_json(system: str, user: str) -> dict | None:
    from services.api_keys import call_openai_json

    return call_openai_json(system, user, model=_OPENAI_VERIFY_MODEL)


def _gemini_json(system: str, user: str) -> dict | None:
    from services.api_keys import call_gemini_json

    return call_gemini_json(system, user)


def _agent_corrector(
    raw: str,
    rule_text: str,
    *,
    mode: str,
    history: list[dict],
) -> dict:
    system = """\
당신은 Whisper ASR 교정 에이전트 A입니다.
로컬링크(농어촌 직거래·숙박 등록) 음성 입력의 오인식을 고칩니다.

규칙:
- 한국어 지명·숫자·상품명 위주로 교정 (값평→가평, 김재→김제 등).
- 의미를 바꾸거나 원문에 없는 정보(가격·이름)를 새로 만들지 마세요.
- 방언·짧은 말은 표준어로 가볍게만 정리.
- 확실할 때만 고치고, 애매하면 rule_text를 유지.
- JSON만 출력."""
    user = (
        f"모드: {mode}\n"
        f"최근 대화:\n{_history_snippet(history) or '(없음)'}\n\n"
        f"Whisper 원문: {raw}\n"
        f"규칙 보정안: {rule_text}\n"
        "최종 교정문을 text에 넣으세요."
    )
    return _claude_json(model=_CORRECTOR_MODEL, system=system, user=user)


def _agent_auditor(
    raw: str,
    proposed: str,
    *,
    mode: str,
) -> dict:
    system = """\
당신은 ASR 검수 에이전트 B입니다. 에이전트 A의 교정안을 검증합니다.

규칙:
- Whisper 원문(raw)과 발음·의미가 연결되는 교정만 승인.
- 지명 동음·유사음(값평/가평, 김재/김제)은 한국 행정구역 기준으로 고칠 수 있음.
- 원문에 없는 가격·상품명·인명을 추가하면 raw에 가까운 쪽으로 되돌림.
- JSON text에 최종 승인 문장만."""
    user = (
        f"모드: {mode}\n"
        f"Whisper 원문: {raw}\n"
        f"교정안: {proposed}\n"
        "검수 후 최종 text를 주세요."
    )
    return _claude_json(model=_AUDITOR_MODEL, system=system, user=user)


def _agent_openai_verifier(raw: str, proposed: str) -> dict | None:
    system = """\
당신은 ASR 3차 검증 에이전트 C(OpenAI)입니다.
Claude 교정 결과를 독립적으로 검토합니다.

JSON 형식:
{"text": "...", "approved": true/false, "changes": ["..."]}

원문에 없는 사실을 추가하지 마세요. 지명·숫자 오타만 교정."""
    user = f"Whisper 원문:\n{raw}\n\n교정안:\n{proposed}"
    result = _openai_json(system, user)
    if not result:
        return None
    return {
        "text": str(result.get("text") or proposed).strip(),
        "changes": result.get("changes") or [],
        "confidence": "high" if result.get("approved") else "medium",
        "agent": "openai_verifier",
    }


def _agent_gemini_verifier(raw: str, proposed: str) -> dict | None:
    system = """\
당신은 ASR 4차 검증 에이전트 D(Gemini)입니다.
Whisper 원문과 교정안을 독립 검토합니다.

JSON: {"text": "...", "approved": true/false, "changes": ["..."]}
원문에 없는 사실 추가 금지. 지명·숫자 오타만 교정."""
    user = f"Whisper 원문:\n{raw}\n\n교정안:\n{proposed}"
    result = _gemini_json(system, user)
    if not result:
        return None
    return {
        "text": str(result.get("text") or proposed).strip(),
        "changes": result.get("changes") or [],
        "confidence": "high" if result.get("approved") else "medium",
        "agent": "gemini_verifier",
    }


def correct_asr_text(
    raw: str,
    *,
    mode: str = "consumer",
    history: list[dict] | None = None,
) -> CorrectionResult:
    raw = (raw or "").strip()
    if not raw:
        return CorrectionResult(raw="", text="")

    mode_val = mode if mode in ("consumer", "seller") else "consumer"
    hist = list(history or [])
    rule_text, rule_fixes = apply_rule_corrections(raw)

    pipe = correction_mode()
    if pipe == "off":
        return CorrectionResult(
            raw=raw,
            text=raw,
            rule_fixes=[],
            pipeline="off",
        )

    if pipe == "rules" or not _anthropic_configured():
        return CorrectionResult(
            raw=raw,
            text=rule_text,
            rule_fixes=rule_fixes,
            pipeline="rules",
        )

    steps: list[dict[str, Any]] = []

    try:
        corr = _agent_corrector(raw, rule_text, mode=mode_val, history=hist)
        corr_text = (corr.get("text") or rule_text).strip()
        steps.append({"agent": "claude_corrector", **corr})

        audit = _agent_auditor(raw, corr_text, mode=mode_val)
        audit_text = (audit.get("text") or corr_text).strip()
        steps.append({"agent": "claude_auditor", **audit})

        final_text = audit_text
        pipeline = "a2a"

        if pipe == "max" and _openai_configured():
            oai = _agent_openai_verifier(raw, audit_text)
            if oai:
                final_text = (oai.get("text") or audit_text).strip()
                steps.append(oai)
                pipeline = "max"

        if pipe == "max" and _gemini_configured():
            gem = _agent_gemini_verifier(raw, final_text)
            if gem:
                final_text = (gem.get("text") or final_text).strip()
                steps.append(gem)
                pipeline = "max"

        final_text, post_fixes = apply_rule_corrections(final_text)
        rule_fixes = rule_fixes + post_fixes

        return CorrectionResult(
            raw=raw,
            text=final_text or rule_text,
            rule_fixes=rule_fixes,
            a2a_steps=steps,
            pipeline=pipeline,
        )
    except Exception as exc:
        steps.append({"agent": "error", "detail": str(exc)})
        return CorrectionResult(
            raw=raw,
            text=rule_text,
            rule_fixes=rule_fixes,
            a2a_steps=steps,
            pipeline="rules_fallback",
        )
