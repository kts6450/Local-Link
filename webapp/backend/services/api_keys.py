"""API 키 로드 — Anthropic·OpenAI 다중 키·Gemini."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any

import httpx

_ANTHROPIC_KEY_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY_2",
)
_OPENAI_KEY_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_API_KEY_2",
)
_GEMINI_KEY_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _split_keys(raw: str) -> list[str]:
    parts = re.split(r"[\s,;]+", raw or "")
    return [p.strip() for p in parts if p.strip()]


@lru_cache(maxsize=1)
def anthropic_keys() -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()

    bulk = (os.environ.get("ANTHROPIC_API_KEYS") or "").strip()
    for k in _split_keys(bulk):
        if k not in seen:
            keys.append(k)
            seen.add(k)

    for var in _ANTHROPIC_KEY_VARS:
        k = (os.environ.get(var) or "").strip()
        if k and k not in seen:
            keys.append(k)
            seen.add(k)

    return tuple(keys)


@lru_cache(maxsize=1)
def openai_keys() -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()

    bulk = (os.environ.get("OPENAI_API_KEYS") or "").strip()
    for k in _split_keys(bulk):
        if k not in seen:
            keys.append(k)
            seen.add(k)

    for var in _OPENAI_KEY_VARS:
        k = (os.environ.get(var) or "").strip()
        if k and k not in seen:
            keys.append(k)
            seen.add(k)

    return tuple(keys)


def primary_openai_key() -> str:
    keys = openai_keys()
    return keys[0] if keys else ""


def openai_base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or "").strip()


def is_openai_configured() -> bool:
    return bool(openai_keys())


@lru_cache(maxsize=1)
def gemini_key() -> str:
    for var in _GEMINI_KEY_VARS:
        k = (os.environ.get(var) or "").strip()
        if k:
            return k
    return ""


def gemini_model() -> str:
    return (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()


def is_gemini_configured() -> bool:
    return bool(gemini_key())


def is_anthropic_configured() -> bool:
    return bool(anthropic_keys())


def anthropic_client(*, key_index: int = 0):
    import anthropic

    keys = anthropic_keys()
    if not keys:
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    idx = min(max(0, key_index), len(keys) - 1)
    return anthropic.Anthropic(api_key=keys[idx])


def anthropic_messages_create(**kwargs: Any) -> Any:
    """messages.create — 키 실패 시 다음 Anthropic 키로 재시도."""
    keys = anthropic_keys()
    if not keys:
        raise RuntimeError("ANTHROPIC_API_KEY missing")
    last_error: Exception | None = None
    for i in range(len(keys)):
        try:
            return anthropic_client(key_index=i).messages.create(**kwargs)
        except Exception as exc:
            last_error = exc
            continue
    assert last_error is not None
    raise last_error


def anthropic_response_text(response: Any) -> str:
    return next(b.text for b in response.content if b.type == "text").strip()


def provider_status() -> dict[str, Any]:
    okeys = openai_keys()
    akeys = anthropic_keys()
    return {
        "anthropic": len(akeys) > 0,
        "anthropic_key_count": len(akeys),
        "openai": len(okeys) > 0,
        "openai_key_count": len(okeys),
        "gemini": is_gemini_configured(),
        "gemini_model": gemini_model() if is_gemini_configured() else None,
    }


def openai_client(*, key_index: int = 0):
    from openai import OpenAI

    keys = openai_keys()
    if not keys:
        raise RuntimeError("OPENAI_API_KEY missing")
    idx = min(max(0, key_index), len(keys) - 1)
    kwargs: dict[str, Any] = {"api_key": keys[idx], "max_retries": 3, "timeout": 120.0}
    base = openai_base_url()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs)


def call_openai_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
) -> dict | None:
    if not is_openai_configured():
        return None
    model_name = (model or os.environ.get("TTT_ASR_OPENAI_MODEL") or "gpt-4o-mini").strip()
    last_error: Exception | None = None

    for i in range(len(openai_keys())):
        try:
            client = openai_client(key_index=i)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        return None
    return None


def call_gemini_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
) -> dict | None:
    key = gemini_key()
    if not key:
        return None

    model_name = (model or gemini_model()).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    try:
        with httpx.Client(timeout=60.0) as http:
            res = http.post(url, params={"key": key}, json=payload)
            res.raise_for_status()
            data = res.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip() or "{}")
    except Exception:
        return None


def clear_key_cache() -> None:
    anthropic_keys.cache_clear()
    openai_keys.cache_clear()
    gemini_key.cache_clear()
