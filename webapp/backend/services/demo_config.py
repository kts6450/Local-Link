"""시연(데모) 안정성 — A2A(max) 유지, 타임아웃·폴백만 강화."""

from __future__ import annotations

import os

from services.api_keys import is_gemini_configured, is_openai_configured


def is_demo_mode() -> bool:
    return (os.environ.get("TTT_DEMO_MODE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
        "demo",
    )


def effective_asr_correction_mode() -> str:
    """데모 모드에서도 max(A2A 전체) 유지 — 교수님 시연·발표용."""
    raw = (os.environ.get("TTT_ASR_CORRECTION") or "max").strip().lower()
    if raw in ("off", "0", "false", "none"):
        return "off"
    if raw in ("rules", "rule"):
        return "rules"
    if raw in ("a2a", "llm"):
        return "a2a"
    return "max"


def effective_agent_pipeline_mode() -> str:
    raw = (os.environ.get("TTT_AGENT_PIPELINE") or "max").strip().lower()
    if raw in ("off", "0", "false", "none"):
        return "off"
    if raw in ("rules", "rule"):
        return "rules"
    if raw in ("a2a", "llm"):
        return "a2a"
    return "max"


def voice_turn_timeout_sec() -> float:
    if is_demo_mode():
        return float(os.environ.get("TTT_VOICE_TIMEOUT_SEC") or "120")
    return float(os.environ.get("TTT_VOICE_TIMEOUT_SEC") or "120")


def a2a_chain_for_status() -> dict:
    """발표·status API — 멀티 에이전트(A2A) 구성 설명."""
    asr_agents = [
        {"id": "rules", "provider": "local", "role": "지명·숫자 규칙 교정"},
        {"id": "claude_corrector", "provider": "anthropic", "role": "ASR 교정 A"},
        {"id": "claude_auditor", "provider": "anthropic", "role": "ASR 검수 B"},
    ]
    if is_openai_configured():
        asr_agents.append(
            {"id": "openai_verifier", "provider": "openai", "role": "ASR 독립 검증 C"}
        )
    if is_gemini_configured():
        asr_agents.append(
            {"id": "gemini_verifier", "provider": "google_gemini", "role": "ASR 독립 검증 D"}
        )

    slot_agents = [
        {"id": "rules", "provider": "local", "role": "슬롯 규칙 교정"},
        {"id": "claude_slot_validator", "provider": "anthropic", "role": "슬롯 검수 A"},
    ]
    if is_openai_configured():
        slot_agents.append(
            {"id": "openai_slot_reviewer", "provider": "openai", "role": "슬롯 검수 B"}
        )
    if is_gemini_configured():
        slot_agents.append(
            {"id": "gemini_slot_reviewer", "provider": "google_gemini", "role": "슬롯 검수 C"}
        )

    return {
        "description": "Agent-to-Agent: 역할별 AI가 순차 협업 (규칙→Claude→OpenAI→Gemini)",
        "asr_pipeline": asr_agents,
        "slot_pipeline": slot_agents,
        "dialogue_provider": "anthropic",
        "image_provider": "openai" if is_openai_configured() else None,
    }
