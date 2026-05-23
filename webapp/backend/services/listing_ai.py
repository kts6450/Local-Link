"""판매 글 — AI 상품 설명·대표 이미지 (Claude 설명, OpenAI 이미지)."""

from __future__ import annotations

import base64
import json
import os

import httpx

from services.agent_pipeline import audit_listing_copy, verify_image_prompt_a2a
from services.llm import DEFAULT_MODEL

_DEFAULT_IMAGE_SIZE = "1024x1024"
# dall-e-3 미지원 계정·프록시가 많아 기본 시도 순서는 2 → 3 → gpt-image-1
_DEFAULT_IMAGE_MODELS = ("dall-e-2", "dall-e-3", "gpt-image-1")


def _openai_api_key() -> str:
    from services.api_keys import primary_openai_key

    return primary_openai_key()


def is_openai_configured() -> bool:
    from services.api_keys import is_openai_configured as _configured

    return _configured()


def image_models_to_try() -> list[str]:
    """OPENAI_IMAGE_MODEL 이 있으면 그것만, 없으면 dall-e-2 → dall-e-3."""
    explicit = (os.environ.get("OPENAI_IMAGE_MODEL") or "").strip()
    if explicit:
        return [explicit]
    return list(_DEFAULT_IMAGE_MODELS)


def _fallback_description(kind: str, title: str, price: int, location: str) -> str:
    kind_ko = "숙박" if kind == "lodging" else "상품"
    loc = location.strip() or "지역"
    return (
        f"«{title}»은(는) {loc}의 {kind_ko}입니다. 판매가 {price:,}원이며, "
        "직접 재배·가공하거나 정성껏 준비한 물건임을 알려 드립니다. "
        "궁금한 점은 메시지로 편히 문의해 주세요."
    )


def generate_listing_description(
    kind: str, title: str, price: int, location: str
) -> str:
    """한국어 마켓플레이스용 짧은 설명 (2~4문장). API 키 없으면 규칙 템플릿."""
    title = (title or "").strip()
    if not title:
        return "상품 이름을 먼저 적어 주세요."
    from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured

    if not is_anthropic_configured():
        return _fallback_description(kind, title, price, location)

    kind_ko = "숙박·민박" if kind == "lodging" else "농산·특산품 등 상품"
    loc = (location or "").strip() or "(지역 미입력)"
    prompt = f"""다음 정보로 로컬링크 쇼핑몰에 올릴 상품 설명을 써 주세요.

- 종류: {kind_ko}
- 이름: {title}
- 가격: {price:,}원
- 지역: {loc}

규칙:
- 한국어만, 2~4문장, 존댓말·쉬운 말.
- 마크다운·글머리·따옴표 장식 없이 본문만.
- 사실에 없는 구체적 수치·인증·수상은 쓰지 말 것.
- 지역 특색은 부드럽게 한 번만 언급해도 됨.
"""

    response = anthropic_messages_create(
        model=DEFAULT_MODEL,
        max_tokens=400,
        system="너는 시골·농어촌 소상공인을 돕는 카피라이터다.",
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
    )
    text = anthropic_response_text(response)
    text = audit_listing_copy(text, title=title, price=price, location=location)
    return text or _fallback_description(kind, title, price, location)


_EXPERIENCE_HINTS = (
    "체험",
    "낚시",
    "수확",
    "투어",
    "견학",
    "만들기",
    "잡기",
    "갯벌",
    "캠핑",
    "승마",
    "트레킹",
    "자전거",
    "요리교실",
    "체험장",
)

_CRAFT_HINTS = ("공예", "도자", "짚", "옻", "만들기", "공방", "전통")


def _listing_text(title: str, description: str) -> str:
    return f"{title} {description}".lower()


def _is_experience(title: str, description: str, category: str) -> bool:
    from services.listing_guide import is_experience

    return is_experience(title, description, category)


def _is_craft(title: str, description: str, category: str) -> bool:
    if category == "craft":
        return True
    t = _listing_text(title, description)
    return any(h in t for h in _CRAFT_HINTS)


def _image_prompt_en(
    kind: str,
    title: str,
    location: str,
    *,
    category: str = "rural",
    description: str = "",
) -> str:
    title = (title or "").strip() or "local experience"
    loc = (location or "").strip() or "Korean countryside"
    desc = (description or "").strip()[:400]

    if kind == "lodging":
        return (
            f"Photorealistic inviting Korean rural guesthouse, hanok, or glamping stay, "
            f"for «{title}» in {loc}. Peaceful exterior or cozy room, travel magazine photo, "
            f"no text, no watermark, no logo."
        )

    if _is_experience(title, desc, category):
        return (
            f"Photorealistic outdoor ACTIVITY and EXPERIENCE scene in Korea for «{title}» "
            f"near {loc}. Show people doing the activity (fishing on boat or pier, harvesting, "
            f"tour, hands-on class) — NOT food on a plate, NOT restaurant dish, NOT raw fish "
            f"served on table unless the title is explicitly about cooking class. "
            f"Context: {desc or title}. Natural daylight, documentary travel photography, "
            f"wide shot, authentic rural or coastal Korea, no text, no watermark."
        )

    if _is_craft(title, desc, category):
        return (
            f"Photorealistic Korean traditional craft workshop scene for «{title}» in {loc}. "
            f"Hands making pottery or craft, materials on table, warm light, "
            f"NOT food photography, no text, no watermark."
        )

    if category == "fishing" or any(
        w in _listing_text(title, desc) for w in ("어촌", "해산", "갯벌", "전복", "멍게", "오징어")
    ):
        return (
            f"Photorealistic Korean coastal fishing village or fresh seafood market scene "
            f"for «{title}» in {loc}. Ocean, harbor, or fishermen's catch on ice — "
            f"NOT fine-dining plated meal unless title says restaurant. "
            f"No text, no watermark, editorial photo."
        )

    return (
        f"Professional product photography of Korean local farm or specialty product "
        f"«{title}» from {loc}. Clean neutral background, marketplace listing, "
        f"NOT people fishing unless product is clearly packaged food only. "
        f"No text, no watermark."
    )


def _fallback_enhance_prompt(
    kind: str,
    title: str,
    location: str,
    category: str,
    description: str,
    user_hint: str,
) -> str:
    """API 키 없을 때 규칙 기반 영문 프롬프트."""
    base = _image_prompt_en(
        kind, title, location, category=category, description=description
    )
    hint = (user_hint or "").strip()
    if hint:
        return f"{base} Additional details from seller: {hint[:500]}"
    return base


def enhance_image_prompt(
    kind: str,
    title: str,
    location: str,
    category: str = "rural",
    description: str = "",
    user_hint: str = "",
) -> dict:
    """짧은 한국어 입력 → DALL·E용 영문 프롬프트 (Claude 또는 규칙)."""
    from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured

    title = (title or "").strip()
    if not title:
        return {"prompt_en": "", "summary_ko": "상품 이름을 먼저 적어 주세요."}

    loc = (location or "").strip() or "(지역 미입력)"
    desc = (description or "").strip()
    hint = (user_hint or "").strip()
    exp = _is_experience(title, desc, category)

    if not is_anthropic_configured():
        prompt_en = _fallback_enhance_prompt(
            kind, title, location, category, desc, hint
        )
        summary = (
            "체험·낚시처럼 보이면 바다·활동 장면으로 잡았습니다."
            if exp
            else "특산품이면 상품 사진 스타일로 잡았습니다."
        )
        return {"prompt_en": prompt_en, "summary_ko": summary}

    kind_ko = "숙박" if kind == "lodging" else "상품/체험"
    cat_ko = category
    prompt = f"""판매자가 로컬링크 마켓에 올릴 대표 사진용 DALL·E 프롬프트를 영어로 작성하세요.

- 종류: {kind_ko}
- 카테고리: {cat_ko}
- 이름: {title}
- 지역: {loc}
- 설명: {desc or "(없음)"}
- 판매자가 적은 사진 힌트: {hint or "(없음)"}

중요 규칙:
1. 이름에 «낚시», «체험», «수확», «투어» 등이 있으면 반드시 그 활동 장면(바다, 배, 낚싯대, 참여)을 묘사할 것.
2. «우럭 낚시»처럼 체험인데 접시에 생선만 올린 음식 사진은 금지.
3. 실제 포장 특산품·농산물만 상품 촬영 스타일.
4. 영문만, 2~4문장, photorealistic, no text, no watermark.
5. JSON만 출력: {{"prompt_en":"...", "summary_ko":"한국어로 1문장 요약"}}
"""

    response = anthropic_messages_create(
        model=DEFAULT_MODEL,
        max_tokens=500,
        system="You output only valid JSON for image generation prompts.",
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
    )
    text = anthropic_response_text(response)

    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        prompt_en = str(data.get("prompt_en", "")).strip()
        summary_ko = str(data.get("summary_ko", "")).strip()
        if prompt_en:
            verified, img_meta = verify_image_prompt_a2a(
                prompt_en,
                kind=kind,
                title=title,
                description=desc,
                category=category,
            )
            summary = summary_ko or "프롬프트를 다듬었습니다."
            if img_meta.get("steps"):
                summary += " (장면 검수 완료)"
            return {
                "prompt_en": verified[:3800],
                "summary_ko": summary,
                "image_pipeline": img_meta,
            }
    except json.JSONDecodeError:
        pass

    prompt_en = _fallback_enhance_prompt(kind, title, location, category, desc, hint)
    verified, img_meta = verify_image_prompt_a2a(
        prompt_en, kind=kind, title=title, description=desc, category=category
    )
    return {
        "prompt_en": verified,
        "summary_ko": "자동으로 장면을 맞춰 적었습니다.",
        "image_pipeline": img_meta,
    }


def _openai_client(*, key_index: int = 0):
    from services.api_keys import openai_client

    return openai_client(key_index=key_index)


def _is_retryable_openai_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "connection" in msg
        or "timeout" in msg
        or "503" in msg
        or "502" in msg
        or "429" in msg
        or "rate limit" in msg
    )


def _model_unavailable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "does not exist" in msg
        or "invalid_value" in msg
        or "model_not_found" in msg
        or "unknown model" in msg
    )


def _retry_without_bad_params(exc: BaseException) -> bool:
    """지원하지 않는 옵션(quality 등)이면 더 단순한 요청으로 재시도."""
    msg = str(exc).lower()
    return "unknown parameter" in msg or "unknown_parameter" in msg


def _image_generate_attempts(model: str, prompt: str) -> list[dict]:
    """호환 API·구버전 엔드포인트용 — 최소 파라미터부터 시도."""
    size = (os.environ.get("OPENAI_IMAGE_SIZE") or _DEFAULT_IMAGE_SIZE).strip()
    base: dict = {
        "model": model,
        "prompt": prompt[:3800],
        "size": size,
        "n": 1,
    }
    attempts = [dict(base)]
    if model.startswith("dall-e-3"):
        quality = (os.environ.get("OPENAI_IMAGE_QUALITY") or "standard").strip()
        attempts.insert(0, {**base, "quality": quality})
    return attempts


def _generate_image(client, model: str, prompt: str):
    attempts = _image_generate_attempts(model, prompt)
    last_error: BaseException | None = None
    for i, kwargs in enumerate(attempts):
        try:
            return client.images.generate(**kwargs)
        except Exception as e:
            last_error = e
            if _retry_without_bad_params(e) and i < len(attempts) - 1:
                continue
            raise
    assert last_error is not None
    raise last_error


def _bytes_from_image_response(result) -> bytes:
    item = result.data[0]
    if getattr(item, "b64_json", None):
        return base64.b64decode(item.b64_json)
    url = getattr(item, "url", None)
    if not url:
        raise RuntimeError("이미지 데이터를 받지 못했습니다.")
    with httpx.Client(timeout=120.0) as http:
        res = http.get(url)
        res.raise_for_status()
        data = res.content
    if len(data) < 256:
        raise RuntimeError("이미지 다운로드에 실패했습니다.")
    return data


def generate_listing_cover_png(
    kind: str,
    title: str,
    location: str,
    *,
    category: str = "rural",
    description: str = "",
    prompt_en: str | None = None,
) -> tuple[bytes, str]:
    """OPENAI_API_KEY 로 DALL·E 이미지 생성. (png bytes, 사용한 프롬프트)."""
    if not is_openai_configured():
        raise RuntimeError("OPENAI_API_KEY missing")

    if (prompt_en or "").strip():
        prompt = prompt_en.strip()[:3800]
    else:
        prompt = _image_prompt_en(
            kind, title, location, category=category, description=description
        )
    models = image_models_to_try()
    last_error: BaseException | None = None
    from services.api_keys import openai_keys

    for key_i in range(len(openai_keys()) or 1):
        client = _openai_client(key_index=key_i)
        for model in models:
            try:
                result = _generate_image(client, model, prompt)
                return _bytes_from_image_response(result), prompt
            except Exception as e:
                last_error = e
                if _model_unavailable(e) and model != models[-1]:
                    continue
                if _is_retryable_openai_error(e):
                    break
                break

    raise RuntimeError(f"이미지 생성 실패: {last_error}")
