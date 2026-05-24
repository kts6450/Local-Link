"""데모용 대규모 시드 — 판매자 15명 + 상품 30 + 숙박 30 + 체험 30 + 리뷰.

호출:
    환경변수 LOCAL_LINK_DEMO_SEED=1 로 백엔드를 띄우면 비어있을 때 자동 시드.
    또는 `python -m db.demo_seed` 직접 실행.
"""
from __future__ import annotations

from .demo_seed_runner import seed_demo_marketplace

__all__ = ["seed_demo_marketplace"]


if __name__ == "__main__":
    n = seed_demo_marketplace(force=True)
    print(f"seeded: sellers={n['sellers']} listings={n['listings']} reviews={n['reviews']}")
