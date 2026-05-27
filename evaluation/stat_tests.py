"""
화자 단위 통계 검증 도구.

입력:
- baseline_per_speaker.csv (B0/B1)
- ttt_variants_per_speaker.csv (P1/P2)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.stats import wilcoxon
except Exception:  # pragma: no cover
    wilcoxon = None


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """
    Cliff's delta 효과크기.
    x > y면 양수(성능 개선 방향으로 해석 가능).
    """
    n_x = len(x)
    n_y = len(y)
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    return float((gt - lt) / (n_x * n_y))


def summarize_test(name: str, before: np.ndarray, after: np.ndarray) -> dict:
    diff = before - after
    result = {
        "name": name,
        "n": int(len(diff)),
        "mean_before": float(np.mean(before)),
        "mean_after": float(np.mean(after)),
        "mean_improvement": float(np.mean(diff)),
        "median_improvement": float(np.median(diff)),
        "cliffs_delta": cliffs_delta(diff, np.zeros_like(diff)),
    }
    if wilcoxon is not None:
        stat = wilcoxon(before, after, zero_method="wilcox", correction=True)
        result["wilcoxon_statistic"] = float(stat.statistic)
        result["wilcoxon_pvalue"] = float(stat.pvalue)
    else:
        result["wilcoxon_statistic"] = None
        result["wilcoxon_pvalue"] = None
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="통계 검증 스크립트")
    p.add_argument("--baseline_csv", required=True)
    p.add_argument("--ttt_csv", required=True)
    p.add_argument("--output", default="./evaluation/results/stat_tests.json")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    baseline_df = pd.read_csv(args.baseline_csv)
    ttt_df = pd.read_csv(args.ttt_csv)

    merged = baseline_df.merge(ttt_df, on="speaker_id", how="inner")
    tests = {
        "b1_vs_b0_wer": summarize_test(
            "B1_vs_B0_WER",
            merged["wer_b0"].to_numpy(),
            merged["wer_b1"].to_numpy(),
        ),
        "p1_vs_b1_wer": summarize_test(
            "P1_vs_B1_WER",
            merged["wer_b1"].to_numpy(),
            merged["wer_p1"].to_numpy(),
        ),
        "p2_vs_p1_wer": summarize_test(
            "P2_vs_P1_WER",
            merged["wer_p1"].to_numpy(),
            merged["wer_p2"].to_numpy(),
        ),
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)

    merged.to_csv(
        out_path.parent / "paper_main_table.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(json.dumps(tests, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
