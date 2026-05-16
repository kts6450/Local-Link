"""
AI Hub 「명령어 음성(노인남녀)」 JSON 라벨 필터.

포맷 B: 전사정보 / 화자정보 / 기타정보(QualityStatus)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ElderlyCommandFilterConfig:
    quality_good_only: bool = True
    exclude_not_provided_dialect: bool = True
    exclude_irregular_zip: bool = True
    # True면 경로·이름에 validation 이 들어간 라벨 zip 스킵
    exclude_validation_zip: bool = True
    # True면 Validation zip 만 처리 (검증용 목록)
    validation_zip_only: bool = False
    random_seed: int = 42
    sample_fraction_per_label_zip: float = 1.0
    max_samples_per_label_zip: int | None = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> ElderlyCommandFilterConfig:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(
            quality_good_only=bool(raw.get("quality_good_only", True)),
            exclude_not_provided_dialect=bool(raw.get("exclude_not_provided_dialect", True)),
            exclude_irregular_zip=bool(raw.get("exclude_irregular_zip", True)),
            exclude_validation_zip=bool(raw.get("exclude_validation_zip", True)),
            validation_zip_only=bool(raw.get("validation_zip_only", False)),
            random_seed=int(raw.get("random_seed", 42)),
            sample_fraction_per_label_zip=float(raw.get("sample_fraction_per_label_zip", 1.0)),
            max_samples_per_label_zip=raw.get("max_samples_per_label_zip"),
        )


def skip_label_zip_path(zip_path: Path, cfg: ElderlyCommandFilterConfig) -> bool:
    """라벨 zip 통째로 건너뛸지 (경로·파일명 기준)."""
    name_lower = zip_path.name.lower()
    is_validation = "validation" in name_lower or any(
        "validation" in part.lower() for part in zip_path.parts
    )
    if cfg.exclude_validation_zip and is_validation:
        return True
    if cfg.validation_zip_only and not is_validation:
        return True
    if cfg.exclude_irregular_zip and "비정형" in zip_path.name:
        return True
    return False


def passes_elderly_command_label(label: dict[str, Any], cfg: ElderlyCommandFilterConfig) -> bool:
    """
    명령어(노년) 포맷 B 위주. 자유대화 포맷 A(발화정보 키 있음)는 그대로 통과.
    """
    if "발화정보" in label:
        return True

    if cfg.quality_good_only:
        extra = label.get("기타정보") or {}
        q = str(extra.get("QualityStatus") or "").strip()
        if q and q != "Good":
            return False

    if cfg.exclude_not_provided_dialect:
        sp = label.get("화자정보") or {}
        d = str(sp.get("Dialect") or "").strip()
        if d and "notprovided" in d.lower():
            return False

    return True


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "configs" / "elderly_command_filter.yaml"
