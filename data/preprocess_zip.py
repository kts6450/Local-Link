"""
ZIP 직접 읽기 전처리 모듈
압축 해제 없이 zip 파일에서 직접 음성+라벨을 읽어 manifest를 생성합니다.

데이터 구조:
  원천 zip: [원천]1.AI챗봇_1.zip → 폴더/파일명_08580.wav
  라벨 zip: [라벨]1.AI챗봇.zip   → 폴더/파일명_08580.json
"""

import io
import json
import re
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
from loguru import logger
from tqdm import tqdm


SAMPLE_RATE = 16_000
MAX_DURATION = 30.0
MIN_DURATION = 0.5

NOISE_TAGS = re.compile(r"\(.*?\)|\[.*?\]|[+/*]|<.*?>")

DIALECT_MAP = {
    "경상": "경상", "전라": "전라", "충청": "충청",
    "강원": "강원", "제주": "제주", "서울": "서울",
    "경기": "서울", "수도권": "서울", "대전": "충청",
    "부산": "경상", "대구": "경상", "광주": "전라",
}


@dataclass
class SampleMeta:
    stem: str
    transcript: str
    dialect: str
    speaker_age: int
    speaker_id: str
    duration_sec: float
    audio_zip: str      # 원천 zip 경로 (학습 시 직접 읽기용)
    audio_entry: str    # zip 내 wav 경로


def clean_transcript(text: str) -> str:
    text = NOISE_TAGS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_age(age_val) -> int:
    match = re.search(r"(\d+)", str(age_val))
    return int(match.group(1)) if match else 0


def parse_dialect(dialect_str: str, region_str: str = "") -> str:
    combined = str(dialect_str) + str(region_str)
    for keyword, dialect in DIALECT_MAP.items():
        if keyword in combined:
            return dialect
    return "기타"


def process_audio_bytes(audio_bytes: bytes) -> Optional[np.ndarray]:
    try:
        audio, _ = librosa.load(io.BytesIO(audio_bytes), sr=SAMPLE_RATE, mono=True)
        audio, _ = librosa.effects.trim(audio, top_db=20)
        duration = len(audio) / SAMPLE_RATE
        if MIN_DURATION <= duration <= MAX_DURATION:
            return audio
        return None
    except Exception as e:
        logger.warning(f"오디오 처리 실패: {e}")
        return None


def build_label_index(label_zip_path: Path) -> dict[str, dict]:
    """라벨 zip에서 {파일stem: json데이터} 인덱스 생성"""
    index = {}
    try:
        with zipfile.ZipFile(label_zip_path, "r") as zf:
            json_entries = [n for n in zf.namelist() if n.lower().endswith(".json")]
            for name in tqdm(json_entries, desc=f"라벨 인덱스 ({label_zip_path.name})", leave=False):
                stem = Path(name).stem
                try:
                    with zf.open(name) as f:
                        data = json.loads(f.read().decode("utf-8"))
                    index[stem] = data
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"라벨 zip 읽기 실패: {label_zip_path} → {e}")
    logger.info(f"라벨 인덱스 완료: {len(index)}개 ({label_zip_path.name})")
    return index


def find_label_zip(audio_zip_name: str, label_zip_dir: Path) -> Optional[Path]:
    """
    [원천]1.AI챗봇_1.zip → [라벨]1.AI챗봇.zip 매칭
    숫자.카테고리명 기준으로 매칭
    """
    match = re.search(r"\[원천\](\d+\.[^_\[]+)", audio_zip_name)
    if not match:
        return None
    category = match.group(1).strip()

        for label_zip in label_zip_dir.glob("*.zip"):
            if "[라벨]" in label_zip.name and category in label_zip.name:
                return label_zip
    return None


def process_zip_pair(
    audio_zip_path: Path,
    label_index: dict,
    min_age: int = 0,
) -> list[SampleMeta]:
    samples = []
    try:
        with zipfile.ZipFile(audio_zip_path, "r") as audio_zf:
            wav_entries = [n for n in audio_zf.namelist() if n.endswith(".wav")]
            logger.info(f"{audio_zip_path.name}: wav {len(wav_entries)}개")

            for wav_name in tqdm(wav_entries, desc=audio_zip_path.name):
                stem = Path(wav_name).stem
                if stem not in label_index:
                    continue

                label = label_index[stem]
                transcript_info = label.get("전사정보", {})
                transcript = clean_transcript(
                    transcript_info.get("LabelText",
                    transcript_info.get("TransLabelText", ""))
                )
                if not transcript:
                    continue

                speaker_info = label.get("화자정보", {})
                age = parse_age(speaker_info.get("Age", speaker_info.get("age", "0")))

                if min_age > 0 and age < min_age:
                    continue

                dialect = parse_dialect(
                    speaker_info.get("Dialect", ""),
                    speaker_info.get("Region", ""),
                )
                speaker_id = str(speaker_info.get("SpeakerName", stem))

                # 오디오 길이만 확인 (실제 바이트 로드)
                with audio_zf.open(wav_name) as wav_file:
                    audio_bytes = wav_file.read()

                audio = process_audio_bytes(audio_bytes)
                if audio is None:
                    continue

                samples.append(SampleMeta(
                    stem=stem,
                    transcript=transcript,
                    dialect=dialect,
                    speaker_age=age,
                    speaker_id=speaker_id,
                    duration_sec=len(audio) / SAMPLE_RATE,
                    audio_zip=str(audio_zip_path),
                    audio_entry=wav_name,
                ))

    except Exception as e:
        logger.error(f"zip 처리 오류 {audio_zip_path}: {e}")

    return samples


def run_preprocessing(
    audio_zip_dirs: list[str],
    label_zip_dirs: list[str],
    manifest_path: str,
    min_age: int = 0,
) -> None:
    """
    Parameters
    ----------
    audio_zip_dirs : 원천 zip이 있는 디렉토리 목록
    label_zip_dirs : 라벨 zip이 있는 디렉토리 목록
    manifest_path  : 결과 manifest.jsonl 저장 경로
    min_age        : 최소 화자 나이 (0 = 필터 없음, 60 = 노인만)
    """
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    label_dirs = [Path(d) for d in label_zip_dirs]
    all_samples: list[SampleMeta] = []
    label_cache: dict[str, dict] = {}

    for audio_dir in audio_zip_dirs:
        audio_dir = Path(audio_dir)
        audio_zips = sorted(p for p in audio_dir.rglob("*.zip") if "[원천]" in p.name)
        logger.info(f"원천 zip {len(audio_zips)}개 발견: {audio_dir}")

        for audio_zip in audio_zips:
            label_zip = None
            for label_dir in label_dirs:
                label_zip = find_label_zip(audio_zip.name, label_dir)
                if label_zip:
                    break

            if label_zip is None:
                logger.warning(f"매칭 라벨 없음: {audio_zip.name}")
                continue

            cache_key = str(label_zip)
            if cache_key not in label_cache:
                label_cache[cache_key] = build_label_index(label_zip)
            label_index = label_cache[cache_key]

            samples = process_zip_pair(audio_zip, label_index, min_age=min_age)
            all_samples.extend(samples)
            logger.info(f"  → {len(samples)}개 샘플 추가 (누적: {len(all_samples)})")

    with open(manifest_path, "w", encoding="utf-8") as f:
        for s in all_samples:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")

    total_hours = sum(s.duration_sec for s in all_samples) / 3600
    logger.success(
        f"전처리 완료: {len(all_samples)}개 샘플 ({total_hours:.1f}시간) → {manifest_path}"
    )


if __name__ == "__main__":
    run_preprocessing(
        audio_zip_dirs=[
            r"C:\Users\dns-server2\TTT-Dialect\data\raw\elderly\자유대화 음성(노인남녀)\Training",
        ],
        label_zip_dirs=[
            r"F:\TTT-data\raw\elderly",
        ],
        manifest_path=r"F:\TTT-data\processed\elderly_freeconv_train.jsonl",
        min_age=60,
    )
