"""ASR 서비스 — 업로드 오디오 → 한국어 텍스트."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

from services.whisper_asr import TARGET_SR, describe_asr_for_status, get_asr


def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    try:
        audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception as e:
        raise RuntimeError(
            f"오디오 디코드 실패: {e}. WAV 또는 FLAC으로 보내거나 ffmpeg 추가 필요."
        ) from e

    if audio_np.ndim > 1:
        audio_np = audio_np.mean(axis=1)
    asr = get_asr()
    return asr.transcribe(audio_np.astype(np.float32), sr=int(sr))


def asr_backend_label() -> str:
    return describe_asr_for_status()["asr_backend_class"]


def asr_status_detail() -> dict:
    return describe_asr_for_status()
