"""
평가 지표 모듈
WER(단어 오류율), CER(글자 오류율) 및 방언별·연령대별 성능 분석
"""

import re
import numpy as np
import pandas as pd
from jiwer import wer, cer
from collections import defaultdict
from loguru import logger


def normalize_korean(text: str) -> str:
    """한국어 텍스트 정규화 (평가 전 처리)"""
    # 구두점 제거
    text = re.sub(r"[.,!?;:'\"\-\(\)\[\]…]", "", text)
    # 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_wer_cer(
    references: list[str],
    hypotheses: list[str],
    normalize: bool = True,
) -> dict[str, float]:
    """WER, CER 동시 계산"""
    if not references or not hypotheses:
        return {"wer": 1.0, "cer": 1.0}

    if normalize:
        references = [normalize_korean(r) for r in references]
        hypotheses = [normalize_korean(h) for h in hypotheses]

    # 빈 문자열 처리
    refs = [r if r else " " for r in references]
    hyps = [h if h else " " for h in hypotheses]

    word_error_rate = wer(refs, hyps)
    char_error_rate = cer(refs, hyps)

    return {
        "wer": round(word_error_rate, 4),
        "cer": round(char_error_rate, 4),
    }


def compute_dialect_metrics(
    references: list[str],
    hypotheses: list[str],
    dialects: list[str],
) -> pd.DataFrame:
    """방언별 WER/CER 분석"""
    results = defaultdict(lambda: {"refs": [], "hyps": []})

    for ref, hyp, dialect in zip(references, hypotheses, dialects):
        results[dialect]["refs"].append(ref)
        results[dialect]["hyps"].append(hyp)

    rows = []
    for dialect, data in sorted(results.items()):
        metrics = compute_wer_cer(data["refs"], data["hyps"])
        rows.append({
            "방언": dialect,
            "샘플 수": len(data["refs"]),
            "WER": metrics["wer"],
            "CER": metrics["cer"],
        })

    df = pd.DataFrame(rows)
    return df


def compute_age_group_metrics(
    references: list[str],
    hypotheses: list[str],
    ages: list[int],
) -> pd.DataFrame:
    """연령대별 WER/CER 분석"""
    def age_to_group(age: int) -> str:
        if age < 60:
            return "~59세"
        elif age < 70:
            return "60대"
        elif age < 80:
            return "70대"
        else:
            return "80세+"

    results = defaultdict(lambda: {"refs": [], "hyps": []})
    for ref, hyp, age in zip(references, hypotheses, ages):
        group = age_to_group(age)
        results[group]["refs"].append(ref)
        results[group]["hyps"].append(hyp)

    rows = []
    order = ["~59세", "60대", "70대", "80세+"]
    for group in order:
        if group not in results:
            continue
        data = results[group]
        metrics = compute_wer_cer(data["refs"], data["hyps"])
        rows.append({
            "연령대": group,
            "샘플 수": len(data["refs"]),
            "WER": metrics["wer"],
            "CER": metrics["cer"],
        })

    return pd.DataFrame(rows)


def compute_ttt_improvement(
    wer_before: float,
    wer_after: float,
) -> dict:
    """TTT 개선 효과 요약"""
    improvement_pp = wer_before - wer_after
    improvement_pct = (improvement_pp / wer_before * 100) if wer_before > 0 else 0

    return {
        "wer_before": wer_before,
        "wer_after": wer_after,
        "improvement_pp": round(improvement_pp, 4),      # percentage point
        "improvement_pct": round(improvement_pct, 1),    # 상대적 개선율 %
        "accuracy_before": round(1 - wer_before, 4),
        "accuracy_after": round(1 - wer_after, 4),
    }


class BenchmarkReporter:
    """
    전체 실험 결과를 종합하여 리포트 생성
    """

    def __init__(self):
        self.records: list[dict] = []

    def add_result(
        self,
        user_id: str,
        dialect: str,
        age: int,
        wer_before: float,
        wer_after: float,
        n_calibration_samples: int,
    ):
        self.records.append({
            "user_id": user_id,
            "dialect": dialect,
            "age": age,
            "wer_before": wer_before,
            "wer_after": wer_after,
            "improvement_pp": wer_before - wer_after,
            "n_calibration_samples": n_calibration_samples,
        })

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)

    def summary(self) -> dict:
        df = self.to_dataframe()
        if df.empty:
            return {}

        return {
            "n_users": len(df),
            "avg_wer_before": df["wer_before"].mean(),
            "avg_wer_after": df["wer_after"].mean(),
            "avg_improvement_pp": df["improvement_pp"].mean(),
            "best_improvement": df["improvement_pp"].max(),
            "dialect_avg": df.groupby("dialect")["improvement_pp"].mean().to_dict(),
        }

    def print_summary(self):
        s = self.summary()
        logger.info("=" * 50)
        logger.info("📊 TTT 성능 요약")
        logger.info(f"  대상 사용자: {s['n_users']}명")
        logger.info(f"  평균 WER (TTT 전): {s['avg_wer_before']:.1%}")
        logger.info(f"  평균 WER (TTT 후): {s['avg_wer_after']:.1%}")
        logger.info(f"  평균 개선: {s['avg_improvement_pp']:.1%}p")
        logger.info(f"  최대 개선: {s['best_improvement']:.1%}p")
        logger.info("  방언별 평균 개선:")
        for dialect, imp in sorted(s["dialect_avg"].items()):
            logger.info(f"    - {dialect}: {imp:.1%}p")
        logger.info("=" * 50)
