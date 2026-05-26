"""수기 메모 이미지 OCR → 상품 등록 초안 (Claude Vision)."""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured

DEFAULT_MODEL = "claude-sonnet-4-6"
_MAX_IMAGES = 5
_MIN_EDGE_PX = 800

_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "number", "null"]},
        "confidence": {"type": "number"},
        "needs_review": {"type": "boolean"},
    },
    "required": ["value", "confidence"],
    "additionalProperties": False,
}

_LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "registration_type": {
            "type": "string",
            "enum": ["product", "reservation", "order"],
        },
        "listing_tab": {
            "type": "string",
            "enum": ["product", "lodging", "experience"],
        },
        "confidence_overall": {"type": "number"},
        "raw_text": {"type": "string"},
        "fields": {
            "type": "object",
            "properties": {
                "title": _FIELD_SCHEMA,
                "price": _FIELD_SCHEMA,
                "quantity": _FIELD_SCHEMA,
                "location": _FIELD_SCHEMA,
                "description": _FIELD_SCHEMA,
                "notes": _FIELD_SCHEMA,
                "customer_name": _FIELD_SCHEMA,
                "date_time": _FIELD_SCHEMA,
                "contact_phone": _FIELD_SCHEMA,
            },
            # 상품 상세 정보(unit/origin/producer/shelf_life/storage_method)는
            # Anthropic optional 파라미터 한도(24) 초과 방지를 위해 schema 에 두지
            # 않고, description/notes/raw_text 에서 백엔드 정규식으로 추출한다.
            "additionalProperties": False,
        },
        "missing_required": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["registration_type", "listing_tab", "confidence_overall", "fields", "raw_text"],
    "additionalProperties": False,
}


def _field(value: str | int | None, confidence: float, *, needs_review: bool | None = None) -> dict:
    conf = max(0.0, min(1.0, float(confidence)))
    return {
        "value": value,
        "confidence": conf,
        "needs_review": needs_review if needs_review is not None else conf < 0.7,
    }


def _decode_image(data_url_or_b64: str) -> tuple[bytes, str]:
    """이미지 bytes → JPEG로 정규화 (Vision API media_type 불일치 방지)."""
    raw = (data_url_or_b64 or "").strip()
    if raw.startswith("data:"):
        _, _, raw = raw.partition(",")
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("invalid image base64") from exc
    if len(data) < 32:
        raise ValueError("image too small")

    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue(), "image/jpeg"
    except Exception:
        # PIL 실패 시 원본 그대로 — media_type 추정
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return data, "image/png"
        if data[:2] == b"\xff\xd8":
            return data, "image/jpeg"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return data, "image/webp"
        return data, "image/jpeg"


def _image_quality_warnings(data: bytes) -> list[str]:
    warnings: list[str] = []
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            if min(w, h) < _MIN_EDGE_PX:
                warnings.append(
                    f"해상도가 낮습니다({w}×{h}). 선명한 사진으로 다시 올려 주세요."
                )
    except Exception:
        pass
    return warnings


def _parse_first_price(val: Any) -> int | str | None:
    """다중 단가 문자열 → 첫 번째 원화 금액."""
    if val is None:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        n = int(val)
        return n if 0 < n < 100_000_000 else None
    s = str(val).strip()
    if not s:
        return None
    first = re.split(r"[/|,;]+", s)[0].strip()
    m = re.search(r"(\d[\d,]*)", first)
    if not m:
        return s
    n = int(m.group(1).replace(",", ""))
    return n if 0 < n < 100_000_000 else s


# 메모에 자주 등장하는 한국어 라벨 → 상세 키.
# 값은 「줄바꿈」 또는 「다음 알려진 라벨 직전」까지 잡고, 괄호 안의 쉼표는 허용.
# 단어 자체가 값 안에 자주 들어가는 「농원」, 단독 「보관」은 라벨 후보에서 뺀다
# (예: "기계 햇살 농원", "서늘한 곳 보관" 같은 값이 잘리는 것을 방지).
_DETAIL_LABELS: list[tuple[str, list[str]]] = [
    ("producer", [r"생\s*산\s*자", r"농\s*가\s*명?"]),
    ("shelf_life", [r"유\s*통\s*기\s*한", r"소\s*비\s*기\s*한", r"보\s*존\s*기\s*간"]),
    ("storage_method", [r"보\s*관\s*방\s*법", r"보\s*관\s*법"]),
    ("origin", [r"원\s*산\s*지", r"생\s*산\s*지"]),
    ("unit", [r"1\s*개\s*단위", r"판매\s*단위"]),
]
# 모든 라벨 후보 (다음 라벨 만나면 값 끝).
_ALL_LABELS_RE = "|".join(p for _, ps in _DETAIL_LABELS for p in ps)


def _extract_details_from_text(text: str) -> dict[str, str]:
    """메모/설명 텍스트에서 5개 상세 키를 정규식으로 떼어낸다.

    값 추출 규칙:
    - 라벨 다음 ':' 또는 '：' 가 있으면 그 뒤부터, 없으면 공백 뒤부터.
    - 줄바꿈 또는 「다음 알려진 라벨」 만날 때까지 캡처.
    - 괄호 안의 쉼표는 값의 일부로 보존.
    """
    out: dict[str, str] = {}
    if not text:
        return out
    for key, label_patterns in _DETAIL_LABELS:
        label_alt = "|".join(label_patterns)
        # `(?:^|\\b|[\\s.,;])` 라벨 앞 경계, `[:：]?` 콜론 선택, 다음 라벨 직전까지.
        regex = re.compile(
            rf"(?:^|[\s.,;·/])(?:{label_alt})\s*[:：]?\s*"
            rf"(.+?)"
            rf"(?=(?:\n|\s+(?:{_ALL_LABELS_RE})\s*[:：]?)|$)",
            re.S,
        )
        m = regex.search(text)
        if not m:
            continue
        val = (m.group(1) or "").strip()
        # 끝의 잡 구두점 정리 (단, 괄호는 보존).
        val = re.sub(r"[\s.,;·/]+$", "", val)
        # 값이 다른 라벨 키워드 자체이면 무시.
        if not val or len(val) < 1:
            continue
        if re.fullmatch(rf"(?:{_ALL_LABELS_RE})", val):
            continue
        out[key] = val[:120]
    return out


def _augment_details_from_blob(fields: dict[str, dict]) -> None:
    """description/notes에 묻혀 들어온 상세 정보를 별도 키로 승격."""
    description = str((fields.get("description") or {}).get("value") or "")
    notes = str((fields.get("notes") or {}).get("value") or "")
    blob = "\n".join(p for p in (description, notes) if p)
    if not blob:
        return
    extracted = _extract_details_from_text(blob)
    for key, val in extracted.items():
        # 이미 LLM 이 그 키를 채워줬으면 건드리지 않는다.
        existing = fields.get(key)
        if existing and str(existing.get("value") or "").strip():
            continue
        fields[key] = _field(val, 0.65)


def _normalize_fields(raw: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
    for key, item in fields.items():
        if not isinstance(item, dict):
            continue
        val = item.get("value")
        if val is not None and not isinstance(val, (str, int, float)):
            val = str(val)
        if isinstance(val, float) and key == "price":
            val = int(val)
        if key == "price":
            val = _parse_first_price(val)
        if key == "location" and val is not None:
            loc = str(val).strip()
            loc = re.sub(r"^국산\s*[·\-/]?\s*", "", loc, flags=re.I)
            loc = re.sub(r"^국내산\s*[·\-/]?\s*", "", loc, flags=re.I)
            loc = re.sub(r"^\(([^)]+)\)$", r"\1", loc)
            val = loc.strip()
        conf = item.get("confidence", 0.5)
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            conf_f = 0.5
        needs = item.get("needs_review")
        out[key] = _field(val, conf_f, needs_review=needs if isinstance(needs, bool) else None)
    return out


def _fallback_from_text(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    price = None
    m = re.search(r"(\d[\d,]*)\s*원", t)
    if m:
        price = int(m.group(1).replace(",", ""))
    qty = None
    mq = re.search(r"(\d+)\s*(kg|킬로|키로|개|묶음|박스|명|인)", t, re.I)
    if mq:
        qty = f"{mq.group(1)}{mq.group(2)}"
    title = ""
    for line in t.splitlines():
        line = line.strip()
        if line and "원" not in line and len(line) >= 2:
            title = line[:80]
            break
    fields: dict[str, dict] = {}
    if title:
        fields["title"] = _field(title, 0.45)
    if price is not None:
        fields["price"] = _field(price, 0.5)
    if qty:
        fields["quantity"] = _field(qty, 0.45)
    if len(t) > 20:
        fields["description"] = _field(t[:400], 0.4)
    return {
        "registration_type": "product",
        "listing_tab": "product",
        "confidence_overall": 0.35,
        "raw_text": t,
        "fields": fields,
        "missing_required": [k for k in ("title", "price") if k not in fields],
        "warnings": ["OCR 신뢰도가 낮습니다. 직접 확인·수정해 주세요."],
    }


def parse_note_images(
    images_b64: list[str],
    *,
    hint_tab: str | None = None,
) -> dict[str, Any]:
    """수기 메모 이미지(최대 5장) → 등록 초안 JSON."""
    if not images_b64:
        raise ValueError("image required")
    if len(images_b64) > _MAX_IMAGES:
        raise ValueError(f"max {_MAX_IMAGES} images")

    warnings: list[str] = []
    content: list[dict[str, Any]] = []
    for i, src in enumerate(images_b64):
        data, media = _decode_image(src)
        warnings.extend(_image_quality_warnings(data))
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
        )

    tab_hint = ""
    if hint_tab in ("product", "lodging", "experience"):
        tab_hint = f"\n셀러가 선택한 등록 유형 힌트: {hint_tab}"

    prompt = f"""한국 농어촌 셀러의 수기 메모·포스트잇·종이 영수증 사진입니다.
OCR로 읽고 JSON만 출력하세요.{tab_hint}

목표:
1) registration_type: product(상품) | reservation(예약) | order(주문) 중 분류
2) listing_tab: product(농축수산·가공품) | lodging(숙박·민박) | experience(체험·투어)
3) fields 각 항목: value, confidence(0~1), needs_review(confidence<0.7이면 true)

상품 필드: title(필수), price 원 단위 숫자(필수), quantity(kg/개 등), location(시·군·동네),
description(특이사항·무농약 등), notes
description 에는 메모에 적힌 다음 항목을 「라벨: 값」 형태로 줄바꿈으로 정확히 옮겨 적어 주세요
(별도 키는 만들지 말고 description 한 칸에 모아 적습니다):
- 생산자: ... (혹은 농가명: ...)
- 유통기한: ...
- 보관방법: ...
- 원산지: ... (location 보다 더 구체적인 표기 — 농가·읍·리까지 들어가면 좋아요)
이 4개 라벨은 메모에 적혀 있을 때만 줄을 추가하고, 없으면 생략하세요. 라벨 표기·값은 메모 그대로 옮겨 적되, 줄바꿈은 \n 으로 구분해 주세요.
예약/주문 필드: customer_name, date_time, quantity(인원), contact_phone(마스킹 010-****-1234),
title(품목/체험명)

규칙:
- 방언·약어 이해 (햅쌀, 수미감자, 갯벌체험 등)
- 가격은 숫자만 (원 제외)
- confidence_overall 전체 신뢰도
- raw_text: 인식한 전체 텍스트
- missing_required: 비어 있는 필수 필드 키 목록
- warnings: 품질·분류 불확실 시 한국어 안내

location(원산지·지역) 정규화 규칙 — 매우 중요:
- 한국 행정구역 표기 «시·도 + 시·군·구 + 읍·면·동» 순으로 가능한 한 풍부하게 작성하세요.
- "국산", "원산지" 같은 라벨은 빼고 실제 지명만 value 에 넣으세요.
- 메모에 면·동·읍 이름만 적혀 있으면, 그 행정구역이 실제로 속한 시·군과 시·도를
  반드시 같이 채우세요. 예시:
  - "기계면"        → "경상북도 포항시 북구 기계면"
  - "북구 기계면"   → "경상북도 포항시 북구 기계면"
  - "가야면"        → "경상남도 합천군 가야면" (또는 "광주광역시 광산구 가야동" 등 상황에 맞게)
  - "죽도"          → "강원특별자치도 양양군 현남면 죽도리"
- "경상북도/경북" 과 "경상남도/경남" 은 절대 혼동하지 마세요. 손글씨가 모호하면
  needs_review=true 로 표시하고, 면·동 이름이 어느 도에 속하는지로 추론하세요.
  (예: 기계면은 경상북도 포항시이므로 "경상남도 포항시"로는 절대 쓰지 마세요.)
- 시·군 정보가 본문에 없고 면·동도 모를 때만 짧게 두고 needs_review=true 로 두세요.
"""

    content.append({"type": "text", "text": prompt})

    if not is_anthropic_configured():
        out = _fallback_from_text("")
        out["warnings"].append("Claude API 키가 없어 OCR을 사용할 수 없습니다.")
        return out

    try:
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=1800,
            system="너는 농어촌 셀러 메모 OCR 전문가다. JSON만 출력한다.",
            messages=[{"role": "user", "content": content}],
            thinking={"type": "disabled"},
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": _LISTING_SCHEMA},
            },
        )
        text = anthropic_response_text(response)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            print("[note_ocr] JSON parse failed; raw text head:", repr(text[:500]))
            raise exc
        # 디버깅: Claude 가 무엇을 돌려줬는지 한 번 보고 갑니다.
        print(
            "[note_ocr] Claude OK — confidence={:.2f}, fields={}, raw_text_len={}".format(
                float(data.get("confidence_overall") or 0.0),
                sorted((data.get("fields") or {}).keys()),
                len(str(data.get("raw_text") or "")),
            )
        )
    except Exception as exc:
        import traceback

        print("[note_ocr] OCR call failed:", type(exc).__name__, exc)
        traceback.print_exc()
        out = _fallback_from_text("")
        out["warnings"].append(
            "AI OCR에 실패했습니다. 사진을 선명하게 다시 올리거나 직접 입력해 주세요."
        )
        out["api_error"] = type(exc).__name__
        return out

    fields = _normalize_fields(data)
    overall = float(data.get("confidence_overall") or 0.5)
    missing = list(data.get("missing_required") or [])
    raw_text = str(data.get("raw_text") or "").strip()

    # LLM 이 description/notes 한 덩어리로 던져준 경우, 한국어 라벨 패턴을 정규식으로
    # 떼어 별도 상세 키(unit/origin/producer/shelf_life/storage_method)로 승격.
    _augment_details_from_blob(fields)
    # raw_text 에도 있을 수 있으므로 보조 시도.
    if raw_text:
        for key, val in _extract_details_from_text(raw_text).items():
            existing = fields.get(key)
            if existing and str(existing.get("value") or "").strip():
                continue
            fields[key] = _field(val, 0.6)

    reg_type = data.get("registration_type") or "product"
    listing_tab = data.get("listing_tab") or hint_tab or "product"
    if listing_tab not in ("product", "lodging", "experience"):
        listing_tab = "product"

    # A2A 검수 — A2(Claude) + A3(OpenAI, max 모드)로 행정구역·단위·일관성 점검
    try:
        from services.agent_pipeline import audit_ocr_listing, pipeline_mode

        fields, a2a_steps = audit_ocr_listing(
            fields, raw_text=raw_text, listing_tab=listing_tab
        )
        a2a_pipeline = "a2a" if a2a_steps else pipeline_mode()
    except Exception:
        a2a_steps = []
        a2a_pipeline = "rules"

    if "title" not in fields or not fields["title"].get("value"):
        if "title" not in missing:
            missing.append("title")
    if "price" not in fields or fields["price"].get("value") in (None, "", 0):
        if reg_type == "product" and "price" not in missing:
            missing.append("price")

    out_warnings = list(data.get("warnings") or []) + warnings
    if overall < 0.4:
        out_warnings.append("인식이 어렵습니다. 직접 입력하거나 선명한 사진으로 다시 시도해 주세요.")
    if reg_type != "product":
        out_warnings.append("예약·주문 메모로 보입니다. 상품 등록 폼에는 일부만 채워집니다.")

    return {
        "registration_type": reg_type,
        "listing_tab": listing_tab,
        "confidence_overall": overall,
        "raw_text": raw_text,
        "fields": fields,
        "missing_required": missing,
        "warnings": out_warnings,
        "a2a_pipeline": a2a_pipeline,
        "a2a_steps": a2a_steps,
    }
