"""
TTT 전·후 성능 비교 평가 스크립트

사용법:
    python -m evaluation.evaluate \
        --base_model ./checkpoints/finetune/best \
        --manifest ./data/processed/manifest.jsonl \
        --output ./evaluation/results
"""

import argparse
import json
import torch
import yaml
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from pathlib import Path
from tqdm import tqdm
from loguru import logger

from models.base_whisper import KoreanWhisperModel
from models.ttt_adapter import TTTAdapter, UserProfile
from data.dataset import KoreanSpeechDataset, UserCalibrationDataset
from evaluation.metrics import (
    compute_wer_cer,
    compute_dialect_metrics,
    compute_age_group_metrics,
    compute_ttt_improvement,
    BenchmarkReporter,
)

# 한국어 폰트 설정 (matplotlib)
plt.rcParams["axes.unicode_minus"] = False
try:
    font_path = fm.findfont(fm.FontProperties(family="Malgun Gothic"))
    plt.rcParams["font.family"] = "Malgun Gothic"
except Exception:
    pass

SAMPLE_RATE = 16_000


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/config.yaml")
    p.add_argument("--base_model", required=True, help="파인튜닝된 Whisper 체크포인트")
    p.add_argument("--manifest", required=True, help="평가 데이터 manifest.jsonl")
    p.add_argument("--output", default="./evaluation/results")
    p.add_argument("--n_calibration", type=int, default=20, help="캘리브레이션 샘플 수")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def load_manifest(path: str) -> list[dict]:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            samples.append(json.loads(line))
    return samples


def group_by_speaker(samples: list[dict]) -> dict[str, list[dict]]:
    """화자 ID 기준으로 그룹화"""
    groups: dict[str, list[dict]] = {}
    for s in samples:
        sid = s["speaker_id"]
        groups.setdefault(sid, []).append(s)
    return groups


def evaluate_speaker(
    speaker_id: str,
    samples: list[dict],
    base_model: KoreanWhisperModel,
    adapter: TTTAdapter,
    n_calibration: int,
    device: torch.device,
) -> dict | None:
    """화자 1명에 대해 TTT 전·후 WER 측정"""
    if len(samples) < n_calibration + 5:
        return None

    import random
    random.shuffle(samples)
    calib_samples = samples[:n_calibration]
    test_samples = samples[n_calibration:]

    def sample_to_feature(s: dict) -> torch.Tensor:
        import librosa
        import numpy as np
        audio, _ = librosa.load(s["audio_path"], sr=SAMPLE_RATE, mono=True)
        feat = base_model.processor.feature_extractor(
            audio, sampling_rate=SAMPLE_RATE, return_tensors="pt"
        ).input_features[0]
        return feat

    # TTT 이전: 베이스 모델로 추론
    refs_test = [s["transcript"] for s in test_samples]
    hyps_before = []
    with torch.no_grad():
        for s in tqdm(test_samples, desc=f"[{speaker_id}] Before TTT", leave=False):
            feat = sample_to_feature(s).unsqueeze(0).to(device)
            hyp = base_model.transcribe(feat)[0]
            hyps_before.append(hyp)

    wer_before = compute_wer_cer(refs_test, hyps_before)["wer"]

    # 캘리브레이션 (TTT)
    calib_features = [sample_to_feature(s) for s in calib_samples]
    calib_texts = [s["transcript"] for s in calib_samples]
    dialect = samples[0].get("dialect", "unknown")
    age = samples[0].get("speaker_age", 0)

    profile = adapter.calibrate(
        user_id=speaker_id,
        audio_features=calib_features,
        transcripts=calib_texts,
        dialect=dialect,
        age=age,
    )

    # TTT 이후: 적응 모델로 추론
    hyps_after = []
    for s in tqdm(test_samples, desc=f"[{speaker_id}] After TTT", leave=False):
        feat = sample_to_feature(s)
        hyp = adapter.transcribe(speaker_id, feat)
        hyps_after.append(hyp)

    wer_after = compute_wer_cer(refs_test, hyps_after)["wer"]

    return {
        "user_id": speaker_id,
        "dialect": dialect,
        "age": age,
        "wer_before": wer_before,
        "wer_after": wer_after,
        "improvement_pp": wer_before - wer_after,
        "n_test_samples": len(test_samples),
    }


def plot_wer_comparison(results_df: pd.DataFrame, output_dir: Path):
    """TTT 전·후 WER 비교 시각화"""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("TTT 적용 전·후 성능 비교", fontsize=16, fontweight="bold")

    # 1. 화자별 WER 비교 막대 그래프
    ax = axes[0]
    x = range(len(results_df))
    ax.bar([i - 0.2 for i in x], results_df["wer_before"], 0.4,
           label="TTT 이전", color="#FF6B6B", alpha=0.8)
    ax.bar([i + 0.2 for i in x], results_df["wer_after"], 0.4,
           label="TTT 이후", color="#4ECDC4", alpha=0.8)
    ax.set_xlabel("화자")
    ax.set_ylabel("WER (낮을수록 좋음)")
    ax.set_title("화자별 WER 비교")
    ax.legend()
    ax.set_xticks(list(x))
    ax.set_xticklabels(results_df["user_id"].tolist(), rotation=45, ha="right", fontsize=7)

    # 2. 방언별 평균 WER
    ax = axes[1]
    dialect_df = results_df.groupby("dialect")[["wer_before", "wer_after"]].mean().reset_index()
    bar_width = 0.35
    x2 = range(len(dialect_df))
    ax.bar([i - bar_width / 2 for i in x2], dialect_df["wer_before"], bar_width,
           label="TTT 이전", color="#FF6B6B", alpha=0.8)
    ax.bar([i + bar_width / 2 for i in x2], dialect_df["wer_after"], bar_width,
           label="TTT 이후", color="#4ECDC4", alpha=0.8)
    ax.set_xlabel("방언")
    ax.set_ylabel("평균 WER")
    ax.set_title("방언별 평균 WER")
    ax.legend()
    ax.set_xticks(list(x2))
    ax.set_xticklabels(dialect_df["dialect"].tolist(), rotation=30, ha="right")

    # 3. 개선 효과 분포
    ax = axes[2]
    ax.hist(results_df["improvement_pp"] * 100, bins=15, color="#45B7D1",
            edgecolor="white", alpha=0.8)
    ax.axvline(results_df["improvement_pp"].mean() * 100, color="red",
               linestyle="--", label=f"평균: {results_df['improvement_pp'].mean()*100:.1f}%p")
    ax.set_xlabel("WER 개선량 (%p)")
    ax.set_ylabel("화자 수")
    ax.set_title("TTT 개선 효과 분포")
    ax.legend()

    plt.tight_layout()
    save_path = output_dir / "wer_comparison.png"
    plt.savefig(str(save_path), dpi=150, bbox_inches="tight")
    logger.info(f"그래프 저장: {save_path}")
    plt.close()


def plot_dialect_heatmap(results_df: pd.DataFrame, output_dir: Path):
    """방언별·연령대별 성능 히트맵"""
    def age_group(age):
        if age < 60: return "~59세"
        elif age < 70: return "60대"
        elif age < 80: return "70대"
        else: return "80세+"

    results_df = results_df.copy()
    results_df["age_group"] = results_df["age"].apply(age_group)

    pivot = results_df.pivot_table(
        values="improvement_pp", index="age_group", columns="dialect",
        aggfunc="mean"
    ) * 100

    age_order = [g for g in ["~59세", "60대", "70대", "80세+"] if g in pivot.index]
    pivot = pivot.reindex(age_order)

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.heatmap(
        pivot, annot=True, fmt=".1f", cmap="YlOrRd",
        linewidths=0.5, ax=ax, cbar_kws={"label": "WER 개선량 (%p)"}
    )
    ax.set_title("방언×연령대별 TTT 개선 히트맵", fontsize=13, fontweight="bold")
    ax.set_xlabel("방언")
    ax.set_ylabel("연령대")

    save_path = output_dir / "dialect_age_heatmap.png"
    plt.savefig(str(save_path), dpi=150, bbox_inches="tight")
    logger.info(f"히트맵 저장: {save_path}")
    plt.close()


def main():
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)

    logger.info(f"평가 시작 | 디바이스: {device}")

    base_model = KoreanWhisperModel.load(args.base_model)
    base_model.model.to(device)
    base_model.model.eval()

    adapter = TTTAdapter(base_model=base_model)
    samples = load_manifest(args.manifest)
    speaker_groups = group_by_speaker(samples)
    logger.info(f"총 화자 수: {len(speaker_groups)}")

    reporter = BenchmarkReporter()
    all_results = []

    for speaker_id, spk_samples in tqdm(speaker_groups.items(), desc="화자별 평가"):
        result = evaluate_speaker(
            speaker_id=speaker_id,
            samples=spk_samples,
            base_model=base_model,
            adapter=adapter,
            n_calibration=args.n_calibration,
            device=device,
        )
        if result is None:
            continue
        all_results.append(result)
        reporter.add_result(
            user_id=result["user_id"],
            dialect=result["dialect"],
            age=result["age"],
            wer_before=result["wer_before"],
            wer_after=result["wer_after"],
            n_calibration_samples=args.n_calibration,
        )

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(str(output_dir / "results.csv"), index=False, encoding="utf-8-sig")

    reporter.print_summary()

    plot_wer_comparison(results_df, output_dir)
    plot_dialect_heatmap(results_df, output_dir)

    summary = reporter.summary()
    with open(str(output_dir / "summary.json"), "w", encoding="utf-8") as f:
        import json
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.success(f"평가 완료! 결과 저장: {output_dir}")


if __name__ == "__main__":
    main()
