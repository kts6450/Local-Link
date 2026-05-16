"""
TTT-Dialect 데모용 Whisper ASR 래퍼.

`TTT_MODEL_PATH` 환경변수로 학습된 Whisper 체크포인트 디렉토리를 가리키면
그 모델을 로드하고, 비어있으면 `openai/whisper-small`로 폴백한다.
키오스크/챗봇 양쪽에서 공통으로 import 해서 사용한다.

테스트와 모델 다운로드 전 UI 개발용으로 `DummyASR`을 함께 제공한다.
`TTT_ASR_BACKEND=dummy` 로 두면 `get_asr()`가 더미를 반환한다.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol

import numpy as np

DEFAULT_MODEL = "openai/whisper-small"
TARGET_SR = 16_000
MAX_NEW_TOKENS = 225

# 짧거나 조용한 오디오는 모델에 보내지 않는다 — Whisper의 알려진
# hallucination(같은 토큰 무한 반복) 진입점이라서.
MIN_AUDIO_SECONDS = 0.4
MIN_AUDIO_RMS = 0.005


class ASRBackend(Protocol):
    def transcribe(self, audio: np.ndarray, sr: int = TARGET_SR) -> str: ...


def _to_mono(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio


def _resample_if_needed(audio: np.ndarray, sr: int) -> np.ndarray:
    """모노 변환 후 16kHz로 맞춘다. 이미 16kHz면 그대로 반환."""
    audio = _to_mono(audio)
    if sr == TARGET_SR:
        return audio
    import librosa  # heavy dep, defer until actually resampling
    return librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR).astype(np.float32)


def _pick_device() -> str:
    """CUDA → MPS(Apple Silicon) → CPU 우선순위로 자동 선택.

    Apple Silicon 맥북에서 발표할 때 CPU 대비 5~10배 빨라진다 (M시리즈 GPU 활용).
    """
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _resolve_model_path(raw: str) -> str:
    """학습된 체크포인트 경로 검증 + 비어있으면 base 모델로 폴백.

    Docker 환경에서 빈 placeholder 디렉토리를 마운트했을 때, transformers의
    cryptic OSError 대신 명확한 동작을 하도록.
    """
    from pathlib import Path

    # HuggingFace hub 식별자 (예: "openai/whisper-small") — 검증 안 하고 그대로
    if "/" in raw and not raw.startswith(("/", ".")) and not (len(raw) > 2 and raw[1] == ":"):
        return raw

    p = Path(raw)
    if not p.exists():
        return DEFAULT_MODEL  # 경로 없음 → base 모델

    # 디렉토리지만 Whisper 체크포인트가 아닌 경우 (config.json / preprocessor_config.json 둘 다 없음)
    has_config = (p / "config.json").exists()
    has_preproc = (p / "preprocessor_config.json").exists()
    if not (has_config and has_preproc):
        return DEFAULT_MODEL

    return raw


class WhisperASR:
    """HuggingFace Whisper 체크포인트 추론 래퍼."""

    def __init__(self, model_path: str | None = None, device: str | None = None):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        raw = model_path or os.environ.get("TTT_MODEL_PATH") or DEFAULT_MODEL
        path = _resolve_model_path(raw)
        self.device = device or _pick_device()
        self.processor = WhisperProcessor.from_pretrained(path)
        self.model = WhisperForConditionalGeneration.from_pretrained(path).to(self.device)
        self.model.eval()
        # transformers 5.x 권장 방식: forced_decoder_ids 대신 generate에
        # language/task 직접 전달. 학습 시 generation_config의 forced_decoder_ids가
        # 영어로 박힌 채 저장되는 케이스가 있어 명시적으로 덮어쓴다.
        self.model.generation_config.forced_decoder_ids = None
        self._torch = torch
        self.model_path = path

    def transcribe(self, audio: np.ndarray, sr: int = TARGET_SR) -> str:
        torch = self._torch
        audio_np = _resample_if_needed(audio, sr)

        # 너무 짧거나 거의 무음이면 generate 호출 자체를 스킵 — Whisper의
        # repetition hallucination("그러니까 그러니까 그러니까…") 진입점 차단.
        if audio_np.shape[0] < int(MIN_AUDIO_SECONDS * TARGET_SR):
            return ""
        rms = float(np.sqrt(np.mean(audio_np * audio_np)))
        if rms < MIN_AUDIO_RMS:
            return ""

        feat = self.processor.feature_extractor(
            audio_np,
            sampling_rate=TARGET_SR,
            return_tensors="pt",
        ).input_features.to(self.device)
        with torch.no_grad():
            ids = self.model.generate(
                feat,
                language="ko",
                task="transcribe",
                max_new_tokens=MAX_NEW_TOKENS,
                # repetition 무한 루프 방지 (학습 epoch 부족 시 자주 발생)
                no_repeat_ngram_size=3,
                repetition_penalty=1.2,
                # Whisper 표준 fallback ladder: 결과가 너무 반복적이거나
                # 평균 logprob이 낮으면 temperature를 올려가며 재시도.
                temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                compression_ratio_threshold=1.8,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
            )
        return self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()


class DummyASR:
    """테스트와 모델 도착 전 UI 시연용 결정론적 백엔드."""

    def __init__(self, fixed_text: str = "더미 인식 결과"):
        self.fixed_text = fixed_text
        self.calls: list[tuple[int, int]] = []  # (length, sr)

    def transcribe(self, audio: np.ndarray, sr: int = TARGET_SR) -> str:
        audio = _to_mono(audio)
        self.calls.append((int(audio.shape[0]), int(sr)))
        return self.fixed_text


@lru_cache(maxsize=1)
def get_asr() -> ASRBackend:
    """프로세스 단위 싱글톤 ASR 백엔드.

    `TTT_ASR_BACKEND=dummy` 가 설정되면 Whisper 로딩을 스킵하고 DummyASR을 반환한다.
    UI plumbing을 모델 없이 미리 검증할 때 사용.
    """
    backend = os.environ.get("TTT_ASR_BACKEND", "whisper").lower()
    if backend == "dummy":
        return DummyASR()
    return WhisperASR()
