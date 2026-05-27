"""음성 한 turn API.

POST /api/voice/turn:
  - audio (multipart): 사용자 발화 wav/flac
  - history (form, JSON 문자열): 대화 히스토리 [{role, content}]
  - 반환: { user_text, reply, slots, intent, ready_to_confirm, tts_url }

GET /api/voice/tts?text=... : 텍스트 → mp3 스트림 (프론트 audio 태그가 직접 재생)

설계 노트:
- WebSocket 대신 HTTP POST + GET TTS — Phase 1 단순함 우선.
- VAD/인터럽트는 Phase 2/3에서 WebSocket으로 전환.
"""

from __future__ import annotations

import io
import json
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.asr import asr_status_detail, transcribe_audio_bytes
from services.demo_config import a2a_chain_for_status, is_demo_mode
from services.agent_pipeline import pipeline_mode
from services.api_keys import provider_status
from services.asr_correction import correct_asr_text, correction_mode
from services.llm import chat_turn_for_mode, is_configured as llm_configured
from services.tts import synthesize_mp3

# 오디오 저장 폴더 — 없으면 자동 생성
_AUDIO_DIR = Path(__file__).resolve().parent.parent / "uploads" / "audio"
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

_bearer = HTTPBearer(auto_error=False)


def _optional_user(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """인증 토큰이 있으면 사용자 정보 반환, 없으면 None (asr 는 비로그인도 허용)."""
    if cred is None:
        return None
    try:
        from services.auth_tokens import decode_access_token
        from services.auth_service import user_from_token_payload
        payload = decode_access_token(cred.credentials)
        if not payload or not payload.get("sub"):
            return None
        return user_from_token_payload(payload)
    except Exception:
        return None


def _save_voice_log(
    *,
    audio_bytes: bytes,
    raw_text: str,
    corrected_text: str,
    source: str,
    user: Optional[dict],
) -> None:
    """음성 로그를 파일 + DB에 저장 (실패해도 API 응답에 영향 없음)."""
    try:
        log_id = str(uuid.uuid4())
        audio_path: Optional[str] = None

        # 오디오 파일 저장
        if audio_bytes:
            file_name = f"{log_id}.wav"
            file_path = _AUDIO_DIR / file_name
            file_path.write_bytes(audio_bytes)
            audio_path = str(file_path)

        # DB 저장
        from db.database import SessionLocal
        from db.models import VoiceLogRow

        now = datetime.now(timezone.utc).isoformat()
        row = VoiceLogRow(
            id=log_id,
            user_id=user.get("id") if user else None,
            seller_id=user.get("seller_id") if user else None,
            source=source,
            audio_path=audio_path,
            raw_text=raw_text or "",
            corrected_text=corrected_text or "",
            created_at=now,
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[voice_log] 저장 실패 (무시됨): {e}")

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/status")
def status():
    """프론트 부팅 시 시스템 상태 표시용."""
    detail = asr_status_detail()
    return {
        **detail,
        # 하위 호환: 기존 필드명 유지
        "asr_backend": detail["asr_backend_class"],
        "llm_configured": llm_configured(),
        "asr_correction_mode": correction_mode(),
        "agent_pipeline_mode": pipeline_mode(),
        "providers": provider_status(),
        "demo_mode": is_demo_mode(),
        "a2a_chain": a2a_chain_for_status(),
    }


@router.post("/asr")
async def asr_only(
    audio: UploadFile = File(...),
    user: Optional[dict] = Depends(_optional_user),
):
    """LLM 호출 없이 ASR만 — 셀러 폼에서 단일 칸을 음성으로 채울 때 사용."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="empty audio")
    try:
        raw = transcribe_audio_bytes(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"ASR 실패: {e}")
    # 한국어 손글씨 톤·맞춤법 보정만 가볍게. 단일 필드 입력은 속도가 중요하므로 규칙 보정만 가볍게 적용합니다.
    try:
        correction = correct_asr_text(raw, mode="seller", history=[], rules_only=True)
        text = correction.text or raw
    except Exception:
        text = raw

    # 음성 로그 저장 (비동기 실패 허용)
    _save_voice_log(
        audio_bytes=audio_bytes,
        raw_text=raw.strip(),
        corrected_text=text.strip(),
        source="asr",
        user=user,
    )

    return {"text": text.strip(), "raw": raw.strip()}


@router.post("/turn")
async def turn(
    audio: UploadFile = File(...),
    history: str = Form("[]"),
    mode: str = Form("consumer"),
    form_state: str = Form("{}"),
    user: Optional[dict] = Depends(_optional_user),
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="empty audio")

    try:
        user_text_raw = transcribe_audio_bytes(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"ASR 실패: {e}")

    try:
        history_list = json.loads(history) if history else []
        if not isinstance(history_list, list):
            history_list = []
    except json.JSONDecodeError:
        history_list = []

    try:
        form_state_dict = json.loads(form_state) if form_state else {}
        if not isinstance(form_state_dict, dict):
            form_state_dict = {}
    except json.JSONDecodeError:
        form_state_dict = {}

    correction = correct_asr_text(
        user_text_raw,
        mode=mode if mode in ("consumer", "seller") else "consumer",
        history=history_list,
    )
    user_text = correction.text

    if not user_text.strip():
        # 인식 결과가 비어있으면 LLM 호출 스킵, 사용자에게 다시 요청
        _save_voice_log(
            audio_bytes=audio_bytes,
            raw_text=user_text_raw,
            corrected_text="",
            source="turn",
            user=user,
        )
        return {
            "user_text": "",
            "user_text_raw": user_text_raw,
            "asr_correction": {
                "pipeline": correction.pipeline,
                "rule_fixes": correction.rule_fixes,
                "a2a_steps": correction.a2a_steps,
            },
            "reply": "죄송합니다. 잘 못 들었어요. 다시 한번 말씀해 주시겠어요?",
            "slots": {},
            "intent": "noisy",
            "ready_to_confirm": False,
            "tts_url": _tts_url("죄송합니다. 잘 못 들었어요. 다시 한번 말씀해 주시겠어요?"),
        }

    try:
        result = chat_turn_for_mode(
            user_text, history_list, mode, form_state=form_state_dict
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"음성 처리 일시 오류: {exc}. 다시 말씀해 주세요.",
        ) from exc

    result["user_text"] = user_text
    result["user_text_raw"] = user_text_raw
    result["asr_correction"] = {
        "pipeline": correction.pipeline,
        "rule_fixes": correction.rule_fixes,
        "a2a_steps": correction.a2a_steps,
    }
    result["tts_url"] = _safe_tts_url(result.get("reply", ""))

    # 음성 로그 저장 (비동기 실패 허용)
    _save_voice_log(
        audio_bytes=audio_bytes,
        raw_text=user_text_raw,
        corrected_text=user_text,
        source="turn",
        user=user,
    )

    return result


@router.post("/text")
async def text_turn(body: dict):
    """음성 없이 텍스트 입력으로 한 turn — 디버깅·접근성 폴백."""
    user_text = (body.get("user_text") or "").strip()
    history = body.get("history") or []
    if not user_text:
        raise HTTPException(status_code=400, detail="user_text required")
    mode_raw = body.get("mode") or "consumer"
    mode = mode_raw if mode_raw in ("consumer", "seller") else "consumer"
    form_state = body.get("form_state") or {}
    if not isinstance(form_state, dict):
        form_state = {}
    result = chat_turn_for_mode(user_text, history, mode, form_state=form_state)
    result["user_text"] = user_text
    result["tts_url"] = _tts_url(result["reply"])
    return result


@router.get("/tts")
def tts(text: str):
    audio = synthesize_mp3(text)
    if audio is None:
        raise HTTPException(status_code=502, detail="TTS 합성 실패")
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _tts_url(text: str) -> str:
    return f"/api/voice/tts?text={urllib.parse.quote(text)}"


def _safe_tts_url(reply: str) -> str | None:
    text = (reply or "").strip()
    if not text:
        return None
    if len(text) > 180:
        text = text[:177].rstrip() + "…"
    return _tts_url(text)
