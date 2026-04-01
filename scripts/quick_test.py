"""
AI Hub 데이터 없이도 즉시 실행할 수 있는 TTT 기능 검증 스크립트
KSS 샘플 또는 마이크 녹음으로 TTT 전·후를 확인합니다.

사용법:
    python scripts/quick_test.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
from loguru import logger


def generate_dummy_audio(duration_sec: float = 3.0, sr: int = 16000) -> np.ndarray:
    """테스트용 더미 오디오 (실제 사용 시 마이크 or 파일로 교체)"""
    t = np.linspace(0, duration_sec, int(sr * duration_sec))
    audio = 0.3 * np.sin(2 * np.pi * 220 * t)  # 220Hz 사인파
    return audio.astype(np.float32)


def run_ttt_demo():
    from models.base_whisper import KoreanWhisperModel
    from models.ttt_adapter import TTTAdapter
    from evaluation.metrics import compute_ttt_improvement

    logger.info("=" * 55)
    logger.info("TTT × 노인·방언 음성 인식 — 기능 검증")
    logger.info("=" * 55)

    # 1. 모델 로드
    logger.info("\n[1] Whisper 모델 로드 중...")
    model = KoreanWhisperModel("openai/whisper-small")
    params = model.count_parameters()
    logger.info(f"    총 파라미터: {params['total']:,}")

    adapter = TTTAdapter(
        base_model=model,
        top_k_layers=2,
        lr=1e-4,
        adaptation_steps=5,   # 빠른 테스트용
    )

    # 2. 더미 캘리브레이션 데이터 생성
    logger.info("\n[2] 더미 캘리브레이션 데이터 생성...")
    calibration_texts = [
        "오늘 날씨가 참 좋네요.",
        "병원에 가려면 몇 번 버스를 타야 하나요?",
        "저는 아침마다 산책을 합니다.",
        "이 약은 하루에 세 번 식후에 드세요.",
        "자식들이 모두 건강하게 지내고 있어요.",
    ]
    calibration_features = []
    for text in calibration_texts:
        dummy_audio = generate_dummy_audio(duration_sec=2.0)
        feat = model.processor.feature_extractor(
            dummy_audio, sampling_rate=16000, return_tensors="pt"
        ).input_features[0]
        calibration_features.append(feat)

    logger.info(f"    캘리브레이션 샘플: {len(calibration_features)}개")

    # 3. TTT 캘리브레이션 실행
    logger.info("\n[3] TTT 캘리브레이션 실행 중...")
    profile = adapter.calibrate(
        user_id="test_user_001",
        audio_features=calibration_features,
        transcripts=calibration_texts,
        dialect="경상도",
        age=72,
    )

    # 4. 결과 출력
    improvement = compute_ttt_improvement(profile.wer_before, profile.wer_after)
    logger.info("\n" + "=" * 55)
    logger.info("TTT 적응 결과 (더미 데이터 기준)")
    logger.info(f"  이전 WER : {improvement['wer_before']:.1%}")
    logger.info(f"  이후 WER : {improvement['wer_after']:.1%}")
    logger.info(f"  개선량   : {improvement['improvement_pp']:.1%}p")
    logger.info(f"  상대 개선: {improvement['improvement_pct']:.1f}%")
    logger.info("=" * 55)

    # 5. TTT 후 추론 테스트
    logger.info("\n[5] 적응 모델 추론 테스트...")
    test_audio = generate_dummy_audio(duration_sec=3.0)
    test_feat = model.processor.feature_extractor(
        test_audio, sampling_rate=16000, return_tensors="pt"
    ).input_features[0]

    result = adapter.transcribe("test_user_001", test_feat)
    logger.info(f"    인식 결과: '{result}'")

    # 6. 모델 파라미터 확인
    logger.info("\n[6] 레이어 동결 확인...")
    model.unfreeze_encoder_top_k(k=2)
    params = model.count_parameters()
    logger.info(f"    전체 파라미터: {params['total']:,}")
    logger.info(f"    학습 파라미터: {params['trainable']:,} ({params['trainable_ratio']:.1%})")
    logger.info(f"    동결 파라미터: {params['frozen']:,}")
    logger.info("\n✅ 모든 기능 검증 완료!")


if __name__ == "__main__":
    run_ttt_demo()
