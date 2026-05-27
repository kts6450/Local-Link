"""
리소스 절약형 아블레이션 실행 스크립트.

축:
- top_k_layers: 1/2/3
- adaptation_steps: 10/20/30
- n_calibration: 10/20/30
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import pandas as pd
import torch

from evaluation.experiment_utils import build_speaker_batches, load_split_file
from evaluation.run_ttt_variants import evaluate_variants_for_speaker
from models.base_whisper import KoreanWhisperModel
from models.ttt_adapter import TTTAdapter


def parse_int_list(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TTT ablation")
    p.add_argument("--split_dir", required=True)
    p.add_argument("--base_model", required=True)
    p.add_argument("--output", default="./evaluation/results/ablation.csv")
    p.add_argument("--top_k", default="1,2,3")
    p.add_argument("--steps", default="10,20,30")
    p.add_argument("--calibration", default="10,20,30")
    p.add_argument("--online_corrections", type=int, default=3)
    p.add_argument("--max_speakers", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    top_k_list = parse_int_list(args.top_k)
    steps_list = parse_int_list(args.steps)
    calib_list = parse_int_list(args.calibration)

    test_rows = load_split_file(args.split_dir, "test")
    device = torch.device(args.device)
    base_model = KoreanWhisperModel.load(args.base_model)
    base_model.model.to(device)
    base_model.model.eval()

    records = []
    for top_k, steps, n_calib in itertools.product(top_k_list, steps_list, calib_list):
        batches = build_speaker_batches(
            test_rows,
            n_calibration=n_calib,
            min_test_samples=8,
            seed=args.seed,
        )[: args.max_speakers]

        adapter = TTTAdapter(
            base_model=base_model,
            top_k_layers=top_k,
            adaptation_steps=steps,
            lr=1e-4,
        )

        for batch in batches:
            result = evaluate_variants_for_speaker(
                batch=batch,
                adapter=adapter,
                device=device,
                online_corrections=args.online_corrections,
            )
            records.append(
                {
                    "top_k_layers": top_k,
                    "adaptation_steps": steps,
                    "n_calibration": n_calib,
                    **result,
                }
            )

    df = pd.DataFrame(records)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    summary = (
        df.groupby(["top_k_layers", "adaptation_steps", "n_calibration"])
        .agg(
            avg_wer_p1=("wer_p1", "mean"),
            avg_wer_p2=("wer_p2", "mean"),
            avg_gain=("wer_gain_p2_vs_p1", "mean"),
            n_speakers=("speaker_id", "nunique"),
        )
        .reset_index()
        .sort_values("avg_wer_p2")
    )
    summary.to_csv(out_path.parent / "ablation_summary.csv", index=False, encoding="utf-8-sig")
    print(summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
