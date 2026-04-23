"""
AI Hub 방언·노인 데이터로 Whisper 초기 파인튜닝

사용법:
    python -m train.finetune --config configs/config.yaml
"""

import argparse
import os
import yaml
import torch

torch.backends.cudnn.benchmark = False
torch.backends.cudnn.enabled = True
from pathlib import Path
from torch.optim import AdamW
from torch.optim.lr_scheduler import LinearLR, CosineAnnealingLR, SequentialLR
from transformers import get_cosine_schedule_with_warmup
from tqdm import tqdm
from loguru import logger

from models.base_whisper import KoreanWhisperModel
from data.dataset import build_dataloaders, build_dataloaders_from_split_dir, build_dataloaders_from_manifests
from evaluation.metrics import compute_wer_cer


def parse_args():
    parser = argparse.ArgumentParser(description="Whisper 한국어 노인·방언 파인튜닝")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--manifest", default=None, help="manifest.jsonl 경로")
    parser.add_argument("--train_manifest", default=None, help="train manifest 경로")
    parser.add_argument("--val_manifest", default=None, help="val manifest 경로")
    parser.add_argument("--split_dir", default=None, help="고정 분할(train/val/test.jsonl) 디렉토리")
    parser.add_argument("--resume", default=None, help="재시작할 체크포인트 경로")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


class Trainer:
    def __init__(
        self,
        cfg: dict,
        manifest_path: str,
        device: str,
        resume: str | None,
        split_dir: str | None = None,
    ):
        self.cfg = cfg
        self.device = torch.device(device)
        self.output_dir = Path(cfg["finetune"]["output_dir"])
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 모델 로드
        if resume:
            logger.info(f"체크포인트 복원: {resume}")
            self.model = KoreanWhisperModel.load(resume)
        else:
            self.model = KoreanWhisperModel(cfg["model"]["base"])
        self.model.model.to(self.device)
        self.model.unfreeze_all()

        # VRAM 절약: gradient checkpointing (활성화 재계산으로 메모리 60% 절감)
        self.model.model.gradient_checkpointing_enable()

        # fp16 혼합정밀도 학습
        self.scaler = torch.cuda.amp.GradScaler()
        self.use_amp = (self.device.type == "cuda")

        # 데이터 로더
        if split_dir:
            self.train_loader, self.val_loader, _ = build_dataloaders_from_split_dir(
                split_dir=split_dir,
                processor=self.model.processor,
                batch_size=cfg["finetune"]["batch_size"],
            )
        elif self.cfg.get("train_manifest") and self.cfg.get("val_manifest"):
            self.train_loader, self.val_loader = build_dataloaders_from_manifests(
                train_manifest=self.cfg["train_manifest"],
                val_manifest=self.cfg["val_manifest"],
                processor=self.model.processor,
                batch_size=cfg["finetune"]["batch_size"],
                num_workers=cfg["finetune"].get("num_workers", 2),
            )
        else:
            self.train_loader, self.val_loader, _ = build_dataloaders(
                manifest_path=manifest_path,
                processor=self.model.processor,
                batch_size=cfg["finetune"]["batch_size"],
            )

        # 옵티마이저 & 스케줄러
        self.optimizer = AdamW(
            self.model.model.parameters(),
            lr=cfg["finetune"]["learning_rate"],
            weight_decay=cfg["finetune"]["weight_decay"],
        )
        total_steps = len(self.train_loader) * cfg["finetune"]["num_epochs"]
        warmup_steps = int(total_steps * cfg["finetune"]["warmup_ratio"])
        self.scheduler = get_cosine_schedule_with_warmup(
            self.optimizer, warmup_steps, total_steps
        )

        self.best_val_wer = float("inf")
        self.global_step = 0

    def _train_epoch(self, epoch: int) -> float:
        self.model.model.train()
        total_loss = 0.0
        accum_steps = self.cfg["finetune"].get("gradient_accumulation_steps", 1)
        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch} [Train]")

        self.optimizer.zero_grad()
        for step, batch in enumerate(pbar):
            input_features = batch["input_features"].to(self.device)
            labels = batch["labels"].to(self.device)

            with torch.cuda.amp.autocast(enabled=self.use_amp):
                output = self.model(input_features=input_features, labels=labels)
                loss = output.loss / accum_steps

            self.scaler.scale(loss).backward()

            if (step + 1) % accum_steps == 0:
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(
                    self.model.model.parameters(), max_norm=1.0
                )
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.scheduler.step()
                self.optimizer.zero_grad()
                self.global_step += 1

                total_loss += loss.item() * accum_steps
                pbar.set_postfix(
                    loss=f"{loss.item() * accum_steps:.4f}",
                    lr=f"{self.scheduler.get_last_lr()[0]:.2e}",
                )

                if self.global_step % self.cfg["finetune"]["eval_steps"] == 0:
                    val_wer = self._validate()
                    logger.info(f"Step {self.global_step} | Val WER: {val_wer:.4f}")
                    if val_wer < self.best_val_wer:
                        self.best_val_wer = val_wer
                        self.model.save(str(self.output_dir / "best"))
                        logger.success(f"최고 모델 저장 (WER: {val_wer:.4f})")
                    self.model.model.train()

        num_updates = len(self.train_loader) // accum_steps
        return total_loss / max(num_updates, 1)

    @torch.no_grad()
    def _validate(self) -> float:
        self.model.model.eval()
        all_refs, all_hyps = [], []

        for batch in tqdm(self.val_loader, desc="Validation", leave=False):
            input_features = batch["input_features"].to(self.device)
            predicted_ids = self.model.model.generate(
                input_features,
                forced_decoder_ids=self.model.forced_decoder_ids,
                max_new_tokens=225,
            )
            hypotheses = self.model.processor.batch_decode(
                predicted_ids, skip_special_tokens=True
            )
            references = self.model.processor.batch_decode(
                batch["labels"].tolist(), skip_special_tokens=True
            )
            all_hyps.extend(hypotheses)
            all_refs.extend(references)

        metrics = compute_wer_cer(all_refs, all_hyps)
        return metrics["wer"]

    def train(self):
        num_epochs = self.cfg["finetune"]["num_epochs"]
        params = self.model.count_parameters()
        logger.info(
            f"학습 시작 | 총 파라미터: {params['total']:,} | "
            f"배치: {self.cfg['finetune']['batch_size']} | "
            f"에폭: {num_epochs}"
        )

        for epoch in range(1, num_epochs + 1):
            train_loss = self._train_epoch(epoch)
            val_wer = self._validate()
            logger.info(
                f"Epoch {epoch}/{num_epochs} | "
                f"Train Loss: {train_loss:.4f} | Val WER: {val_wer:.4f}"
            )

            ckpt_path = self.output_dir / f"epoch_{epoch:02d}"
            self.model.save(str(ckpt_path))

        logger.success(f"학습 완료! 최고 Val WER: {self.best_val_wer:.4f}")
        return self.best_val_wer


def main():
    args = parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    os.makedirs("logs", exist_ok=True)
    logger.add(cfg["logging"]["file"], rotation="10 MB")

    if args.train_manifest and args.val_manifest:
        cfg["train_manifest"] = args.train_manifest
        cfg["val_manifest"] = args.val_manifest

    trainer = Trainer(
        cfg=cfg,
        manifest_path=args.manifest,
        device=args.device,
        resume=args.resume,
        split_dir=args.split_dir,
    )
    trainer.train()


if __name__ == "__main__":
    main()
