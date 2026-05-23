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

상품 필드: title(필수), price 원 단위 숫자(필수), quantity(kg/개 등), location(원산지·지역),
description(특이사항·무농약 등), notes
예약/주문 필드: customer_name, date_time, quantity(인원), contact_phone(마스킹 010-****-1234),
title(품목/체험명)

규칙:
- 방언·약어 이해 (햅쌀, 수미감자, 갯벌체험 등)
- 가격은 숫자만 (원 제외)
- confidence_overall 전체 신뢰도
- raw_text: 인식한 전체 텍스트
- missing_required: 비어 있는 필수 필드 키 목록
- warnings: 품질·분류 불확실 시 한국어 안내
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
        data = json.loads(text)
    except Exception as exc:
        out = _fallback_from_text("")
        out["warnings"].append(
            "AI OCR에 실패했습니다. 사진을 선명하게 다시 올리거나 직접 입력해 주세요."
        )
        out["api_error"] = type(exc).__name__
        return out

    fields = _normalize_fields(data)
    overall = float(data.get("confidence_overall") or 0.5)
    missing = list(data.get("missing_required") or [])
    if "title" not in fields or not fields["title"].get("value"):
        if "title" not in missing:
            missing.append("title")
    if "price" not in fields or fields["price"].get("value") in (None, "", 0):
        if data.get("registration_type") == "product" and "price" not in missing:
            missing.append("price")

    out_warnings = list(data.get("warnings") or []) + warnings
    if overall < 0.4:
        out_warnings.append("인식이 어렵습니다. 직접 입력하거나 선명한 사진으로 다시 시도해 주세요.")
    if data.get("registration_type") != "product":
        out_warnings.append("예약·주문 메모로 보입니다. 상품 등록 폼에는 일부만 채워집니다.")

    reg_type = data.get("registration_type") or "product"
    listing_tab = data.get("listing_tab") or hint_tab or "product"
    if listing_tab not in ("product", "lodging", "experience"):
        listing_tab = "product"

    return {
        "registration_type": reg_type,
        "listing_tab": listing_tab,
        "confidence_overall": overall,
        "raw_text": str(data.get("raw_text") or "").strip(),
        "fields": fields,
        "missing_required": missing,
        "warnings": out_warnings,
    }
