"""
Whisper 기반 모델 래퍼
AI Hub 한국어 방언·노인 데이터로 초기 fine-tuning된 모델을 관리합니다.
"""

import torch
import torch.nn as nn
from pathlib import Path
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    WhisperConfig,
)
from loguru import logger


class KoreanWhisperModel(nn.Module):
    """
    Whisper 모델 래퍼
    - 한국어 특화 생성 파라미터 설정
    - 체크포인트 저장/로드
    - TTT 적응을 위한 레이어 접근 인터페이스 제공
    """

    def __init__(self, model_name: str = "openai/whisper-small"):
        super().__init__()
        logger.info(f"모델 로드 중: {model_name}")
        self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
        self.processor = WhisperProcessor.from_pretrained(model_name)
        self.model_name = model_name

        # 한국어 강제 디코딩 설정
        self.forced_decoder_ids = self.processor.get_decoder_prompt_ids(
            language="korean", task="transcribe"
        )
        self.model.config.forced_decoder_ids = self.forced_decoder_ids
        self.model.config.suppress_tokens = []

    @property
    def device(self) -> torch.device:
        return next(self.model.parameters()).device

    def forward(
        self,
        input_features: torch.Tensor,
        labels: torch.Tensor | None = None,
    ) -> dict:
        output = self.model(
            input_features=input_features,
            labels=labels,
        )
        return output

    @torch.no_grad()
    def transcribe(self, input_features: torch.Tensor) -> list[str]:
        """음성 특징 → 텍스트 변환 (추론 전용)"""
        predicted_ids = self.model.generate(
            input_features,
            forced_decoder_ids=self.forced_decoder_ids,
            max_new_tokens=225,
        )
        transcripts = self.processor.batch_decode(
            predicted_ids, skip_special_tokens=True
        )
        return transcripts

    def freeze_all(self):
        """전체 파라미터 동결"""
        for param in self.model.parameters():
            param.requires_grad = False

    def unfreeze_layers(self, layer_names: list[str]):
        """지정 레이어만 학습 가능하게 설정 (TTT용)"""
        self.freeze_all()
        unfrozen_count = 0
        for name, param in self.model.named_parameters():
            if any(layer_name in name for layer_name in layer_names):
                param.requires_grad = True
                unfrozen_count += 1
        logger.info(f"TTT 학습 파라미터 수: {unfrozen_count}")

    def unfreeze_encoder_top_k(self, k: int = 2):
        """인코더 상위 k개 레이어만 학습 가능하게 설정"""
        self.freeze_all()
        encoder_layers = self.model.model.encoder.layers
        n = len(encoder_layers)
        for i in range(max(0, n - k), n):
            for param in encoder_layers[i].parameters():
                param.requires_grad = True
        # 인코더 layer_norm도 학습
        for param in self.model.model.encoder.layer_norm.parameters():
            param.requires_grad = True
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        logger.info(f"인코더 상위 {k}레이어 언프리즈: 학습 파라미터 {trainable:,}개")

    def unfreeze_all(self):
        """전체 파라미터 학습 가능 (초기 파인튜닝용)"""
        for param in self.model.parameters():
            param.requires_grad = True
        total = sum(p.numel() for p in self.model.parameters())
        logger.info(f"전체 파라미터 언프리즈: {total:,}개")

    def save(self, output_dir: str):
        """모델 및 프로세서 저장"""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(path))
        self.processor.save_pretrained(str(path))
        logger.success(f"모델 저장 완료: {path}")

    @classmethod
    def load(cls, checkpoint_dir: str) -> "KoreanWhisperModel":
        """저장된 체크포인트에서 로드"""
        instance = cls.__new__(cls)
        super(KoreanWhisperModel, instance).__init__()
        instance.model = WhisperForConditionalGeneration.from_pretrained(checkpoint_dir)
        instance.processor = WhisperProcessor.from_pretrained(checkpoint_dir)
        instance.model_name = checkpoint_dir
        instance.forced_decoder_ids = instance.processor.get_decoder_prompt_ids(
            language="korean", task="transcribe"
        )
        instance.model.config.forced_decoder_ids = instance.forced_decoder_ids
        logger.success(f"모델 로드 완료: {checkpoint_dir}")
        return instance

    def count_parameters(self) -> dict:
        total = sum(p.numel() for p in self.model.parameters())
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        return {
            "total": total,
            "trainable": trainable,
            "frozen": total - trainable,
            "trainable_ratio": trainable / total,
        }
