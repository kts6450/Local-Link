"""
AI Hub 데이터 다운로드 가이드 및 자동화 스크립트

AI Hub (https://aihub.or.kr) 에서 아래 데이터셋을 신청하세요:
  1. 한국어 방언 발화 데이터  (약 900GB, 학술 무료)
  2. 노인 음성 데이터          (약 300GB, 학술 무료)

승인 후 aihub 공식 CLI로 다운로드:
    pip install aihubshell
    aihubshell -mode d -datasetkey {데이터셋_키} -o ./data/raw/
"""

import os
import sys
import argparse
from pathlib import Path
from loguru import logger


AIHUB_DATASETS = {
    "dialect": {
        "name": "한국어 방언 발화",
        "key": "71",
        "description": "경상/전라/충청/강원/제주 방언 약 900GB",
        "url": "https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&aihubDataSe=realm&dataSetSn=71",
    },
    "elderly": {
        "name": "노인 음성 데이터",
        "key": "129",
        "description": "60세 이상 발화 데이터 약 300GB",
        "url": "https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&aihubDataSe=realm&dataSetSn=129",
    },
    "kss": {
        "name": "KSS Korean Speech",
        "key": None,
        "description": "공개 한국어 음성 12시간 (HuggingFace에서 직접 다운로드 가능)",
        "url": "https://huggingface.co/datasets/mozilla-foundation/common_voice_13_0",
    }
}


def print_guide():
    logger.info("=" * 60)
    logger.info("AI Hub 데이터 다운로드 가이드")
    logger.info("=" * 60)
    for key, info in AIHUB_DATASETS.items():
        logger.info(f"\n[{key.upper()}] {info['name']}")
        logger.info(f"  설명: {info['description']}")
        logger.info(f"  URL : {info['url']}")

    logger.info("\n📌 다운로드 절차:")
    logger.info("  1. https://aihub.or.kr 회원가입")
    logger.info("  2. 위 URL에서 '신청하기' 클릭 → 학술 목적 선택")
    logger.info("  3. 1~3일 내 승인 이메일 수신")
    logger.info("  4. pip install aihubshell")
    logger.info("  5. 아래 명령어로 다운로드:")
    logger.info("     aihubshell -mode d -datasetkey 71 -o ./data/raw/dialect")
    logger.info("     aihubshell -mode d -datasetkey 129 -o ./data/raw/elderly")
    logger.info("=" * 60)


def download_kss_sample():
    """HuggingFace에서 KSS 소규모 샘플 다운로드 (즉시 사용 가능)"""
    try:
        from datasets import load_dataset
        logger.info("KSS Common Voice 샘플 다운로드 중 (HuggingFace)...")
        ds = load_dataset(
            "mozilla-foundation/common_voice_13_0",
            "ko",
            split="train[:500]",
            trust_remote_code=True,
        )
        output_dir = Path("./data/raw/kss_sample")
        output_dir.mkdir(parents=True, exist_ok=True)

        import json
        import soundfile as sf
        import numpy as np

        manifest = []
        for i, item in enumerate(ds):
            audio_arr = np.array(item["audio"]["array"], dtype=np.float32)
            sr = item["audio"]["sampling_rate"]
            audio_path = output_dir / f"sample_{i:04d}.wav"
            sf.write(str(audio_path), audio_arr, sr)
            manifest.append({
                "audio_path": str(audio_path),
                "transcript": item["sentence"],
                "dialect": "서울",
                "speaker_age": 0,
                "speaker_id": item.get("client_id", f"anon_{i}"),
                "duration_sec": len(audio_arr) / sr,
            })

        manifest_path = output_dir / "manifest.jsonl"
        with open(manifest_path, "w", encoding="utf-8") as f:
            for m in manifest:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")

        logger.success(f"KSS 샘플 {len(manifest)}개 다운로드 완료: {output_dir}")
        return str(manifest_path)

    except Exception as e:
        logger.error(f"KSS 다운로드 실패: {e}")
        logger.info("먼저 'pip install datasets' 실행 후 재시도하세요.")
        return None


def parse_args():
    p = argparse.ArgumentParser(description="데이터 다운로드 도우미")
    p.add_argument("--guide", action="store_true", help="AI Hub 가이드 출력")
    p.add_argument("--kss-sample", action="store_true", help="KSS 샘플 500개 즉시 다운로드")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.guide or not any(vars(args).values()):
        print_guide()
    if args.kss_sample:
        download_kss_sample()
