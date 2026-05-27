"""
P1/P2 개인 적응 평가 스크립트.

P1: 1회 캘리브레이션 후 고정 모델 평가
P2: 캘리브레이션 + 테스트 중 사용자 수정 반영 지속 적응
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
from loguru import logger

from evaluation.experiment_utils import (
    build_speaker_batches,
    load_split_file,
    sample_to_feature,
)
from evaluation.metrics import compute_wer_cer
from models.base_whisper import KoreanWhisperModel
from models.ttt_adapter import TTTAdapter, UserProfile


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P1/P2 TTT evaluation")
    p.add_argument("--split_dir", required=True)
    p.add_argument("--base_model", required=True, help="B1 체크포인트 경로")
    p.add_argument("--output_dir", default="./evaluation/results")
    p.add_argument("--n_calibration", type=int, default=20)
    p.add_argument("--min_test_samples", type=int, default=8)
    p.add_argument("--online_corrections", type=int, default=3, help="P2에서 온라인 수정 반영 샘플 수")
    p.add_argument("--top_k_layers", type=int, default=2)
    p.add_argument("--adaptation_steps", type=int, default=30)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def evaluate_variants_for_speaker(
    batch,
    adapter: TTTAdapter,
    device: torch.device,
    online_corrections: int,
) -> dict:
    user_id = batch.speaker_id
    calib_feats = [sample_to_feature(s, adapter.base_model) for s in batch.calibration_samples]
    calib_refs = [str(s["transcript"]) for s in batch.calibration_samples]

    profile = adapter.calibrate(
        user_id=user_id,
        audio_features=calib_feats,
        transcripts=calib_refs,
        dialect=batch.dialect,
        age=batch.age,
    )

    p1_refs, p1_hyps = [], []
    for row in batch.test_samples:
        feat = sample_to_feature(row, adapter.base_model)
        hyp = adapter.transcribe(user_id, feat)
        p1_refs.append(str(row["transcript"]))
        p1_hyps.append(hyp)
    p1 = compute_wer_cer(p1_refs, p1_hyps)

    # P2: 앞부분 샘플은 사용자 수정 반영으로 온라인 적응에 사용
    p2_refs, p2_hyps = [], []
    p2_profile = profile
    test_rows = batch.test_samples
    correction_end = min(online_corrections, len(test_rows))

    for idx, row in enumerate(test_rows):
        feat = sample_to_feature(row, adapter.base_model)
        hyp = adapter.transcribe(user_id, feat)
        ref = str(row["transcript"])

        if idx < correction_end:
            p2_profile = adapter.adapt_from_correction(
                user_id=user_id,
                audio_feature=feat,
                corrected_text=ref,
                profile=p2_profile,
            )
            continue

        p2_refs.append(ref)
        p2_hyps.append(hyp)

    # 남은 평가 샘플이 0개면 P1과 동일한 값으로 대체
    if p2_refs:
        p2 = compute_wer_cer(p2_refs, p2_hyps)
    else:
        p2 = p1

    return {
        "speaker_id": user_id,
        "dialect": batch.dialect,
        "age": batch.age,
        "n_test_samples": len(batch.test_samples),
        "wer_p1": p1["wer"],
        "cer_p1": p1["cer"],
        "wer_p2": p2["wer"],
        "cer_p2": p2["cer"],
        "wer_gain_p2_vs_p1": p1["wer"] - p2["wer"],
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)

    samples = load_split_file(args.split_dir, "test")
    batches = build_speaker_batches(
        samples,
        n_calibration=args.n_calibration,
        min_test_samples=args.min_test_samples,
        seed=args.seed,
    )
    logger.info(f"TTT 변형 평가 대상 화자 수: {len(batches)}")

    model = KoreanWhisperModel.load(args.base_model)
    model.model.to(device)
    model.model.eval()
    adapter = TTTAdapter(
        base_model=model,
        top_k_layers=args.top_k_layers,
        adaptation_steps=args.adaptation_steps,
        lr=args.lr,
    )

    records = []
    for batch in batches:
        records.append(
            evaluate_variants_for_speaker(
                batch=batch,
                adapter=adapter,
                device=device,
                online_corrections=args.online_corrections,
            )
        )

    df = pd.DataFrame(records)
    out_csv = output_dir / "ttt_variants_per_speaker.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    summary = {
        "n_speakers": int(len(df)),
        "avg_wer_p1": float(df["wer_p1"].mean()) if len(df) else 0.0,
        "avg_wer_p2": float(df["wer_p2"].mean()) if len(df) else 0.0,
        "avg_cer_p1": float(df["cer_p1"].mean()) if len(df) else 0.0,
        "avg_cer_p2": float(df["cer_p2"].mean()) if len(df) else 0.0,
        "avg_wer_gain_p2_vs_p1": float(df["wer_gain_p2_vs_p1"].mean()) if len(df) else 0.0,
    }
    with (output_dir / "ttt_variants_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.success(f"TTT 변형 평가 완료: {out_csv}")
    logger.info(summary)


if __name__ == "__main__":
    main()
