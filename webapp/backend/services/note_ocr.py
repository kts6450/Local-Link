"""수기 메모 이미지 OCR → 상품 등록 초안.

- LOCAL_LINK_OCR_PROVIDER=clova + CLOVA 키: Clova OCR → Claude 구조화
- 그 외: Claude Vision (이미지 직접)
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured
from services.clova_ocr import clova_ocr_many, ocr_provider_name

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


# confidence_overall 재계산 시 핵심·상세 필드 가중치
_CORE_FIELD_WEIGHTS: dict[str, float] = {
    "title": 0.24,
    "price": 0.22,
    "location": 0.16,
    "quantity": 0.08,
    "description": 0.12,
}
_DETAIL_FIELD_WEIGHTS: dict[str, float] = {
    "producer": 0.045,
    "shelf_life": 0.045,
    "storage_method": 0.045,
    "origin": 0.045,
    "unit": 0.045,
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


_APP_SCREEN_MARKERS = (
    "갤러리에서 사진 선택",
    "OCR 결과",
    "신뢰도",
    "폼에 채우기",
    "노트 사진으로",
    "물건 올리기",
)


def _looks_like_app_screenshot(text: str) -> bool:
    """앱 UI 캡처 여부 — 경고 문구·버튼 텍스트가 OCR에 섞이면 오인식."""
    t = text or ""
    hits = sum(1 for m in _APP_SCREEN_MARKERS if m in t)
    return hits >= 2 or ("OCR 결과" in t and "신뢰도" in t)


_UI_SKIP_SUBSTRINGS = (
    "갤러리에서 사진 선택",
    "OCR 결과",
    "CLOVA OCR",
    "AI가 한 번",
    "노트 사진으로",
    "메모·포스트잇",
    "용량·가격 옵션",
    "네이버 CLOVA",
    "폼에 채우기",
    "물건 올리기",
    "아래 옵션란",
    "상품 추천",
)


def _strip_ui_pollution(raw_text: str) -> tuple[str, list[str]]:
    """앱 UI 캡처 OCR 잡음 제거 → 메모 본문만 남김."""
    extra_warnings: list[str] = []
    if not _looks_like_app_screenshot(raw_text):
        return raw_text, extra_warnings

    start = len(raw_text)
    for marker in (
        "* 판매상품",
        "* 상품명",
        "* 원산지",
        "* 생산자",
        "* 유통기한",
        "인식 텍스트",
    ):
        idx = raw_text.find(marker)
        if idx >= 0:
            start = min(start, idx)
    chunk = raw_text[start:] if start < len(raw_text) else raw_text

    kept: list[str] = []
    for line in chunk.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.search(r"^신뢰도\s*\d", s):
            continue
        if any(skip in s for skip in _UI_SKIP_SUBSTRINGS):
            continue
        if re.search(r"(추론하였|확인이 필요|적혀 있지 않|직접 확인|다시 확인)", s):
            continue
        kept.append(line)

    cleaned = "\n".join(kept).strip()
    if cleaned and cleaned != raw_text.strip():
        extra_warnings.append(
            "화면 UI 글자가 같이 찍혀 메모 본문만 따로 읽었어요. 다음엔 메모만 크게 찍어 주세요."
        )
    return (cleaned if len(cleaned) >= 12 else raw_text), extra_warnings


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


def _clean_detail_value(val: str) -> str:
    """정규식 추출 값에서 OCR 잡음(화살표·끝 구두점)을 제거."""
    cleaned = (val or "").strip()
    cleaned = re.sub(r"^[→\-–—>\s]+", "", cleaned)
    cleaned = re.sub(r"\s*[→\-–—>]+\s*(?:가을|봄|여름|겨울|환절기)\s*$", "", cleaned)
    cleaned = re.sub(r"\s*[→\-–—>]+\s*[가-힣]{1,4}\s*$", "", cleaned)
    cleaned = re.sub(r"[→\-–—>\s]+$", "", cleaned)
    cleaned = re.sub(r"[\s.,;·/]+$", "", cleaned)
    return cleaned[:120]


_STORAGE_TYPO_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"냉공"), "냉장"),
    (re.compile(r"냉쟁"), "냉장"),
    (re.compile(r"냉장고"), "냉장"),
    (re.compile(r"동풍\s*절?되(?:는)?\s*곳"), "통풍 잘 되는 곳"),
    (re.compile(r"동풍"), "통풍"),
    (re.compile(r"등풍\s*절?되(?:는)?\s*곳"), "통풍 잘 되는 곳"),
    (re.compile(r"등풍"), "통풍"),
]


def _normalize_storage_method(val: str) -> str:
    """보관방법 OCR 오타·화살표 잡음 정리."""
    cleaned = _clean_detail_value(val)
    for pattern, repl in _STORAGE_TYPO_FIXES:
        cleaned = pattern.sub(repl, cleaned)
    return cleaned.strip()[:120]


def _ocr_context_blob(fields: dict[str, dict], raw_text: str) -> str:
    parts = [raw_text]
    for key in ("description", "notes", "title"):
        parts.append(str((fields.get(key) or {}).get("value") or ""))
    return "\n".join(p for p in parts if p)


def _reconcile_cross_field_typos(fields: dict[str, dict], raw_text: str) -> list[str]:
    """원문·다른 필드를 대조해 흔한 손글씨 OCR 혼동을 교정 (예: 기계정하→기계장터)."""
    notes: list[str] = []
    blob = _ocr_context_blob(fields, raw_text)

    if re.search(r"기계\s*장터|장터\s*마을|장터마을", blob):

        def fix_jangteo(text: str) -> str:
            out = re.sub(r"기계\s*정하", "기계장터", text)
            return out.replace("기계정하", "기계장터")

        prod = fields.get("producer")
        if isinstance(prod, dict):
            val = str(prod.get("value") or "")
            if val and ("기계정하" in val or re.search(r"기계\s*정하", val)):
                fixed = fix_jangteo(val)
                fields["producer"] = _field(fixed, 0.94, needs_review=False)
                notes.append(f"생산자명을 「{fixed}」로 바로잡았어요 (메모·원문의 ‘장터’와 맞춤).")

        desc = fields.get("description")
        if isinstance(desc, dict):
            val = str(desc.get("value") or "")
            if val and ("기계정하" in val or re.search(r"기계\s*정하", val)):
                fixed = fix_jangteo(val)
                fields["description"] = _field(
                    fixed,
                    max(float(desc.get("confidence") or 0.8), 0.9),
                    needs_review=False,
                )

    return notes


def _postprocess_detail_fields(fields: dict[str, dict]) -> None:
    """상세 필드 값 후처리 — 보관방법 오타 등."""
    item = fields.get("storage_method")
    if not isinstance(item, dict):
        return
    raw = str(item.get("value") or "").strip()
    if not raw:
        return
    fixed = _normalize_storage_method(raw)
    if fixed == raw:
        return
    conf = float(item.get("confidence") or 0.7)
    fields["storage_method"] = _field(
        fixed,
        min(1.0, conf + 0.05),
        needs_review=False,
    )


def _extract_price_variants(text: str) -> list[dict[str, Any]] | None:
    """raw_text·설명·가격 문자열에서 용량·단가 옵션 추출."""
    if not (text or "").strip():
        return None

    items: list[tuple[str, int]] = []
    seen: set[str] = set()

    def add(label: str, price: int) -> None:
        label = re.sub(r"\s+", "", (label or "").strip())
        if not label or len(label) > 40 or price <= 0 or price >= 100_000_000:
            return
        if label in seen:
            return
        seen.add(label)
        items.append((label, price))

    blob = text

    for m in re.finditer(r"(\d[\d,]*)\s*원?\s*\(\s*([^)]+?)\s*\)", blob):
        add(m.group(2), int(m.group(1).replace(",", "")))

    for m in re.finditer(
        r"(\d+\s*(?:g|kg|그램|킬로|키로|ml|cc|l|리터|L))\s*\(\s*(\d[\d,]*)\s*원?\s*\)",
        blob,
        re.I,
    ):
        add(m.group(1), int(m.group(2).replace(",", "")))

    for m in re.finditer(
        r"(\d+\s*(?:g|kg|그램|킬로|키로|ml|cc|l|리터|L))\s*[:：·]\s*(\d[\d,]*)\s*원?",
        blob,
        re.I,
    ):
        add(m.group(1), int(m.group(2).replace(",", "")))

    for seg in re.split(r"[/|,;]+|\s+·\s+", blob):
        seg = seg.strip()
        if not seg:
            continue
        wm = re.search(r"(\d+\s*(?:g|kg|그램|킬로|키로|ml|cc|l|리터|L))", seg, re.I)
        pm = re.search(r"(\d[\d,]*)\s*원", seg)
        if wm and pm:
            add(wm.group(1), int(pm.group(1).replace(",", "")))

    if len(items) < 2:
        return None
    return [{"label": lbl, "price": pr} for lbl, pr in items]


def _is_multi_price_warning(msg: str) -> bool:
    s = msg or ""
    return any(
        k in s
        for k in (
            "여러 단가",
            "옵션 설정",
            "대표 가격",
            "대표가",
            "여러 가격",
        )
    )


_REQUIRED_FIELD_KEYS = ("title", "price")


def _applied_audit_keys(a2a_steps: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for step in a2a_steps:
        for key in step.get("applied") or []:
            if isinstance(key, str):
                keys.add(key)
        if step.get("agent") == "openai_ocr_verifier" and step.get("corrected_location"):
            keys.add("location")
    return keys


def _sync_field_confidence_after_audit(
    fields: dict[str, dict],
    *,
    raw_text: str,
    a2a_steps: list[dict[str, Any]],
    variants: list[dict[str, Any]] | None = None,
) -> None:
    """LLM 보정(A2A)·규칙 후처리가 끝난 뒤 필드별 confidence/needs_review를 최종 정렬."""
    applied = _applied_audit_keys(a2a_steps)
    blobs = "\n".join(p for p in (raw_text, str((fields.get("description") or {}).get("value") or "")) if p)

    for key, val in _extract_details_from_text(raw_text).items():
        existing = fields.get(key)
        existing_val = str((existing or {}).get("value") or "").strip()
        if existing_val in ("", "미기재", "미상", "없음"):
            conf = _detail_value_confidence(key, val, raw_text)
            fields[key] = _field(val, conf, needs_review=False)

    for key, item in list(fields.items()):
        if not isinstance(item, dict):
            continue
        val = item.get("value")
        if val in (None, "", 0):
            continue

        if key in applied:
            fields[key] = _field(val, 0.94, needs_review=False)
            continue

        if key == "price" and variants and len(variants) >= 2:
            fields[key] = _field(val, 0.93, needs_review=False)
            continue

        if key in _DETAIL_FIELD_WEIGHTS:
            val_s = str(val).strip()
            conf = _detail_value_confidence(key, val_s, blobs or raw_text)
            if val_s in ("미기재", "미상", "없음"):
                fields[key] = _field(val, 0.86, needs_review=False)
            elif conf >= 0.92:
                fields[key] = _field(val, conf, needs_review=False)
            continue

        if key in _CORE_FIELD_WEIGHTS and not item.get("needs_review"):
            conf = max(float(item.get("confidence") or 0.8), 0.88)
            fields[key] = _field(val, conf, needs_review=False)


def _filter_resolved_warnings(
    warnings: list[str],
    *,
    fields: dict[str, dict],
    a2a_steps: list[dict[str, Any]],
    variants: list[dict[str, Any]] | None,
) -> list[str]:
    """자동 보정된 항목에 대한 중복 경고를 제거."""
    location_fixed = any("location" in (s.get("applied") or []) for s in a2a_steps)
    storage_item = fields.get("storage_method") or {}
    storage_val = str(storage_item.get("value") or "")
    storage_typo_fixed = "냉장" in storage_val and "냉공" not in storage_val
    storage_ok = bool(storage_val) and not storage_item.get("needs_review")
    shelf_val = str((fields.get("shelf_life") or {}).get("value") or "").strip()
    shelf_ok = bool(shelf_val) and shelf_val not in ("미기재", "미상", "없음")

    out: list[str] = []
    for w in warnings:
        if variants and len(variants) >= 2 and _is_multi_price_warning(w):
            continue
        if location_fixed and ("경항" in w or ("추론" in w and "원산지" in w)):
            continue
        if storage_typo_fixed and "냉공" in w:
            continue
        if storage_ok and "보관방법" in w and ("해석" in w or "흐" in w or "동풍" in w or "등풍" in w):
            continue
        if shelf_ok and "유통기한" in w and ("미기재" in w or "명확" in w):
            continue
        out.append(w)
    return out


def _detail_value_confidence(key: str, val: str, source_text: str) -> float:
    """정규식으로 뽑은 상세 필드 신뢰도 — 라벨·값이 원문과 맞으면 높게."""
    val = _clean_detail_value(val)
    if not val or len(val) < 2:
        return 0.78
    if re.search(r"^[→\-–—>]", val) or "→" in val[:4]:
        return 0.78
    blob = source_text or ""
    for detail_key, label_patterns in _DETAIL_LABELS:
        if detail_key != key:
            continue
        for pattern in label_patterns:
            probe = re.escape(val[: min(len(val), 24)])
            if re.search(rf"{pattern}\s*[:：]?\s*{probe}", blob, re.I | re.S):
                return 0.97
        break
    return 0.92


def _recompute_confidence_overall(
    fields: dict[str, dict],
    *,
    a2a_steps: list[dict[str, Any]],
    missing_required: list[str],
    variants: list[dict[str, Any]] | None = None,
) -> float:
    """LLM 보정(A2A) 완료 후 최종 필드 상태만으로 신뢰도 산정."""
    weights: dict[str, float] = dict(_CORE_FIELD_WEIGHTS)
    for key, weight in _DETAIL_FIELD_WEIGHTS.items():
        item = fields.get(key)
        if item and str(item.get("value") or "").strip():
            weights[key] = weight

    weighted: list[tuple[float, float]] = []
    for key, weight in weights.items():
        item = fields.get(key)
        if not isinstance(item, dict):
            continue
        val = item.get("value")
        if val in (None, "", 0):
            continue
        conf = float(item.get("confidence") or 0.85)
        if item.get("needs_review"):
            conf *= 0.92
        weighted.append((conf, weight))

    if weighted:
        total_w = sum(w for _, w in weighted)
        adjusted = sum(c * w / total_w for c, w in weighted)
    else:
        adjusted = 0.5

    applied_count = sum(len(s.get("applied") or []) for s in a2a_steps)
    if any(s.get("approved") for s in a2a_steps):
        adjusted = min(1.0, adjusted + 0.03)
    if applied_count:
        adjusted = min(1.0, adjusted + 0.012 * min(applied_count, 4))

    req_missing = [k for k in missing_required if k in _REQUIRED_FIELD_KEYS]
    if req_missing:
        adjusted = max(0.35, adjusted - 0.08 * len(req_missing))

    title_ok = bool(str((fields.get("title") or {}).get("value") or "").strip())
    price_ok = fields.get("price", {}).get("value") not in (None, "", 0)
    core_review = any(
        bool(fields.get(k, {}).get("needs_review"))
        for k in ("title", "price", "quantity")
        if fields.get(k) and fields[k].get("value") not in (None, "", 0)
    )
    if title_ok and price_ok and not core_review and not req_missing:
        adjusted = max(adjusted, 0.90)
        if applied_count or any(s.get("approved") for s in a2a_steps):
            adjusted = max(adjusted, 0.93)
    detail_hits = sum(
        1
        for k in _DETAIL_FIELD_WEIGHTS
        if fields.get(k)
        and str(fields[k].get("value") or "").strip() not in ("", "미기재", "미상")
        and float(fields[k].get("confidence") or 0) >= 0.9
    )
    if title_ok and price_ok and detail_hits >= 2 and not core_review:
        adjusted = max(adjusted, 0.92)
    if variants and len(variants) >= 2 and title_ok and price_ok and not core_review:
        adjusted = max(adjusted, 0.91)

    return round(max(0.0, min(0.98, adjusted)), 3)


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
        val = _clean_detail_value(m.group(1) or "")
        # 값이 다른 라벨 키워드 자체이면 무시.
        if not val or len(val) < 1:
            continue
        if re.fullmatch(rf"(?:{_ALL_LABELS_RE})", val):
            continue
        out[key] = val
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
        conf = _detail_value_confidence(key, val, blob)
        fields[key] = _field(val, conf)


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
            loc = loc.replace("결항시", "포항시")
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


def _structure_prompt(hint_tab: str | None) -> str:
    tab_hint = ""
    if hint_tab in ("product", "lodging", "experience"):
        tab_hint = f"\n셀러가 선택한 등록 유형 힌트: {hint_tab}"
    return f"""한국 농어촌 셀러의 수기 메모·포스트잇·종이 영수증입니다.
JSON만 출력하세요.{tab_hint}

목표:
1) registration_type: product(상품) | reservation(예약) | order(주문) 중 분류
2) listing_tab: product(농축수산·가공품) | lodging(숙박·민박) | experience(체험·투어)
3) fields 각 항목: value, confidence(0~1), needs_review(confidence<0.7이면 true)

confidence_overall 부여 기준 (보수적으로 깎지 말 것):
- 메모 글자가 선명하고 필수 필드(title·price)가 원문과 누락 없이 맞으면 0.92~0.98
- 일부 필드가 애매하거나 손글씨가 흐릿하면 0.75~0.88
- 가격·제목 중 하나라도 추측이면 0.55~0.72
- 대부분 읽기 어렵거나 빈칸이 많으면 0.35~0.54
- 각 field confidence 도 같은 기준으로: 원문과 정확히 일치 0.9+, 약간 추론 0.75~0.85

상품 필드: title(필수), price 원 단위 숫자(필수), quantity(kg/개 등), location(시·군·동네),
description(특이사항·무농약 등), notes
description 에는 메모에 적힌 다음 항목을 「라벨: 값」 형태로 줄바꿈으로 정확히 옮겨 적어 주세요
(별도 키는 만들지 말고 description 한 칸에 모아 적습니다):
- 생산자: ... (혹은 농가명: ...)
- 유통기한: ...
- 보관방법: ...
- 원산지: ... (location 보다 더 구체적인 표기 — 농가·읍·리까지 들어가면 좋아요)
이 4개 라벨은 메모에 적혀 있을 때만 줄을 추가하고, 없으면 생략하세요. 라벨 표기·값은 메모 그대로 옮겨 적되, 줄바꿈은 \\n 으로 구분해 주세요.
예약/주문 필드: customer_name, date_time, quantity(인원), contact_phone(마스킹 010-****-1234),
title(품목/체험명)

규칙:
- 방언·약어 이해 (햅쌀, 수미감자, 갯벌체험 등)
- 가격은 숫자만 (원 제외)
- confidence_overall: 위 기준표에 따라 0~1 숫자 하나 (소수 둘째 자리)
- raw_text: 인식한 전체 텍스트
- missing_required: 비어 있는 필수 필드 키 목록
- warnings: 품질·분류 불확실 시 한국어 안내 (어르신용 — listing_tab·product 같은 영어/코드명 금지.
  예: 「체험 탭이 선택돼 있었지만, 메모는 고사리 상품이라 상품으로 채웠어요.」)

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


def _call_claude_listing_json(*, user_text: str, image_blocks: list[dict] | None = None) -> dict:
    content: list[dict[str, Any]] = []
    if image_blocks:
        content.extend(image_blocks)
    content.append({"type": "text", "text": user_text})
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
    return json.loads(text)


def _claude_from_vision(decoded: list[tuple[bytes, str]], hint_tab: str | None) -> dict:
    image_blocks: list[dict[str, Any]] = []
    for data, media in decoded:
        image_blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            }
        )
    prompt = _structure_prompt(hint_tab)
    prompt = prompt.replace(
        "JSON만 출력하세요.",
        "이미지를 OCR로 읽고 JSON만 출력하세요.",
        1,
    )
    data = _call_claude_listing_json(user_text=prompt, image_blocks=image_blocks)
    print(
        "[note_ocr] Claude Vision OK — confidence={:.2f}, fields={}, raw_text_len={}".format(
            float(data.get("confidence_overall") or 0.0),
            sorted((data.get("fields") or {}).keys()),
            len(str(data.get("raw_text") or "")),
        )
    )
    return data


def _claude_from_text(raw_text: str, hint_tab: str | None, *, source_label: str) -> dict:
    prompt = _structure_prompt(hint_tab)
    prompt += f"""

## OCR로 읽은 텍스트 ({source_label})
아래는 OCR API가 추출한 원문입니다. raw_text 필드에는 **아래 텍스트를 그대로** 넣으세요.

---
{raw_text}
---
"""
    data = _call_claude_listing_json(user_text=prompt, image_blocks=None)
    if not str(data.get("raw_text") or "").strip():
        data["raw_text"] = raw_text
    print(
        "[note_ocr] Claude structure OK ({}) — confidence={:.2f}, fields={}".format(
            source_label,
            float(data.get("confidence_overall") or 0.0),
            sorted((data.get("fields") or {}).keys()),
        )
    )
    return data


def _finalize_listing_draft(
    data: dict,
    warnings: list[str],
    *,
    hint_tab: str | None,
    ocr_engine: str,
) -> dict[str, Any]:
    fields = _normalize_fields(data)
    missing = list(data.get("missing_required") or [])
    raw_text = str(data.get("raw_text") or "").strip()

    _augment_details_from_blob(fields)
    if raw_text:
        for key, val in _extract_details_from_text(raw_text).items():
            existing = fields.get(key)
            if existing and str(existing.get("value") or "").strip():
                continue
            conf = _detail_value_confidence(key, val, raw_text)
            fields[key] = _field(val, conf)

    _postprocess_detail_fields(fields)

    price_raw = (data.get("fields") or {}).get("price", {})
    price_blob = ""
    if isinstance(price_raw, dict) and price_raw.get("value") is not None:
        price_blob = str(price_raw.get("value"))

    reg_type = data.get("registration_type") or "product"
    listing_tab = data.get("listing_tab") or hint_tab or "product"
    if listing_tab not in ("product", "lodging", "experience"):
        listing_tab = "product"

    try:
        from services.agent_pipeline import audit_ocr_listing, pipeline_mode

        fields, a2a_steps = audit_ocr_listing(
            fields, raw_text=raw_text, listing_tab=listing_tab
        )
        a2a_pipeline = "a2a" if a2a_steps else pipeline_mode()
    except Exception:
        a2a_steps = []
        a2a_pipeline = "rules"

    _postprocess_detail_fields(fields)

    variant_text = "\n".join(
        p
        for p in (
            raw_text,
            price_blob,
            str((fields.get("description") or {}).get("value") or ""),
            str((fields.get("quantity") or {}).get("value") or ""),
            " ".join(
                f
                for s in a2a_steps
                if isinstance(s, dict)
                for f in (s.get("fixes") or [])
                if isinstance(f, str)
            ),
        )
        if p
    )
    variants = _extract_price_variants(variant_text)
    if variants:
        min_price = min(v["price"] for v in variants)
        prev_conf = float((fields.get("price") or {}).get("confidence") or 0.85)
        fields["price"] = _field(min_price, max(prev_conf, 0.92), needs_review=False)

    if "title" not in fields or not fields["title"].get("value"):
        if "title" not in missing:
            missing.append("title")
    if "price" not in fields or fields["price"].get("value") in (None, "", 0):
        if reg_type == "product" and "price" not in missing:
            missing.append("price")

    typo_notes = _reconcile_cross_field_typos(fields, raw_text)
    if typo_notes:
        warnings.extend(typo_notes)

    _sync_field_confidence_after_audit(
        fields, raw_text=raw_text, a2a_steps=a2a_steps, variants=variants
    )
    _postprocess_detail_fields(fields)

    overall = _recompute_confidence_overall(
        fields,
        a2a_steps=a2a_steps,
        missing_required=missing,
        variants=variants,
    )

    out_warnings = list(data.get("warnings") or []) + warnings
    out_warnings = _filter_resolved_warnings(
        out_warnings,
        fields=fields,
        a2a_steps=a2a_steps,
        variants=variants,
    )
    if variants and len(variants) >= 2:
        out_warnings.insert(
            0,
            f"용량·가격 옵션 {len(variants)}개를 자동으로 찾았어요. 아래 옵션란에서 확인해 주세요.",
        )
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
        "variants": variants,
        "ocr_engine": ocr_engine,
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
    decoded: list[tuple[bytes, str]] = []
    for src in images_b64:
        data, media = _decode_image(src)
        warnings.extend(_image_quality_warnings(data))
        decoded.append((data, media))

    if not is_anthropic_configured() and ocr_provider_name() != "clova":
        out = _fallback_from_text("")
        out["warnings"] = list(out.get("warnings") or []) + warnings
        out["ocr_engine"] = "none"
        return out

    provider = ocr_provider_name()
    ocr_engine = "claude_vision"
    data: dict[str, Any]

    if provider == "clova":
        try:
            raw_text, clova_conf = clova_ocr_many(decoded)
            cleaned, ui_warnings = _strip_ui_pollution(raw_text)
            if cleaned != raw_text:
                raw_text = cleaned
                warnings.extend(ui_warnings)
            print(
                "[note_ocr] Clova OK — conf={:.2f}, raw_text_len={}".format(
                    clova_conf, len(raw_text)
                )
            )
            if not raw_text.strip():
                raise RuntimeError("Clova OCR 결과가 비어 있습니다.")
            if not is_anthropic_configured():
                out = _fallback_from_text(raw_text)
                out["warnings"] = warnings + list(out.get("warnings") or [])
                out["ocr_engine"] = "clova"
                return out
            data = _claude_from_text(raw_text, hint_tab, source_label="CLOVA OCR")
            data["raw_text"] = raw_text
            ocr_engine = "clova+claude"
            warnings.append("네이버 CLOVA OCR로 글자를 읽고, AI가 항목을 정리했어요.")
        except Exception as exc:
            import traceback

            print("[note_ocr] Clova path failed, fallback Vision:", type(exc).__name__, exc)
            traceback.print_exc()
            detail = str(exc).strip()
            if detail:
                warnings.append(detail)
            warnings.append("CLOVA OCR을 사용하지 못해 Claude Vision으로 다시 읽었습니다.")
            data = _claude_from_vision(decoded, hint_tab)
            ocr_engine = "claude_vision"
    else:
        try:
            data = _claude_from_vision(decoded, hint_tab)
        except Exception as exc:
            import traceback

            print("[note_ocr] OCR call failed:", type(exc).__name__, exc)
            traceback.print_exc()
            out = _fallback_from_text("")
            out["warnings"] = warnings + list(out.get("warnings") or [])
            out["warnings"].append(
                "AI OCR에 실패했습니다. 사진을 선명하게 다시 올리거나 직접 입력해 주세요."
            )
            out["api_error"] = type(exc).__name__
            out["ocr_engine"] = ocr_engine
            return out

    return _finalize_listing_draft(
        data,
        warnings,
        hint_tab=hint_tab,
        ocr_engine=ocr_engine,
    )
