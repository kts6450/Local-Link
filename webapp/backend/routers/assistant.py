"""쇼핑 도우미 챗봇 — Claude 기반(키 있을 때) + 룰 기반 폴백.

사용자가 "사과 추천해줘" / "강원도 숙소 보여줘" 같은 대화를 하면
listings 카탈로그를 컨텍스트로 LLM이 적절한 추천 + 인라인 카드를 반환한다.
"""
from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.api_keys import (
    anthropic_messages_create,
    anthropic_response_text,
    is_anthropic_configured,
)
from services.listings_store import list_listings

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


class AssistantTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class AssistantBody(BaseModel):
    user_text: str = Field(min_length=1, max_length=2000)
    history: list[AssistantTurn] = Field(default_factory=list, max_length=20)


def _kind_label(item: dict) -> str:
    if item.get("kind") == "lodging":
        return "스테이"
    if item.get("category") == "experience":
        return "체험"
    return "상품"


def _catalog_block(items: list[dict], *, max_items: int = 60) -> str:
    if not items:
        return "(현재 등록된 상품이 없습니다.)"
    sample = items[:max_items]
    lines: list[str] = []
    for it in sample:
        rating = it.get("rating") or 0.0
        rc = it.get("review_count") or 0
        lines.append(
            f"- id={it['id']} | {_kind_label(it)} | {it['title']} | "
            f"{int(it['price']):,}원 | {it.get('location','')} | "
            f"평점 {rating}({rc}건)"
        )
    return "\n".join(lines)


def _system_prompt(items: list[dict]) -> str:
    return f"""\
당신은 '로컬링크 Local Link' 쇼핑몰의 친근한 AI 도우미입니다.
사용자가 자연어로 상품·숙박·체험을 묻거나 추천을 요청할 때,
아래 카탈로그에서 가장 적절한 1~5개를 골라 짧게 추천하세요.

## 답변 규칙
- 따뜻하고 친근한 한국어 한두 문단(2~4문장).
- 마크다운 헤더·목록은 쓰지 마세요. 문장형으로.
- 가격·지역을 자연스럽게 언급하세요.
- 카탈로그에 없는 것은 추측하지 말고 "비슷한 상품으로는…"식으로 안내.
- 상품 ID는 답변 끝에 [[recommend: id1, id2]] 형식의 인라인 태그로 적으세요.
  태그 안에는 카탈로그에 실제 존재하는 id만 넣어주세요.

## 카탈로그 (요약)
{_catalog_block(items)}
"""


def _extract_recommend_ids(text: str, valid_ids: set[str]) -> tuple[str, list[str]]:
    """답변 텍스트에서 [[recommend: id, id]] 태그를 분리."""
    out_ids: list[str] = []
    cleaned = text or ""
    for m in re.finditer(r"\[\[recommend:\s*([^\]]+)\]\]", cleaned, flags=re.IGNORECASE):
        for raw in m.group(1).split(","):
            rid = raw.strip().strip("`'\" ")
            if rid and rid in valid_ids and rid not in out_ids:
                out_ids.append(rid)
    cleaned = re.sub(r"\[\[recommend:[^\]]+\]\]", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned, out_ids


def _rule_based_search(user_text: str, items: list[dict]) -> list[dict]:
    """LLM 없이 단순 키워드 매칭 — 카테고리·지역·가격 힌트."""
    text = (user_text or "").lower()
    if not text or not items:
        return items[:5]

    def score(it: dict) -> int:
        s = 0
        title = (it.get("title") or "").lower()
        loc = (it.get("location") or "").lower()
        desc = (it.get("description") or "").lower()
        for token in re.findall(r"[가-힣a-z0-9]+", text):
            if len(token) < 2:
                continue
            if token in title:
                s += 8
            if token in loc:
                s += 5
            if token in desc:
                s += 2
        if "숙박" in text or "스테이" in text or "민박" in text or "펜션" in text:
            if it.get("kind") == "lodging":
                s += 6
        if "체험" in text or "클래스" in text:
            if it.get("category") == "experience":
                s += 6
        if "베스트" in text or "인기" in text or "추천" in text:
            s += int((it.get("rating") or 0) * 2) + min(int(it.get("review_count") or 0) // 4, 6)
        return s

    ranked = sorted(items, key=score, reverse=True)
    top = [it for it in ranked if score(it) > 0]
    return (top or ranked)[:5]


def _format_card(it: dict) -> dict:
    return {
        "id": it["id"],
        "kind": it["kind"],
        "category": it.get("category"),
        "title": it["title"],
        "price": it["price"],
        "location": it.get("location") or "",
        "cover_image_url": it.get("cover_image_url"),
        "rating": it.get("rating") or 0.0,
        "review_count": it.get("review_count") or 0,
    }


def _fallback_reply(user_text: str, items: list[dict]) -> dict[str, Any]:
    picks = _rule_based_search(user_text, items)
    if not picks:
        return {
            "reply": "지금 조건에 맞는 상품을 찾지 못했어요. 키워드를 조금만 바꿔서 다시 말씀해 주시겠어요?",
            "recommendations": [],
        }
    parts = []
    for it in picks[:3]:
        parts.append(
            f"«{it['title']}» ({_kind_label(it)} · {int(it['price']):,}원, {it.get('location','')})"
        )
    text = "다음 상품이 잘 어울릴 것 같아요. " + ", ".join(parts) + ". 자세한 내용은 카드에서 확인하세요."
    return {
        "reply": text,
        "recommendations": [_format_card(it) for it in picks],
    }


@router.post("/chat")
def post_chat(body: AssistantBody):
    items = list_listings()
    if not is_anthropic_configured():
        return _fallback_reply(body.user_text, items)

    try:
        history = [
            {"role": m.role, "content": m.content}
            for m in body.history[-10:]
        ]
        history.append({"role": "user", "content": body.user_text})
        response = anthropic_messages_create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _system_prompt(items),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=history,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
        )
        reply_raw = anthropic_response_text(response)
    except Exception:
        return _fallback_reply(body.user_text, items)

    valid = {it["id"] for it in items}
    cleaned, ids = _extract_recommend_ids(reply_raw, valid)
    by_id = {it["id"]: it for it in items}
    recs = [_format_card(by_id[i]) for i in ids if i in by_id]

    if not recs:
        recs = [_format_card(it) for it in _rule_based_search(body.user_text, items)[:3]]

    if not cleaned.strip():
        cleaned = "추천 결과를 카드로 정리해 드렸어요."

    return {"reply": cleaned, "recommendations": recs}


@router.get("/health")
def health():
    return {"llm_configured": is_anthropic_configured()}
