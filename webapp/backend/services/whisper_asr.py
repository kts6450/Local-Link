"""Whisper ASR — 로컬링크 음성 인식.

`TTT_MODEL_PATH` 로 파인튜닝 체크포인트 또는 `openai/whisper-small`.
`TTT_ASR_BACKEND=dummy` 면 DummyASR (UI 검증용).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol

import numpy as np

DEFAULT_MODEL = "openai/whisper-small"
TARGET_SR = 16_000
MAX_NEW_TOKENS = 225

# 저장소 models/inference/* junction → model/ · models_archive/
MODEL_PRESETS: dict[str, str] = {
    "base": DEFAULT_MODEL,
    "elderly_command": "models/inference/elderly_command",
    "gangwon": "models/inference/gangwon",
    "combined": "models/inference/combined",
}


def _project_root() -> "Path":
    from pathlib import Path

    return Path(__file__).resolve().parents[3]

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
    audio = _to_mono(audio)
    if sr == TARGET_SR:
        return audio
    import librosa

    return librosa.resample(audio, orig_sr=sr, target_sr=TARGET_SR).astype(np.float32)


def _pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _effective_model_raw_from_env() -> str:
    explicit = (os.environ.get("TTT_MODEL_PATH") or "").strip()
    if explicit:
        return explicit
    preset_id = (os.environ.get("TTT_MODEL_ID") or "").strip().lower()
    if preset_id in MODEL_PRESETS:
        return MODEL_PRESETS[preset_id]
    return DEFAULT_MODEL


def _resolve_model_path(raw: str) -> str:
    from pathlib import Path

    if _is_hub_model_id(raw):
        return raw

    p = Path(raw)
    if not p.is_absolute():
        p = (_project_root() / p).resolve()

    if not p.exists():
        return DEFAULT_MODEL

    has_config = (p / "config.json").exists()
    has_preproc = (p / "preprocessor_config.json").exists()
    if not (has_config and has_preproc):
        return DEFAULT_MODEL

    return str(p)


class WhisperASR:
    def __init__(self, model_path: str | None = None, device: str | None = None):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        raw = model_path or _effective_model_raw_from_env()
        path = _resolve_model_path(raw)
        self.device = device or _pick_device()
        self.processor = WhisperProcessor.from_pretrained(path)
        self.model = WhisperForConditionalGeneration.from_pretrained(path).to(self.device)
        self.model.eval()
        self.model.generation_config.forced_decoder_ids = None
        self._torch = torch
        self.model_path = path

    def transcribe(self, audio: np.ndarray, sr: int = TARGET_SR) -> str:
        torch = self._torch
        audio_np = _resample_if_needed(audio, sr)

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
            )
        return self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()


class DummyASR:
    def __init__(self, fixed_text: str = "더미 인식 결과"):
        self.fixed_text = fixed_text
        self.calls: list[tuple[int, int]] = []

    def transcribe(self, audio: np.ndarray, sr: int = TARGET_SR) -> str:
        audio = _to_mono(audio)
        self.calls.append((int(audio.shape[0]), int(sr)))
        return self.fixed_text


@lru_cache(maxsize=1)
def get_asr() -> ASRBackend:
    backend = os.environ.get("TTT_ASR_BACKEND", "whisper").lower()
    if backend == "dummy":
        return DummyASR()
    return WhisperASR()


def describe_asr_for_status() -> dict:
    backend_env = (os.environ.get("TTT_ASR_BACKEND") or "whisper").lower()
    env_path = (os.environ.get("TTT_MODEL_PATH") or "").strip()
    env_preset = (os.environ.get("TTT_MODEL_ID") or "").strip()

    if backend_env == "dummy":
        get_asr()
        return {
            "asr_backend_class": "DummyASR",
            "asr_is_dummy": True,
            "env_ttt_asr_backend": os.environ.get("TTT_ASR_BACKEND", ""),
            "env_ttt_model_path": env_path,
            "env_ttt_model_id": env_preset,
            "model_requested": env_path or None,
            "model_presets": MODEL_PRESETS,
            "model_resolved_before_load": None,
            "model_loaded_path": None,
            "device": None,
            "local_whisper_checkpoint_ok": None,
            "using_openai_whisper_small_fallback": False,
        }

    requested = _effective_model_raw_from_env()
    resolved_preview = _resolve_model_path(requested)

    from pathlib import Path

    local_checkpoint_ok: bool | None = None
    if _is_hub_model_id(resolved_preview):
        local_checkpoint_ok = None
    else:
        p = Path(resolved_preview)
        local_checkpoint_ok = (
            p.is_dir()
            and (p / "config.json").is_file()
            and (p / "preprocessor_config.json").is_file()
        )

    asr = get_asr()
    cls_name = type(asr).__name__
    loaded_path = getattr(asr, "model_path", None)
    device = getattr(asr, "device", None)
    is_dummy = cls_name == "DummyASR"
    fallback_used = (
        not is_dummy
        and loaded_path == DEFAULT_MODEL
        and requested != DEFAULT_MODEL
        and not _is_hub_model_id(requested)
    )

    return {
        "asr_backend_class": cls_name,
        "asr_is_dummy": is_dummy,
        "env_ttt_asr_backend": os.environ.get("TTT_ASR_BACKEND", ""),
        "env_ttt_model_path": env_path,
        "env_ttt_model_id": env_preset,
        "model_requested": requested,
        "model_presets": MODEL_PRESETS,
        "model_resolved_before_load": resolved_preview,
        "model_loaded_path": loaded_path,
        "device": device,
        "local_whisper_checkpoint_ok": local_checkpoint_ok,
        "using_openai_whisper_small_fallback": fallback_used,
    }


def _is_hub_model_id(raw: str) -> bool:
    if not raw or "/" not in raw or "\\" in raw:
        return False
    if raw.startswith(("/", ".", "~")):
        return False
    if len(raw) > 2 and raw[1] == ":":
        return False
    parts = raw.split("/")
    return len(parts) == 2 and all(parts)
