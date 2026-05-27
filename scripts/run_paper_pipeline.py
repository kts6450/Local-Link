"""
논문 실험 파이프라인 실행기.

순서:
1) 분할 생성
2) B0/B1 평가
3) P1/P2 평가
4) 통계검증
5) 아블레이션
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="paper pipeline")
    p.add_argument("--manifest", required=True)
    p.add_argument("--finetuned_model", required=True)
    p.add_argument("--split_dir", default="./data/processed/splits")
    p.add_argument("--result_dir", default="./evaluation/results")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    Path(args.split_dir).mkdir(parents=True, exist_ok=True)
    Path(args.result_dir).mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            "-m",
            "data.split_protocol",
            "--manifest",
            args.manifest,
            "--output_dir",
            args.split_dir,
            "--seed",
            str(args.seed),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "evaluation.run_baselines",
            "--split_dir",
            args.split_dir,
            "--finetuned_model",
            args.finetuned_model,
            "--output_dir",
            args.result_dir,
            "--seed",
            str(args.seed),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "evaluation.run_ttt_variants",
            "--split_dir",
            args.split_dir,
            "--base_model",
            args.finetuned_model,
            "--output_dir",
            args.result_dir,
            "--seed",
            str(args.seed),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "evaluation.stat_tests",
            "--baseline_csv",
            str(Path(args.result_dir) / "baseline_per_speaker.csv"),
            "--ttt_csv",
            str(Path(args.result_dir) / "ttt_variants_per_speaker.csv"),
            "--output",
            str(Path(args.result_dir) / "stat_tests.json"),
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "evaluation.run_ablation",
            "--split_dir",
            args.split_dir,
            "--base_model",
            args.finetuned_model,
            "--output",
            str(Path(args.result_dir) / "ablation.csv"),
            "--seed",
            str(args.seed),
        ]
    )


if __name__ == "__main__":
    main()
