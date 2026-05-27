"""
논문 실험 공용 유틸리티.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import librosa
import torch

from models.base_whisper import KoreanWhisperModel


SAMPLE_RATE = 16_000


@dataclass
class SpeakerBatch:
    speaker_id: str
    dialect: str
    age: int
    calibration_samples: list[dict]
    test_samples: list[dict]


def load_manifest(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_split_file(split_dir: str, split: str) -> list[dict]:
    path = Path(split_dir) / f"{split}.jsonl"
    return load_manifest(str(path))


def group_by_speaker(samples: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        grouped[str(s.get("speaker_id", "unknown"))].append(s)
    return grouped


def build_speaker_batches(
    samples: list[dict],
    n_calibration: int,
    min_test_samples: int = 5,
    seed: int = 42,
) -> list[SpeakerBatch]:
    rng = random.Random(seed)
    batches: list[SpeakerBatch] = []
    grouped = group_by_speaker(samples)
    for speaker_id, spk_samples in grouped.items():
        if len(spk_samples) < n_calibration + min_test_samples:
            continue
        copied = spk_samples[:]
        rng.shuffle(copied)
        calib = copied[:n_calibration]
        test = copied[n_calibration:]
        batches.append(
            SpeakerBatch(
                speaker_id=speaker_id,
                dialect=str(copied[0].get("dialect", "unknown")),
                age=int(copied[0].get("speaker_age", 0)),
                calibration_samples=calib,
                test_samples=test,
            )
        )
    return batches


def sample_to_feature(sample: dict, model: KoreanWhisperModel) -> torch.Tensor:
    audio, _ = librosa.load(sample["audio_path"], sr=SAMPLE_RATE, mono=True)
    return model.processor.feature_extractor(
        audio,
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
    ).input_features[0]


def transcribe_batch(
    model: KoreanWhisperModel,
    rows: list[dict],
    device: torch.device,
) -> tuple[list[str], list[str], list[str]]:
    refs, hyps, dialects = [], [], []
    for row in rows:
        feat = sample_to_feature(row, model).unsqueeze(0).to(device)
        hyp = model.transcribe(feat)[0]
        refs.append(str(row["transcript"]))
        hyps.append(hyp)
        dialects.append(str(row.get("dialect", "unknown")))
    return refs, hyps, dialects
