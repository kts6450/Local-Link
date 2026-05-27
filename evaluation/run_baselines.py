"""
B0/B1 베이스라인 평가 스크립트.

B0: openai/whisper-small (범용)
B1: 파인튜닝 체크포인트 (도메인)
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="B0/B1 baseline evaluation")
    p.add_argument("--split_dir", required=True, help="train/val/test.jsonl 디렉토리")
    p.add_argument("--finetuned_model", required=True, help="B1 체크포인트 경로")
    p.add_argument("--output_dir", default="./evaluation/results")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n_calibration", type=int, default=20)
    p.add_argument("--min_test_samples", type=int, default=5)
    return p.parse_args()


def evaluate_model_on_batches(
    model: KoreanWhisperModel,
    batches,
    device: torch.device,
) -> pd.DataFrame:
    rows = []
    model.model.to(device)
    model.model.eval()

    for batch in batches:
        refs, hyps = [], []
        for s in batch.test_samples:
            feat = sample_to_feature(s, model).unsqueeze(0).to(device)
            hyp = model.transcribe(feat)[0]
            refs.append(str(s["transcript"]))
            hyps.append(hyp)
        metric = compute_wer_cer(refs, hyps)
        rows.append(
            {
                "speaker_id": batch.speaker_id,
                "dialect": batch.dialect,
                "age": batch.age,
                "n_test_samples": len(batch.test_samples),
                "wer": metric["wer"],
                "cer": metric["cer"],
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)

    test_rows = load_split_file(args.split_dir, "test")
    batches = build_speaker_batches(
        test_rows,
        n_calibration=args.n_calibration,
        min_test_samples=args.min_test_samples,
        seed=args.seed,
    )
    logger.info(f"평가 대상 화자 수: {len(batches)}")

    b0_model = KoreanWhisperModel("openai/whisper-small")
    b1_model = KoreanWhisperModel.load(args.finetuned_model)

    b0_df = evaluate_model_on_batches(b0_model, batches, device)
    b1_df = evaluate_model_on_batches(b1_model, batches, device)

    b0_df = b0_df.rename(columns={"wer": "wer_b0", "cer": "cer_b0"})
    b1_df = b1_df.rename(columns={"wer": "wer_b1", "cer": "cer_b1"})
    merged = b0_df.merge(
        b1_df[["speaker_id", "wer_b1", "cer_b1"]],
        on="speaker_id",
        how="inner",
    )
    merged["wer_gain_b1_vs_b0"] = merged["wer_b0"] - merged["wer_b1"]

    merged_path = output_dir / "baseline_per_speaker.csv"
    merged.to_csv(merged_path, index=False, encoding="utf-8-sig")

    summary = {
        "n_speakers": int(len(merged)),
        "avg_wer_b0": float(merged["wer_b0"].mean()),
        "avg_wer_b1": float(merged["wer_b1"].mean()),
        "avg_cer_b0": float(merged["cer_b0"].mean()),
        "avg_cer_b1": float(merged["cer_b1"].mean()),
        "avg_wer_gain_b1_vs_b0": float(merged["wer_gain_b1_vs_b0"].mean()),
    }
    with (output_dir / "baseline_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.success(f"베이스라인 평가 완료: {merged_path}")
    logger.info(summary)


if __name__ == "__main__":
    main()
