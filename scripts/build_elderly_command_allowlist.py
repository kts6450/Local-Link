#!/usr/bin/env python3
"""
명령어 음성(노인남녀) 라벨 zip만 순회해 학습에 태울 발화 stem 목록·통계를 만든다.
오디오 없이 실행 가능 (데이터량 사전 조절용).

예:
  python scripts/build_elderly_command_allowlist.py \\
    --labels-root data/raw/elderly_labels \\
    --config configs/elderly_command_filter.yaml \\
    --output data/processed/elderly_command_allowlist_train.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import zlib
import zipfile
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from loguru import logger

from data.elderly_command_filter import (
    ElderlyCommandFilterConfig,
    passes_elderly_command_label,
    skip_label_zip_path,
)


def iter_json_from_zip(zpath: Path):
    with zipfile.ZipFile(zpath, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue
            try:
                raw = zf.read(name).decode("utf-8")
                yield Path(name).stem, json.loads(raw)
            except Exception:
                continue


def process_one_zip(
    zpath: Path,
    cfg: ElderlyCommandFilterConfig,
) -> tuple[list[dict], Counter, Counter]:
    if skip_label_zip_path(zpath, cfg):
        logger.info(f"건너뜀(zip 규칙): {zpath}")
        return [], Counter(), Counter()

    kept_rows: list[dict] = []
    dialect_c = Counter()
    category_c = Counter()

    for stem, label in iter_json_from_zip(zpath):
        if not passes_elderly_command_label(label, cfg):
            continue

        sp = label.get("화자정보") or {}
        dia = str(sp.get("Dialect") or "").strip() or "(empty)"
        dialect_c[dia] += 1

        basic = label.get("기본정보") or {}
        cat = str(basic.get("DataCategory") or "").strip() or "(unknown)"
        category_c[cat] += 1

        fi = label.get("파일정보") or {}
        wav_name = str(fi.get("FileName") or "").strip()
        kept_rows.append(
            {
                "stem": stem,
                "wav_file_name": wav_name or None,
                "label_zip": str(zpath),
                "data_category": cat,
                "dialect": dia if dia != "(empty)" else "",
                "gender": sp.get("Gender"),
                "age_band": sp.get("Age"),
                "region": sp.get("Region"),
            }
        )

    adler = zlib.adler32(zpath.name.encode("utf-8")) & 0x7FFFFFFF
    rng = random.Random(cfg.random_seed + adler)
    frac = cfg.sample_fraction_per_label_zip
    if frac < 1.0 and kept_rows:
        k = max(1, int(len(kept_rows) * frac))
        rng.shuffle(kept_rows)
        kept_rows = kept_rows[:k]

    cap = cfg.max_samples_per_label_zip
    if cap is not None and len(kept_rows) > cap:
        rng.shuffle(kept_rows)
        kept_rows = kept_rows[:cap]

    return kept_rows, dialect_c, category_c


def main() -> None:
    p = argparse.ArgumentParser(description="명령어 노인 라벨 기반 allowlist · 통계")
    p.add_argument(
        "--labels-root",
        type=Path,
        default=_ROOT / "data/raw/elderly_labels",
        help="명령어 음성(노인남녀) 상위 폴더 (그 아래 Training 등 탐색)",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=_ROOT / "configs/elderly_command_filter.yaml",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "data/processed/elderly_command_allowlist_train.jsonl",
    )
    p.add_argument(
        "--stats-output",
        type=Path,
        default=None,
        help="미지정 시 --output 과 같은 폴더에 <output stem>_stats.json",
    )
    args = p.parse_args()

    # 상대 경로 인자는 레포 루트 기준 (conda run 시 cwd가 달라도 동작)
    if not args.config.is_absolute():
        args.config = (_ROOT / args.config).resolve()
    if not args.output.is_absolute():
        args.output = (_ROOT / args.output).resolve()
    if args.stats_output is None:
        args.stats_output = args.output.parent / f"{args.output.stem}_stats.json"
    elif not args.stats_output.is_absolute():
        args.stats_output = (_ROOT / args.stats_output).resolve()
    if not args.labels_root.is_absolute():
        args.labels_root = (_ROOT / args.labels_root).resolve()

    cfg = ElderlyCommandFilterConfig.from_yaml(args.config)

    label_zips = sorted(
        z
        for z in args.labels_root.rglob("*.zip")
        if "[라벨]" in z.name and "대본" not in z.parts
    )
    if not label_zips:
        logger.error(f"[라벨]*.zip 없음: {args.labels_root}")
        raise SystemExit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.stats_output.parent.mkdir(parents=True, exist_ok=True)

    total_written = 0
    glob_dialect: Counter = Counter()
    glob_category: Counter = Counter()

    with open(args.output, "w", encoding="utf-8") as out_f:
        for zpath in label_zips:
            rows, dia, cat = process_one_zip(zpath, cfg)
            glob_dialect.update(dia)
            glob_category.update(cat)
            for row in rows:
                out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                total_written += 1
            logger.info(f"{zpath.name}: 유지 {len(rows)}줄")

    stats = {
        "total_rows": total_written,
        "label_zips_processed": len(label_zips),
        "config_path": str(args.config),
        "dialect_top": glob_dialect.most_common(40),
        "data_category_top": glob_category.most_common(40),
    }
    with open(args.stats_output, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.success(f"allowlist {total_written}줄 → {args.output}")
    logger.success(f"통계 → {args.stats_output}")


if __name__ == "__main__":
    main()
