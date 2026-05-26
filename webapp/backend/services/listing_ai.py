"""판매 글 — AI 상품 설명 (Claude) · 대표 이미지 (OpenAI DALL·E / Pollinations)."""

from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.parse

import httpx

from services.agent_pipeline import audit_listing_copy
from services.llm import DEFAULT_MODEL


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

    is_market = kind != "lodging" and not _looks_experience(title, "")
    if kind == "lodging":
        kind_ko = "숙박·민박"
    elif is_market:
        kind_ko = "농산·특산품 등 마켓 상품 (택배·픽업 판매)"
    else:
        kind_ko = "체험·축제 프로그램"
    loc = (location or "").strip() or "(지역 미입력)"
    extra_rule = (
        "- 마켓 상품이므로 '체험', '체험하다', '견학', '프로그램', '일정' 같은\n"
        "  단어를 쓰지 마세요. 대신 '맛보세요', '직접 받아보세요', '드셔보세요' 같이\n"
        "  택배·픽업으로 받는 상품에 어울리는 말로 적습니다.\n"
        if is_market
        else ""
    )
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
{extra_rule}"""

    response = anthropic_messages_create(
        model=DEFAULT_MODEL,
        max_tokens=400,
        system="너는 시골·농어촌 소상공인을 돕는 카피라이터다.",
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
    )
    text = anthropic_response_text(response)
    text = audit_listing_copy(
        text,
        title=title,
        price=price,
        location=location,
        is_market_product=is_market,
    )
    return text or _fallback_description(kind, title, price, location)


def _looks_experience(title: str, description: str) -> bool:
    blob = f"{title} {description}".lower()
    return any(h in blob for h in _EXPERIENCE_HINTS)


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
    """짧은 한국어 입력 → 이미지 모델용 영문 프롬프트.
    Claude를 사용하여 한국어 상품명(예: 서리태)을 정확한 영문으로 번역하고 강화된 프롬프트를 생성합니다.
    """
    title = (title or "").strip()
    if not title:
        return {"prompt_en": "", "summary_ko": "상품 이름을 먼저 적어 주세요."}

    desc = (description or "").strip()
    hint = (user_hint or "").strip()

    if _is_experience(title, desc, category):
        summary = "체험·활동 장면으로 잡았습니다."
    elif kind == "lodging":
        summary = "숙박·민박 장면으로 잡았습니다."
    else:
        summary = "특산품 상품 사진 스타일로 잡았습니다."

    from services.api_keys import anthropic_messages_create, anthropic_response_text, is_anthropic_configured
    from services.llm import DEFAULT_MODEL

    if not is_anthropic_configured():
        prompt_en = _fallback_enhance_prompt(kind, title, location, category, desc, hint)
        return {"prompt_en": prompt_en, "summary_ko": summary}

    base = _image_prompt_en(kind, title, location, category=category, description=desc)
    
    prompt = f"""I need an English prompt for an AI image generator (like Flux/Midjourney) based on a Korean local marketplace listing.
Please translate the specific Korean product/subject into accurate English terms (e.g. "서리태" -> "black soybeans") and combine it with the base instructions.

Korean Title: {title}
Description: {desc}
Additional Hint: {hint}
Base Instruction: {base}

Requirements:
- Output ONLY the final English prompt string.
- Make sure the main subject is correctly translated and clearly described.
- Focus on high-quality, photorealistic product/scene photography.
- Do NOT include markdown formatting or conversational text."""

    try:
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=300,
            system="You are an expert prompt engineer for AI image generation.",
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
        )
        prompt_en = anthropic_response_text(response).strip()
    except Exception:
        prompt_en = _fallback_enhance_prompt(kind, title, location, category, desc, hint)

    return {"prompt_en": prompt_en, "summary_ko": summary}


def _image_provider() -> str:
    """openai | pollinations — OPENAI 키 있으면 기본 openai."""
    raw = (os.environ.get("LOCAL_LINK_IMAGE_PROVIDER") or "").strip().lower()
    if raw in ("openai", "dalle", "dall-e"):
        return "openai"
    if raw in ("pollinations", "flux"):
        return "pollinations"
    from services.api_keys import is_openai_configured

    return "openai" if is_openai_configured() else "pollinations"


_OPENAI_IMAGE_FALLBACKS = (
    "gpt-image-1.5",
    "gpt-image-1",
    "gpt-image-1-mini",
    "dall-e-3",
    "dall-e-2",
)


def _openai_image_models() -> list[str]:
    explicit = (os.environ.get("OPENAI_IMAGE_MODEL") or "").strip()
    ordered: list[str] = []
    seen: set[str] = set()
    for model in ([explicit] if explicit else []) + list(_OPENAI_IMAGE_FALLBACKS):
        if model and model not in seen:
            ordered.append(model)
            seen.add(model)
    return ordered or list(_OPENAI_IMAGE_FALLBACKS)


def _openai_image_kwargs(model: str, prompt: str) -> dict:
    kwargs: dict = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
    }
    if model.startswith("dall-e"):
        kwargs["response_format"] = "b64_json"
    if model.startswith("dall-e-3"):
        kwargs["quality"] = (os.environ.get("OPENAI_IMAGE_QUALITY") or "standard").strip()
    return kwargs


def _openai_image(prompt: str) -> bytes:
    """OpenAI Images API — dall-e-3 / dall-e-2."""
    from services.api_keys import is_openai_configured, openai_client, openai_keys

    if not is_openai_configured():
        raise RuntimeError("OPENAI_API_KEY 가 없습니다.")

    prompt = prompt.strip()[:4000]
    if not prompt:
        raise RuntimeError("이미지 프롬프트가 비어 있습니다.")

    last_error: Exception | None = None
    for model in _openai_image_models():
        for i in range(len(openai_keys())):
            try:
                client = openai_client(key_index=i)
                resp = client.images.generate(**_openai_image_kwargs(model, prompt))
                item = resp.data[0]
                b64 = item.b64_json
                if not b64 and item.url:
                    with httpx.Client(timeout=120.0, follow_redirects=True) as http:
                        img_res = http.get(item.url)
                        img_res.raise_for_status()
                        data = img_res.content
                    if len(data) < 1024:
                        raise RuntimeError("이미지 데이터가 너무 작습니다.")
                    return data
                if not b64:
                    raise RuntimeError("OpenAI 이미지 응답이 비어 있습니다.")
                data = base64.b64decode(b64)
                if len(data) < 1024:
                    raise RuntimeError("이미지 데이터가 너무 작습니다.")
                return data
            except Exception as exc:
                last_error = exc
                continue

    msg = f"OpenAI 이미지 생성 실패: {last_error}"
    raise RuntimeError(msg) from last_error


def _pollinations_image(prompt: str, *, seed: int | None = None) -> bytes:
    """Pollinations.ai Flux — 키 불필요, 1024x1024 PNG/JPEG bytes 반환.

    같은 prompt 라도 호출 시각마다 결과가 달라지도록 seed 를 무작위로 부여한다.
    """
    encoded = urllib.parse.quote(prompt[:1500], safe="")
    url = "https://image.pollinations.ai/prompt/" + encoded
    params = {
        "width": "1024",
        "height": "1024",
        "nologo": "true",
        "model": (os.environ.get("POLLINATIONS_MODEL") or "flux").strip(),
        "enhance": "true",
        "safe": "true",
        # 캐시 우회 + 매번 다른 결과를 위해 seed 와 nocache 동시 사용
        "seed": str(seed if seed is not None else secrets.randbelow(1_000_000_000)),
        "nocache": "true",
    }
    with httpx.Client(timeout=180.0, follow_redirects=True) as http:
        res = http.get(url, params=params)
    if res.status_code != 200:
        raise RuntimeError(f"이미지 서버 응답 {res.status_code}")
    ctype = (res.headers.get("content-type") or "").lower()
    if "image" not in ctype:
        raise RuntimeError(f"이미지 응답이 아닙니다: {ctype}")
    data = res.content
    if len(data) < 1024:
        raise RuntimeError("이미지 데이터가 너무 작습니다.")
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
    """대표 이미지 생성 — OpenAI DALL·E(기본) 또는 Pollinations."""
    if (prompt_en or "").strip():
        prompt = prompt_en.strip()[:1500]
    else:
        prompt = _image_prompt_en(
            kind, title, location, category=category, description=description
        )[:1500]

    provider = _image_provider()
    if provider == "openai":
        try:
            data = _openai_image(prompt)
        except Exception as exc:
            import logging

            logging.getLogger("listing_ai").warning(
                "OpenAI 이미지 실패, Pollinations 폴백: %s", exc
            )
            data = _pollinations_image(prompt)
    else:
        data = _pollinations_image(prompt)
    return data, prompt


def image_generation_info() -> dict:
    """프론트 /capabilities용."""
    from services.api_keys import is_openai_configured

    provider = _image_provider()
    if provider == "openai":
        models = _openai_image_models()
        return {
            "provider": "openai",
            "models": models,
            "configured": is_openai_configured(),
        }
    return {
        "provider": "pollinations",
        "models": [(os.environ.get("POLLINATIONS_MODEL") or "flux").strip()],
        "configured": True,
    }
