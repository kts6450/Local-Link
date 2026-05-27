"""
PyTorch Dataset / DataLoader 정의
Whisper 입력 형식(log-mel spectrogram + token ids)으로 변환합니다.
"""

import io
import json
import random
import functools
import zipfile
from functools import partial
import numpy as np
import soundfile as sf
import torch
from pathlib import Path
from torch.utils.data import Dataset, DataLoader, random_split
from transformers import WhisperProcessor
import librosa
from loguru import logger


SAMPLE_RATE = 16_000


@functools.lru_cache(maxsize=64)
def _open_zip(zip_path: str) -> zipfile.ZipFile:
    """zip 파일 핸들을 캐시하여 반복 open 오버헤드 제거"""
    return zipfile.ZipFile(zip_path, "r")


def load_audio_np(path: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    audio, orig_sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if orig_sr != sr:
        audio = librosa.resample(audio, orig_sr=orig_sr, target_sr=sr)
    return audio


def load_audio_from_zip(zip_path: str, entry: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    zf = _open_zip(zip_path)
    with zf.open(entry) as wav_file:
        audio_bytes = wav_file.read()
    audio, orig_sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if orig_sr != sr:
        audio = librosa.resample(audio, orig_sr=orig_sr, target_sr=sr)
    return audio


class KoreanSpeechDataset(Dataset):
    """
    AI Hub 방언·노인 음성 → Whisper 입력 형식 Dataset

    각 항목: {input_features, labels, dialect, speaker_age, speaker_id}
    """

    def __init__(
        self,
        manifest_path: str,
        processor: WhisperProcessor,
        max_label_length: int = 448,
        augment: bool = False,
    ):
        self.processor = processor
        self.max_label_length = max_label_length
        self.augment = augment

        self.samples = []
        with open(manifest_path, encoding="utf-8") as f:
            for line in f:
                self.samples.append(json.loads(line.strip()))

        logger.info(f"Dataset 로드: {len(self.samples)}개 샘플 ({manifest_path})")

    def __len__(self) -> int:
        return len(self.samples)

    def _augment_audio(self, audio: np.ndarray) -> np.ndarray:
        """노인 음성 특성 반영 데이터 증강"""
        # 발화 속도 변화 (느린 발화 시뮬레이션)
        if random.random() < 0.3:
            rate = random.uniform(0.85, 1.0)
            audio = librosa.effects.time_stretch(audio, rate=rate)

        # 피치 변화 (개인 음역대 차이)
        if random.random() < 0.2:
            steps = random.uniform(-1.5, 1.5)
            audio = librosa.effects.pitch_shift(audio, sr=SAMPLE_RATE, n_steps=steps)

        # 배경 잡음 추가 (키오스크 환경)
        if random.random() < 0.2:
            noise = np.random.randn(len(audio)) * 0.005
            audio = audio + noise

        # 볼륨 정규화
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio)) * 0.9

        return audio

    def __getitem__(self, idx: int) -> dict:
        sample = self.samples[idx]

        if "audio_zip" in sample:
            audio = load_audio_from_zip(sample["audio_zip"], sample["audio_entry"])
        else:
            audio = load_audio_np(sample["audio_path"])

        if self.augment:
            audio = self._augment_audio(audio)

        # Whisper log-mel 특징 추출
        input_features = self.processor.feature_extractor(
            audio, sampling_rate=SAMPLE_RATE, return_tensors="pt"
        ).input_features[0]

        # 텍스트 → 토큰 ID
        labels = self.processor.tokenizer(
            sample["transcript"],
            max_length=self.max_label_length,
            truncation=True,
            return_tensors="pt",
        ).input_ids[0]

        return {
            "input_features": input_features,
            "labels": labels,
            "dialect": sample.get("dialect", "unknown"),
            "speaker_age": sample.get("speaker_age", 0),
            "speaker_id": sample.get("speaker_id", "unknown"),
        }


def _collate_with_pad(batch: list[dict], pad_token_id: int) -> dict:
    return collate_fn(batch, pad_token_id=pad_token_id)


def collate_fn(batch: list[dict], pad_token_id: int = -100) -> dict:
    """배치 패딩 처리"""
    input_features = torch.stack([b["input_features"] for b in batch])

    max_len = max(b["labels"].shape[0] for b in batch)
    padded_labels = torch.full((len(batch), max_len), pad_token_id, dtype=torch.long)
    for i, b in enumerate(batch):
        padded_labels[i, : b["labels"].shape[0]] = b["labels"]

    return {
        "input_features": input_features,
        "labels": padded_labels,
        "dialects": [b["dialect"] for b in batch],
        "speaker_ages": [b["speaker_age"] for b in batch],
    }


def build_dataloaders(
    manifest_path: str,
    processor: WhisperProcessor,
    batch_size: int = 8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    num_workers: int = 0,
    augment_train: bool = True,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Train / Val / Test DataLoader 생성"""

    full_dataset = KoreanSpeechDataset(manifest_path, processor, augment=False)
    n = len(full_dataset)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    n_train = n - n_test - n_val

    train_ds, val_ds, test_ds = random_split(
        full_dataset, [n_train, n_val, n_test],
        generator=torch.Generator().manual_seed(42)
    )

    pad_id = processor.tokenizer.pad_token_id
    _collate = partial(_collate_with_pad, pad_token_id=pad_id)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        collate_fn=_collate, num_workers=num_workers
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        collate_fn=_collate, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_ds, batch_size=batch_size, shuffle=False,
        collate_fn=_collate, num_workers=num_workers
    )

    logger.info(f"DataLoader 생성 완료: train={n_train} / val={n_val} / test={n_test}")
    return train_loader, val_loader, test_loader


def build_dataloaders_from_split_dir(
    split_dir: str,
    processor: WhisperProcessor,
    batch_size: int = 8,
    num_workers: int = 0,
    augment_train: bool = True,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """
    고정 분할(train/val/test.jsonl) 기반 DataLoader 생성.
    논문 재현성을 위해 권장합니다.
    """
    split_path = Path(split_dir)
    train_manifest = split_path / "train.jsonl"
    val_manifest = split_path / "val.jsonl"
    test_manifest = split_path / "test.jsonl"

    if not (train_manifest.exists() and val_manifest.exists() and test_manifest.exists()):
        raise FileNotFoundError(
            f"분할 파일이 없습니다: {train_manifest}, {val_manifest}, {test_manifest}"
        )

    train_ds = KoreanSpeechDataset(
        str(train_manifest), processor, augment=augment_train
    )
    val_ds = KoreanSpeechDataset(str(val_manifest), processor, augment=False)
    test_ds = KoreanSpeechDataset(str(test_manifest), processor, augment=False)

    pad_id = processor.tokenizer.pad_token_id
    _collate = partial(_collate_with_pad, pad_token_id=pad_id)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        collate_fn=_collate, num_workers=num_workers
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        collate_fn=_collate, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_ds, batch_size=batch_size, shuffle=False,
        collate_fn=_collate, num_workers=num_workers
    )

    logger.info(
        "고정 분할 DataLoader 생성 완료: "
        f"train={len(train_ds)} / val={len(val_ds)} / test={len(test_ds)}"
    )
    return train_loader, val_loader, test_loader


def build_dataloaders_from_manifests(
    train_manifest: str,
    val_manifest: str,
    processor: WhisperProcessor,
    batch_size: int = 8,
    num_workers: int = 0,
    augment_train: bool = True,
) -> tuple[DataLoader, DataLoader]:
    """train/val manifest를 각각 받아 DataLoader 생성"""
    train_ds = KoreanSpeechDataset(train_manifest, processor, augment=augment_train)
    val_ds = KoreanSpeechDataset(val_manifest, processor, augment=False)

    pad_id = processor.tokenizer.pad_token_id
    _collate = partial(_collate_with_pad, pad_token_id=pad_id)

    pin = num_workers > 0
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        collate_fn=_collate, num_workers=num_workers,
        pin_memory=pin, persistent_workers=(num_workers > 0),
        prefetch_factor=(2 if num_workers > 0 else None),
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        collate_fn=_collate, num_workers=num_workers,
        pin_memory=pin, persistent_workers=(num_workers > 0),
        prefetch_factor=(2 if num_workers > 0 else None),
    )
    logger.info(f"DataLoader 생성: train={len(train_ds)} / val={len(val_ds)} (num_workers={num_workers})")
    return train_loader, val_loader


class UserCalibrationDataset(Dataset):
    """
    TTT 사용자 캘리브레이션 데이터셋
    사용자가 읽은 20개 문장을 실시간 적응에 사용
    """

    CALIBRATION_SENTENCES = [
        "오늘 날씨가 참 좋네요.",
        "저는 아침마다 산책을 합니다.",
        "병원에 가려면 몇 번 버스를 타야 하나요?",
        "이 약은 하루에 세 번 식후에 드세요.",
        "자식들이 모두 건강하게 지내고 있어요.",
        "요즘 무릎이 많이 아파서 걷기가 힘들어요.",
        "점심은 뭘 먹을까요? 된장찌개 어때요?",
        "은행에서 돈을 찾으려고 왔는데요.",
        "전화번호를 좀 알려주시겠어요?",
        "기차표를 예매하고 싶은데 어떻게 하면 되나요?",
        "오랜만에 친구들을 만나서 너무 반가웠어요.",
        "이 동네에 산 지가 벌써 삼십 년이 넘었어요.",
        "손자가 이번에 학교에 입학했답니다.",
        "시장에 가서 채소를 좀 사와야겠어요.",
        "혈압약을 계속 먹어야 한다고 하던데요.",
        "텔레비전이 갑자기 안 나와서 걱정이에요.",
        "어디서 버스를 내려야 하는지 모르겠어요.",
        "고향이 어디세요? 저는 경상도 출신이에요.",
        "요즘 젊은 사람들은 말이 너무 빨라요.",
        "다음에 또 놀러 오세요. 반갑습니다.",
    ]

    def __init__(
        self,
        audio_paths: list[str],
        transcripts: list[str],
        processor: WhisperProcessor,
    ):
        assert len(audio_paths) == len(transcripts)
        self.audio_paths = audio_paths
        self.transcripts = transcripts
        self.processor = processor

    def __len__(self) -> int:
        return len(self.audio_paths)

    def __getitem__(self, idx: int) -> dict:
        audio = load_audio_np(self.audio_paths[idx])
        input_features = self.processor.feature_extractor(
            audio, sampling_rate=SAMPLE_RATE, return_tensors="pt"
        ).input_features[0]
        labels = self.processor.tokenizer(
            self.transcripts[idx], return_tensors="pt"
        ).input_ids[0]
        return {"input_features": input_features, "labels": labels}
