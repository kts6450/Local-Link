"""
데이터 전처리 모듈
AI Hub 방언·노인 음성 데이터를 Whisper 학습 형식으로 변환합니다.
"""

import os
import json
import re
import librosa
import soundfile as sf
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from tqdm import tqdm


@dataclass
class AudioSample:
    audio_path: str
    transcript: str
    dialect: str           # 경상 / 전라 / 충청 / 강원 / 제주 / 서울
    speaker_age: int
    speaker_id: str
    duration_sec: float


SAMPLE_RATE = 16_000
MAX_DURATION = 30.0
MIN_DURATION = 0.5

# AI Hub 노이즈 표기 → 제거
NOISE_TAGS = re.compile(r"\(.*?\)|\[.*?\]|[+/*]|<.*?>|[a-zA-Z]")


def clean_transcript(text: str) -> str:
    """전사 텍스트 정규화"""
    text = NOISE_TAGS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_audio(path: str, sr: int = SAMPLE_RATE) -> Optional[np.ndarray]:
    """오디오 파일을 로드하고 모노 16kHz로 변환"""
    try:
        audio, orig_sr = librosa.load(path, sr=sr, mono=True)
        return audio
    except Exception as e:
        logger.warning(f"오디오 로드 실패: {path} → {e}")
        return None


def trim_silence(audio: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    """앞뒤 무음 제거"""
    audio_trimmed, _ = librosa.effects.trim(audio, top_db=20)
    return audio_trimmed


def validate_duration(audio: np.ndarray, sr: int = SAMPLE_RATE) -> bool:
    duration = len(audio) / sr
    return MIN_DURATION <= duration <= MAX_DURATION


class AIHubDialectPreprocessor:
    """
    AI Hub 한국어 방언 데이터셋 전처리기
    폴더 구조: {dialect}/{speaker_id}/{audio_id}.wav + label.json
    """

    def __init__(self, raw_dir: str, output_dir: str):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_label(self, label_path: Path) -> dict:
        with open(label_path, encoding="utf-8") as f:
            return json.load(f)

    def process_dialect(self, dialect: str) -> list[AudioSample]:
        dialect_dir = self.raw_dir / dialect
        if not dialect_dir.exists():
            logger.warning(f"방언 디렉토리 없음: {dialect_dir}")
            return []

        samples = []
        audio_files = list(dialect_dir.rglob("*.wav"))
        logger.info(f"[{dialect}] 오디오 파일 {len(audio_files)}개 처리 시작")

        for audio_path in tqdm(audio_files, desc=f"{dialect} 전처리"):
            label_path = audio_path.with_suffix(".json")
            if not label_path.exists():
                label_path = audio_path.parent / "label.json"

            if not label_path.exists():
                continue

            try:
                label = self.parse_label(label_path)
                transcript = clean_transcript(
                    label.get("dialect_form", label.get("standard_form", ""))
                )
                if not transcript:
                    continue

                audio = load_audio(str(audio_path))
                if audio is None:
                    continue

                audio = trim_silence(audio)
                if not validate_duration(audio):
                    continue

                out_path = self.output_dir / dialect / audio_path.name
                out_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(str(out_path), audio, SAMPLE_RATE)

                speaker_id = label.get("speaker_id", audio_path.parent.name)
                age = int(label.get("age", 0))

                samples.append(AudioSample(
                    audio_path=str(out_path),
                    transcript=transcript,
                    dialect=dialect,
                    speaker_age=age,
                    speaker_id=speaker_id,
                    duration_sec=len(audio) / SAMPLE_RATE,
                ))
            except Exception as e:
                logger.error(f"처리 오류 {audio_path}: {e}")

        logger.info(f"[{dialect}] {len(samples)}개 샘플 완료")
        return samples

    def run(self, dialects: list[str] | None = None) -> list[AudioSample]:
        if dialects is None:
            dialects = ["경상", "전라", "충청", "강원", "제주", "서울"]

        all_samples: list[AudioSample] = []
        for dialect in dialects:
            all_samples.extend(self.process_dialect(dialect))

        manifest_path = self.output_dir / "manifest.jsonl"
        with open(manifest_path, "w", encoding="utf-8") as f:
            for s in all_samples:
                f.write(json.dumps(s.__dict__, ensure_ascii=False) + "\n")

        logger.success(f"전처리 완료: 총 {len(all_samples)}개 샘플 → {manifest_path}")
        return all_samples


class AIHubElderlyPreprocessor(AIHubDialectPreprocessor):
    """AI Hub 노인 음성 데이터셋 전처리기 (60세 이상 필터링)"""

    MIN_AGE = 60

    def process_dialect(self, dialect: str) -> list[AudioSample]:
        samples = super().process_dialect(dialect)
        elderly = [s for s in samples if s.speaker_age >= self.MIN_AGE]
        logger.info(f"[{dialect}] 노인(60+) 필터: {len(samples)} → {len(elderly)}개")
        return elderly


def compute_dataset_stats(manifest_path: str) -> dict:
    """데이터셋 통계 계산"""
    samples = []
    with open(manifest_path, encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))

    if not samples:
        return {}

    durations = [s["duration_sec"] for s in samples]
    ages = [s["speaker_age"] for s in samples if s["speaker_age"] > 0]

    dialect_counts: dict[str, int] = {}
    for s in samples:
        dialect_counts[s["dialect"]] = dialect_counts.get(s["dialect"], 0) + 1

    return {
        "total_samples": len(samples),
        "total_hours": sum(durations) / 3600,
        "avg_duration_sec": np.mean(durations),
        "dialect_distribution": dialect_counts,
        "avg_speaker_age": np.mean(ages) if ages else None,
        "age_range": (min(ages), max(ages)) if ages else None,
    }


if __name__ == "__main__":
    import yaml

    with open("configs/config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    dialect_preprocessor = AIHubDialectPreprocessor(
        raw_dir=cfg["data"]["aihub_dialect_path"],
        output_dir=cfg["data"]["processed_path"] + "/dialect",
    )
    dialect_preprocessor.run(cfg["data"]["dialects"])

    elderly_preprocessor = AIHubElderlyPreprocessor(
        raw_dir=cfg["data"]["aihub_elderly_path"],
        output_dir=cfg["data"]["processed_path"] + "/elderly",
    )
    elderly_preprocessor.run()
