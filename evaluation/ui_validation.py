"""
고령층 친화 UI 가설 검증 스크립트.

입력: app/demo.py에서 생성한 ui_events.csv
출력: UI 요약 지표 JSON/CSV
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UI validation metrics")
    p.add_argument("--event_csv", default="./evaluation/results/ui_events.csv")
    p.add_argument("--output_dir", default="./evaluation/results")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.event_csv)
    if df.empty:
        raise ValueError("이벤트 로그가 비어 있습니다.")

    # 숫자형 변환
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    session_groups = df.groupby("session_id")
    session_rows = []
    for session_id, g in session_groups:
        uid = g["user_id"].iloc[0]
        calib = g[g["event_type"] == "calibration_complete"]["value"]
        correction_count = int((g["event_type"] == "correction_submitted").sum())
        base_time = g[g["event_type"] == "base_transcribe_complete"]["value"].mean()
        ttt_time = g[g["event_type"] == "ttt_transcribe_complete"]["value"].mean()
        session_rows.append(
            {
                "session_id": session_id,
                "user_id": uid,
                "calibration_time_sec": float(calib.iloc[0]) if len(calib) else None,
                "n_corrections": correction_count,
                "avg_base_transcribe_sec": float(base_time) if pd.notna(base_time) else None,
                "avg_ttt_transcribe_sec": float(ttt_time) if pd.notna(ttt_time) else None,
            }
        )

    summary_df = pd.DataFrame(session_rows)
    summary_df.to_csv(output_dir / "ui_session_summary.csv", index=False, encoding="utf-8-sig")

    aggregate = {
        "n_sessions": int(len(summary_df)),
        "avg_calibration_time_sec": float(summary_df["calibration_time_sec"].dropna().mean())
        if "calibration_time_sec" in summary_df else None,
        "avg_corrections_per_session": float(summary_df["n_corrections"].mean()),
        "avg_base_transcribe_sec": float(summary_df["avg_base_transcribe_sec"].dropna().mean())
        if "avg_base_transcribe_sec" in summary_df else None,
        "avg_ttt_transcribe_sec": float(summary_df["avg_ttt_transcribe_sec"].dropna().mean())
        if "avg_ttt_transcribe_sec" in summary_df else None,
    }
    with (output_dir / "ui_validation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(aggregate, f, ensure_ascii=False, indent=2)
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
