"""
TTT (Test-Time Training) 적응 모듈 — 핵심 구현

사용자별 발화 패턴에 실시간으로 적응합니다:
  1. 캘리브레이션: 사용자가 읽은 20개 문장으로 상위 레이어 업데이트
  2. 지속 적응: 인식 결과 수정 시 추가 학습
  3. 프로파일 저장/복원: 다음 세션에도 개인화 유지
"""

import copy
import json
import time
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from loguru import logger

from models.base_whisper import KoreanWhisperModel


@dataclass
class UserProfile:
    """사용자 개인화 프로파일"""
    user_id: str
    dialect: str = "unknown"
    age: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    calibration_done: bool = False
    n_corrections: int = 0
    wer_before: float = 0.0       # TTT 이전 WER
    wer_after: float = 0.0        # TTT 이후 WER
    adaptation_history: list[dict] = field(default_factory=list)

    def record_adaptation(self, wer: float, loss: float):
        self.wer_after = wer
        self.last_updated = time.time()
        self.adaptation_history.append({
            "timestamp": time.time(),
            "wer": wer,
            "loss": loss,
            "n_corrections": self.n_corrections,
        })

    def save(self, profile_dir: str):
        path = Path(profile_dir) / f"{self.user_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, user_id: str, profile_dir: str) -> Optional["UserProfile"]:
        path = Path(profile_dir) / f"{user_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class TTTAdapter:
    """
    Test-Time Training 적응 엔진

    동작 방식:
      - 베이스 모델의 상위 인코더 레이어만 언프리즈
      - 사용자 발화 데이터로 짧은 gradient descent 수행
      - 적응 전/후 WER 추적
      - 사용자별 모델 상태(state_dict delta) 저장
    """

    def __init__(
        self,
        base_model: KoreanWhisperModel,
        profile_dir: str = "./data/user_profiles",
        top_k_layers: int = 2,
        lr: float = 1e-4,
        adaptation_steps: int = 30,
        gradient_clip: float = 1.0,
    ):
        self.base_model = base_model
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self.top_k_layers = top_k_layers
        self.lr = lr
        self.adaptation_steps = adaptation_steps
        self.gradient_clip = gradient_clip

        # 사용자별 적응된 state_dict delta 저장
        self._user_state_cache: dict[str, dict] = {}

    def _clone_model(self) -> KoreanWhisperModel:
        """베이스 모델 복제 (사용자별 독립 모델)"""
        cloned = copy.deepcopy(self.base_model)
        cloned.to(self.base_model.device)
        return cloned

    def _run_adaptation(
        self,
        model: KoreanWhisperModel,
        audio_features: list[torch.Tensor],
        transcripts: list[str],
    ) -> list[float]:
        """
        TTT 핵심 루프: 사용자 데이터로 상위 레이어 업데이트
        Returns: 스텝별 loss 리스트
        """
        model.unfreeze_encoder_top_k(k=self.top_k_layers)
        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=self.lr,
            weight_decay=0.01,
        )

        losses = []
        device = model.device

        for step in range(self.adaptation_steps):
            # 무작위 샘플 선택 (소규모 데이터에서 반복 학습)
            idx = step % len(audio_features)
            feat = audio_features[idx].unsqueeze(0).to(device)
            label_ids = model.processor.tokenizer(
                transcripts[idx], return_tensors="pt"
            ).input_ids.to(device)

            optimizer.zero_grad()
            output = model(input_features=feat, labels=label_ids)
            loss = output.loss
            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                filter(lambda p: p.requires_grad, model.parameters()),
                self.gradient_clip,
            )
            optimizer.step()
            losses.append(loss.item())

            if (step + 1) % 10 == 0:
                logger.debug(f"  TTT Step {step+1}/{self.adaptation_steps} | loss={loss.item():.4f}")

        return losses

    def calibrate(
        self,
        user_id: str,
        audio_features: list[torch.Tensor],
        transcripts: list[str],
        dialect: str = "unknown",
        age: int = 0,
    ) -> UserProfile:
        """
        사용자 캘리브레이션 (최초 실행 or 재캘리브레이션)

        Args:
            user_id: 사용자 식별자
            audio_features: 캘리브레이션 문장의 log-mel 특징 리스트
            transcripts: 대응 정답 텍스트 리스트
        """
        assert len(audio_features) == len(transcripts), "특징과 텍스트 수가 일치해야 합니다"
        logger.info(f"[{user_id}] 캘리브레이션 시작: {len(audio_features)}개 문장")

        # TTT 이전 WER 측정
        wer_before = self._measure_wer(self.base_model, audio_features, transcripts)
        logger.info(f"[{user_id}] TTT 이전 WER: {wer_before:.1%}")

        # 사용자 전용 모델 생성 후 TTT
        user_model = self._clone_model()
        losses = self._run_adaptation(user_model, audio_features, transcripts)

        # TTT 이후 WER 측정
        wer_after = self._measure_wer(user_model, audio_features, transcripts)
        logger.info(f"[{user_id}] TTT 이후 WER: {wer_after:.1%} (개선: {wer_before - wer_after:.1%}p)")

        # state_dict delta 저장 (메모리 효율적)
        self._save_user_state(user_id, user_model)
        self._user_state_cache[user_id] = self._extract_state_delta(
            self.base_model, user_model
        )

        profile = UserProfile(
            user_id=user_id,
            dialect=dialect,
            age=age,
            calibration_done=True,
            wer_before=wer_before,
            wer_after=wer_after,
        )
        profile.record_adaptation(wer_after, np.mean(losses[-5:]))
        profile.save(str(self.profile_dir))

        return profile

    def adapt_from_correction(
        self,
        user_id: str,
        audio_feature: torch.Tensor,
        corrected_text: str,
        profile: UserProfile,
    ) -> UserProfile:
        """
        사용자 수정 입력으로 추가 적응 (지속 학습)
        """
        user_model = self._load_user_model(user_id)
        if user_model is None:
            logger.warning(f"[{user_id}] 저장된 모델 없음. 베이스 모델 사용.")
            user_model = self._clone_model()

        losses = self._run_adaptation(
            user_model,
            [audio_feature],
            [corrected_text],
        )

        self._save_user_state(user_id, user_model)
        profile.n_corrections += 1

        wer = self._measure_wer(user_model, [audio_feature], [corrected_text])
        profile.record_adaptation(wer, np.mean(losses))
        profile.save(str(self.profile_dir))

        logger.info(f"[{user_id}] 수정 학습 완료 (총 수정 횟수: {profile.n_corrections})")
        return profile

    @torch.no_grad()
    def transcribe(
        self,
        user_id: str,
        audio_feature: torch.Tensor,
    ) -> str:
        """사용자 적응 모델로 음성 인식"""
        user_model = self._load_user_model(user_id)
        if user_model is None:
            user_model = self.base_model

        feat = audio_feature.unsqueeze(0).to(user_model.device)
        results = user_model.transcribe(feat)
        return results[0] if results else ""

    def _measure_wer(
        self,
        model: KoreanWhisperModel,
        audio_features: list[torch.Tensor],
        references: list[str],
    ) -> float:
        """Word Error Rate 계산"""
        from jiwer import wer
        device = model.device
        hypotheses = []
        with torch.no_grad():
            for feat in audio_features:
                feat = feat.unsqueeze(0).to(device)
                result = model.transcribe(feat)
                hypotheses.append(result[0] if result else "")

        try:
            return wer(references, hypotheses)
        except Exception:
            return 1.0

    def _save_user_state(self, user_id: str, model: KoreanWhisperModel):
        """사용자 모델 state_dict 저장"""
        path = self.profile_dir / f"{user_id}_model.pt"
        torch.save(model.model.state_dict(), str(path))

    def _load_user_model(self, user_id: str) -> Optional[KoreanWhisperModel]:
        """저장된 사용자 모델 복원"""
        path = self.profile_dir / f"{user_id}_model.pt"
        if not path.exists():
            return None
        model = self._clone_model()
        model.model.load_state_dict(
            torch.load(str(path), map_location=model.device)
        )
        return model

    @staticmethod
    def _extract_state_delta(
        base: KoreanWhisperModel,
        adapted: KoreanWhisperModel,
    ) -> dict:
        """베이스 모델 대비 변화된 파라미터만 추출 (메모리 절약)"""
        delta = {}
        base_sd = base.model.state_dict()
        adapted_sd = adapted.model.state_dict()
        for key in base_sd:
            diff = adapted_sd[key] - base_sd[key]
            if diff.abs().max().item() > 1e-7:
                delta[key] = diff.cpu()
        return delta

    def get_improvement_summary(self, user_id: str) -> dict:
        """개선 현황 요약"""
        profile = UserProfile.load(user_id, str(self.profile_dir))
        if profile is None:
            return {}
        return {
            "user_id": user_id,
            "wer_before": profile.wer_before,
            "wer_after": profile.wer_after,
            "wer_improvement_pp": profile.wer_before - profile.wer_after,
            "wer_improvement_pct": (
                (profile.wer_before - profile.wer_after) / profile.wer_before * 100
                if profile.wer_before > 0 else 0
            ),
            "n_corrections": profile.n_corrections,
            "adaptation_history": profile.adaptation_history,
        }
