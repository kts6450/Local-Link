#!/usr/bin/env python3
"""
서버에서 명령어(노인남녀) 원천 wav zip + 라벨 zip → manifest 생성.

allowlist(jsonl)를 주면 학습량 조절; 라벨만 받았던 레포에서 생성한 파일 복사해도 됨.

예 (학습 manifest):
  python scripts/run_elderly_command_preprocess.py ^
    --audio-dir F:/TTT-data/raw/elderly/명령어 음성(노인남녀)/Training ^
    --label-dir F:/TTT-data/raw/elderly_labels/명령어 음성(노인남녀)/Training ^
    --output F:/TTT-data/processed/elderly_command_train.jsonl ^
    --allowlist F:/TTT-data/processed/elderly_command_allowlist_train.jsonl

예 (검증 manifest, Validation 디렉터리 지정):
  python scripts/run_elderly_command_preprocess.py ^
    --audio-dir .../Validation --label-dir .../Validation ^
    --output .../elderly_command_val.jsonl ^
    --allowlist .../elderly_command_allowlist_val.jsonl
"""

from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.elderly_command_filter import ElderlyCommandFilterConfig
from data.preprocess_zip import run_preprocessing


def main() -> None:
    p = argparse.ArgumentParser(description="명령어 노인 wav zip → manifest")
    p.add_argument("--audio-dir", required=True, type=Path, help="[원천] zip 들어 있는 폴더 (Training 또는 Validation)")
    p.add_argument("--label-dir", required=True, type=Path, help="[라벨] zip 들어 있는 폴더")
    p.add_argument("--output", required=True, type=Path, help="출력 manifest.jsonl")
    p.add_argument("--allowlist", type=Path, default=None, help="stem 화이트리스트 jsonl (있으면 필터·샘플링은 여기서 이미 반영된 것 권장)")
    p.add_argument(
        "--filter-config",
        type=Path,
        default=None,
        help="allowlist 없을 때만 사용: configs/elderly_command_filter.yaml 등",
    )
    p.add_argument("--min-age", type=int, default=0)
    args = p.parse_args()

    label_filter_cfg = None
    stem_allowlist_path = None
    if args.allowlist is not None:
        stem_allowlist_path = str(args.allowlist.resolve())
    elif args.filter_config is not None:
        label_filter_cfg = ElderlyCommandFilterConfig.from_yaml(args.filter_config)
    else:
        raise SystemExit("--allowlist 또는 --filter-config 중 하나는 필요합니다.")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    sig = inspect.signature(run_preprocessing)
    params = sig.parameters

    def _need(name: str, value: object) -> None:
        if value is None:
            return
        if name not in params:
            raise SystemExit(
                f"현재 로드된 data/preprocess_zip.run_preprocessing 이 인자 {name!r} 을(를) 받지 않습니다.\n"
                "서버의 TTT-Dialect\\data\\preprocess_zip.py 를 레포 최신본으로 덮어쓴 뒤 다시 실행하세요.\n"
                r"(집 PC: Documents\TTT\data\preprocess_zip.py)"
            )

    _need("stem_allowlist_path", stem_allowlist_path)
    _need("label_filter_cfg", label_filter_cfg)

    call_kw: dict = {
        "audio_zip_dirs": [str(args.audio_dir.resolve())],
        "label_zip_dirs": [str(args.label_dir.resolve())],
        "manifest_path": str(args.output.resolve()),
        "min_age": args.min_age,
    }
    if "label_filter_cfg" in params:
        call_kw["label_filter_cfg"] = label_filter_cfg
    if "stem_allowlist_path" in params:
        call_kw["stem_allowlist_path"] = stem_allowlist_path

    run_preprocessing(**call_kw)


if __name__ == "__main__":
    main()
