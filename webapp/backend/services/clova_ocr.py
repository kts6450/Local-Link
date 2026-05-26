"""네이버 CLOVA OCR — General OCR API (손글씨·인쇄 텍스트 추출)."""

from __future__ import annotations

import base64
import os
import re
import time
import uuid
from typing import Any

import httpx

_MEDIA_TO_FMT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def is_clova_configured() -> bool:
    return bool(
        (os.environ.get("CLOVA_OCR_API_URL") or "").strip()
        and (os.environ.get("CLOVA_OCR_SECRET") or "").strip()
    )


def validate_clova_api_url(api_url: str) -> None:
    """APIGW Invoke URL 형식 검증. 잘못된 URL이면 RuntimeError."""
    url = (api_url or "").strip()
    if not url.startswith("https://"):
        raise RuntimeError(
            "CLOVA_OCR_API_URL은 https:// 로 시작하는 API Gateway Invoke URL이어야 합니다. "
            "OCR 빌더 → API Gateway 연동(자동) → Invoke URL을 복사해 넣어 주세요."
        )
    host = httpx.URL(url).host or ""
    if "apigw.ntruss.com" not in host:
        raise RuntimeError(
            "CLOVA_OCR_API_URL이 APIGW Invoke URL이 아닙니다. "
            "clovaocr-api-kr.ncloud.com 같은 주소가 아니라 "
            "https://xxxx.apigw.ntruss.com/custom/v1/.../general 형식이어야 합니다."
        )
    if not url.rstrip("/").endswith("/general"):
        raise RuntimeError("CLOVA_OCR_API_URL 끝에 /general 이 포함되어야 합니다.")


def ocr_provider_name() -> str:
    """claude = Claude Vision OCR | clova = Clova OCR + Claude 구조화."""
    pref = (os.environ.get("LOCAL_LINK_OCR_PROVIDER") or "").strip().lower()
    if pref == "claude":
        return "claude"
    if pref == "clova" and is_clova_configured():
        return "clova"
    if is_clova_configured():
        return "clova"
    return "claude"


def ocr_engine_info() -> dict[str, Any]:
    provider = ocr_provider_name()
    api_url = (os.environ.get("CLOVA_OCR_API_URL") or "").strip()
    url_ok = True
    url_hint = ""
    if is_clova_configured():
        try:
            validate_clova_api_url(api_url)
        except RuntimeError as exc:
            url_ok = False
            url_hint = str(exc)
    return {
        "provider": provider,
        "clova_configured": is_clova_configured(),
        "clova_url_ok": url_ok,
        "clova_url_hint": url_hint,
        "label": "CLOVA OCR + AI" if provider == "clova" else "Claude Vision OCR",
    }


def _media_to_format(media: str) -> str:
    return _MEDIA_TO_FMT.get((media or "").lower(), "jpg")


def _text_from_clova_image(img: dict[str, Any]) -> tuple[str, float]:
    parts: list[str] = []
    confs: list[float] = []

    def ingest(items: list[Any] | None) -> None:
        if not items:
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("inferText") or item.get("text") or "").strip()
            if not text:
                continue
            parts.append(text)
            try:
                confs.append(float(item.get("inferConfidence") or item.get("confidence") or 0.85))
            except (TypeError, ValueError):
                confs.append(0.85)
            if item.get("lineBreak"):
                parts.append("\n")
            else:
                parts.append(" ")

    ingest(img.get("fields"))
    for table in img.get("tables") or []:
        if isinstance(table, dict):
            ingest(table.get("cells"))

    raw = "".join(parts)
    raw = re.sub(r"[ \t]+\n", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r" +", " ", raw).strip()
    avg = sum(confs) / len(confs) if confs else 0.75
    return raw, avg


def clova_ocr_bytes(
    image_bytes: bytes,
    *,
    media_type: str = "image/jpeg",
    name: str = "memo",
) -> tuple[str, float]:
    """단일 이미지 → (인식 텍스트, 평균 confidence 0~1)."""
    api_url = (os.environ.get("CLOVA_OCR_API_URL") or "").strip()
    secret = (os.environ.get("CLOVA_OCR_SECRET") or "").strip()
    if not api_url or not secret:
        raise RuntimeError("CLOVA_OCR_API_URL / CLOVA_OCR_SECRET 가 설정되지 않았습니다.")
    validate_clova_api_url(api_url)

    fmt = _media_to_format(media_type)
    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "lang": "ko",
        "enableTableDetection": False,
        "images": [
            {
                "format": fmt,
                "name": name,
                "data": base64.b64encode(image_bytes).decode("ascii"),
            }
        ],
    }
    headers = {
        "X-OCR-SECRET": secret,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(api_url, headers=headers, json=payload)
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "CLOVA OCR 서버에 연결하지 못했습니다. "
            "CLOVA_OCR_API_URL이 API Gateway Invoke URL(https://....apigw.ntruss.com/.../general)인지 확인해 주세요."
        ) from exc

    if resp.status_code >= 400:
        detail = resp.text[:400]
        raise RuntimeError(f"Clova OCR HTTP {resp.status_code}: {detail}")
    data = resp.json()

    images = data.get("images") or []
    if not images:
        raise RuntimeError("Clova OCR 응답에 images 가 없습니다.")
    img0 = images[0]
    if not isinstance(img0, dict):
        raise RuntimeError("Clova OCR 응답 형식이 올바르지 않습니다.")

    infer_result = str(img0.get("inferResult") or "SUCCESS").upper()
    if infer_result not in ("SUCCESS", "OK", ""):
        message = img0.get("message") or data.get("message") or infer_result
        raise RuntimeError(f"Clova OCR 실패: {message}")

    return _text_from_clova_image(img0)


def clova_ocr_many(
    items: list[tuple[bytes, str]],
) -> tuple[str, float]:
    """여러 (bytes, media_type) → 합친 raw_text, 평균 confidence."""
    chunks: list[str] = []
    confs: list[float] = []
    for i, (data, media) in enumerate(items):
        text, conf = clova_ocr_bytes(data, media_type=media, name=f"memo_{i + 1}")
        if text:
            chunks.append(text)
            confs.append(conf)
    combined = "\n\n".join(chunks).strip()
    avg = sum(confs) / len(confs) if confs else 0.5
    return combined, avg
