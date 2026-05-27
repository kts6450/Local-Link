"""
논문 실험용 화자 독립 분할 스크립트.

- 화자 단위로 train/val/test를 분할해 화자 누수를 방지합니다.
- 방언/발화유형 비율을 최대한 유지하도록 그룹별로 분할합니다.

사용 예시:
    python -m data.split_protocol \
        --manifest ./data/processed/manifest.jsonl \
        --output_dir ./data/processed/splits \
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    seed: int = 42


def _load_manifest(path: Path) -> list[dict]:
    samples: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            samples.append(json.loads(line))
    return samples


def _bucket_key(sample: dict) -> str:
    dialect = str(sample.get("dialect", "unknown"))
    utter_type = str(sample.get("utterance_type", "unknown"))
    return f"{dialect}::{utter_type}"


def _speaker_key(sample: dict) -> str:
    return str(sample.get("speaker_id", "unknown"))


def _split_speakers_for_bucket(
    speakers: list[str],
    cfg: SplitConfig,
    rng: random.Random,
) -> tuple[set[str], set[str], set[str]]:
    shuffled = speakers[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_train = int(round(n * cfg.train_ratio))
    n_val = int(round(n * cfg.val_ratio))
    n_train = min(n_train, n)
    n_val = min(n_val, max(0, n - n_train))
    n_test = max(0, n - n_train - n_val)

    train = set(shuffled[:n_train])
    val = set(shuffled[n_train:n_train + n_val])
    test = set(shuffled[n_train + n_val:n_train + n_val + n_test])
    return train, val, test


def _assign_speakers(samples: list[dict], cfg: SplitConfig) -> dict[str, str]:
    rng = random.Random(cfg.seed)
    bucket_to_speakers: dict[str, set[str]] = defaultdict(set)
    speaker_to_samples: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        speaker = _speaker_key(s)
        bucket = _bucket_key(s)
        bucket_to_speakers[bucket].add(speaker)
        speaker_to_samples[speaker].append(s)

    speaker_assignments: dict[str, str] = {}
    for bucket, speakers in sorted(bucket_to_speakers.items()):
        train, val, test = _split_speakers_for_bucket(list(speakers), cfg, rng)
        for spk in train:
            speaker_assignments.setdefault(spk, "train")
        for spk in val:
            if spk not in speaker_assignments:
                speaker_assignments[spk] = "val"
        for spk in test:
            if spk not in speaker_assignments:
                speaker_assignments[spk] = "test"

    # 미할당 화자 방어 처리
    all_speakers = set(speaker_to_samples.keys())
    leftovers = sorted(all_speakers - set(speaker_assignments.keys()))
    for i, spk in enumerate(leftovers):
        speaker_assignments[spk] = ("train", "val", "test")[i % 3]

    return speaker_assignments


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _count_distribution(rows: list[dict], field: str) -> dict[str, int]:
    c = Counter(str(r.get(field, "unknown")) for r in rows)
    return dict(sorted(c.items(), key=lambda x: x[0]))


def _build_report(
    train_rows: list[dict],
    val_rows: list[dict],
    test_rows: list[dict],
) -> dict:
    return {
        "counts": {
            "train": len(train_rows),
            "val": len(val_rows),
            "test": len(test_rows),
            "total": len(train_rows) + len(val_rows) + len(test_rows),
        },
        "dialect_distribution": {
            "train": _count_distribution(train_rows, "dialect"),
            "val": _count_distribution(val_rows, "dialect"),
            "test": _count_distribution(test_rows, "dialect"),
        },
        "utterance_type_distribution": {
            "train": _count_distribution(train_rows, "utterance_type"),
            "val": _count_distribution(val_rows, "utterance_type"),
            "test": _count_distribution(test_rows, "utterance_type"),
        },
        "unique_speakers": {
            "train": len({_speaker_key(r) for r in train_rows}),
            "val": len({_speaker_key(r) for r in val_rows}),
            "test": len({_speaker_key(r) for r in test_rows}),
        },
    }


def create_splits(
    manifest_path: Path,
    output_dir: Path,
    cfg: SplitConfig,
) -> dict:
    samples = _load_manifest(manifest_path)
    assignments = _assign_speakers(samples, cfg)

    split_rows = {"train": [], "val": [], "test": []}
    for s in samples:
        split = assignments[_speaker_key(s)]
        row = dict(s)
        row["split"] = split
        split_rows[split].append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "train.jsonl", split_rows["train"])
    _write_jsonl(output_dir / "val.jsonl", split_rows["val"])
    _write_jsonl(output_dir / "test.jsonl", split_rows["test"])
    _write_jsonl(output_dir / "manifest_with_split.jsonl", split_rows["train"] + split_rows["val"] + split_rows["test"])

    report = _build_report(split_rows["train"], split_rows["val"], split_rows["test"])
    with (output_dir / "split_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="화자 독립/층화 분할 생성")
    p.add_argument("--manifest", required=True, help="원본 manifest.jsonl 경로")
    p.add_argument("--output_dir", required=True, help="분할 결과 저장 경로")
    p.add_argument("--train_ratio", type=float, default=0.8)
    p.add_argument("--val_ratio", type=float, default=0.1)
    p.add_argument("--test_ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = SplitConfig(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    report = create_splits(Path(args.manifest), Path(args.output_dir), cfg)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
