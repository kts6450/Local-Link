# 발표용 학습·평가 수치 정리

랩실 서버(`dns-server1@100.92.197.114`, `C:\Users\dns-server2\TTT-Dialect`) SSH·로그 실측 + Git 학습 코드 기준.

> **WER** = 단어 오류율 (REF 대비 삽입+삭제+치환 / REF 단어 수). 문장 오답률과 다름.

---

## 표 1. 공통 학습 하이퍼파라미터 (코드 + 서버 config)

| 항목 | Git 기본 (`configs/config.yaml`) | 서버 실측 | 코드 위치 |
|------|----------------------------------|-----------|-----------|
| Base model | `openai/whisper-small` | 동일 | `configs/config.yaml` → `model.base` |
| 학습 범위 | 전 파라미터 unfreeze | 동일 | `train/finetune.py` → `unfreeze_all()` |
| **Batch size** | **4** | **4** | `finetune.batch_size` → `DataLoader(..., batch_size=4)` |
| **Gradient accumulation** | **4** | **4** | `finetune.gradient_accumulation_steps` |
| **유효 배치 (effective batch)** | **16** | **16** | `loss / accum_steps`, 4 step마다 1회 optimizer step |
| Learning rate | 5e-5 | 5e-5 (로그 4.99e-05→4.67e-05) | AdamW + cosine warmup 10% |
| Weight decay | 0.01 | 0.01 | `finetune.weight_decay` |
| **Epoch** | 3 (Git) | **2** (서버 yaml 수정) | `finetune.num_epochs` |
| Val 검증 주기 | 2000 step | 2000 step | `finetune.eval_steps` |
| Mixed precision | fp16 (CUDA) | fp16 | `torch.cuda.amp` |
| Gradient checkpointing | ON | ON | VRAM 절약 |
| DataLoader workers | 2 | 2 | `finetune.num_workers` |
| Gradient clip | max_norm=1.0 | max_norm=1.0 | `clip_grad_norm_` |
| Checkpoint 저장 | `best` + `epoch_XX` | `C:\TTT-data\checkpoints\<실험명>\` | `output_dir` 실험별 변경 |

**배치 계산 (elderly_command 예시)**

| 항목 | 값 | 계산 |
|------|-----|------|
| Train utterances | 359,961 | manifest 줄 수 |
| Batch size | 4 | config |
| Steps / epoch | 89,991 | 359,961 ÷ 4 |
| Accum steps | 4 | config |
| Optimizer updates / epoch | 22,498 | 89,991 ÷ 4 |
| Effective batch | 16 | 4 × 4 |

---

## 표 2. 체크포인트 위치 (서버 실측)

| 모델 | `best` 경로 | epoch 폴더 | 학습 일자 |
|------|-------------|-----------|-----------|
| **elderly_command** (노인 명령어) | `C:\TTT-data\checkpoints\elderly_command\best` | `epoch_01`, `epoch_02` | 2026-05-17 ~ 05-21 |
| **combined** (강원+경상) | `C:\TTT-data\checkpoints\combined\best` | `epoch_01`, `epoch_02` | epoch_01 5/4, epoch_02 5/5 |
| **gangwon** (강원 방언) | `C:\TTT-data\checkpoints\gangwon\best` | 없음 (best만) | 2026-05-03 |
| freeconv (별도 실험) | `C:\TTT-data\checkpoints\freeconv\` | — | config `output_dir` 현재값 |

---

## 표 3. 노인 명령어 (`elderly_command`) — Training Configuration

로그: `C:\TTT-data\logs\finetune_stderr_20260517_125646.log`

| 항목 | 값 |
|------|-----|
| Base model | Whisper-small |
| Epoch | **2** (`Epoch 1/2` → `2/2`) |
| Batch | 4 × accum 4 = **유효 16** |
| Learning rate | 5e-5 |
| Train manifest | `elderly_command_train.jsonl` — **359,961** |
| Val manifest | `elderly_command_val.jsonl` — **275,298** |
| Steps / epoch | **89,991** |
| 학습 기간 | 2026-05-17 ~ 05-21 |

---

## 표 4. 노인 명령어 — Val WER (REF vs HYP)

| 시점 | Train Loss | Val WER | 비고 |
|------|------------|---------|------|
| Epoch 1, step 20000 | — | **13.25%** | `best` 1차 저장 |
| **Epoch 1/2 끝** | 0.0861 | **13.38%** | `epoch_01` 저장 |
| Epoch 2, step 40000 | — | **10.86%** | **`best` 최종 갱신** |
| **Epoch 2/2 끝** | 0.0280 | **11.34%** | epoch end (best보다 나쁨) |
| **배포용 best** | — | **10.86%** | `...\elderly_command\best` |

**개선 (Val 기준)**

| 구간 | WER | 상대 개선 |
|------|-----|-----------|
| Epoch 1 끝 → best | 13.38% → 10.86% | **−2.52%p** (약 **19%** 상대 감소) |

---

## 표 5. 4월 학습 run (`ttt.log`, 2026-04-23~24)

로그: `C:\Users\dns-server2\TTT-Dialect\logs\ttt.log`  
대상: gangwon/combined 초기 run 추정 (checkpoint 날짜와 시기상). **3 epoch**.

| Epoch | Train Loss | Val WER (epoch end) |
|-------|------------|---------------------|
| 1/3 | 0.3285 | **22.24%** |
| 2/3 | 0.2488 | **20.96%** |
| 3/3 | 0.1764 | **19.74%** |
| best (step 18000) | — | **20.64%** → `best` 저장 |

> epoch 3 끝(19.74%)이 best(20.64%)보다 좋지만, `best`는 **2000 step마다 검증할 때만** 갱신 (`train/finetune.py`).

**부가 (같은 로그)**

| 항목 | 값 |
|------|-----|
| gangwon train manifest 로드 | 239,299 samples (2026-05-03 기록) |
| combined 데이터 규모 (config 주석) | 약 **1517h** |

---

## 표 6. 실험별 요약 비교

| 실험 | Epoch | Best Val WER | 로그 | baseline(B0) WER |
|------|-------|--------------|------|------------------|
| **elderly_command** | 2 | **10.86%** | `TTT-data\logs\finetune_stderr_20260517_*.log` | **미측정** |
| gangwon/combined (4월) | 3 | 20.64% (best) / 19.74% (ep3 end) | `TTT-Dialect\logs\ttt.log` | **미측정** |
| combined (5월) | 2 | **로그 미확인** | `TTT-data\logs\` 추가 검색 필요 | **미측정** |

---

## 표 7. REF / HYP / baseline / 개선폭 (코드 vs 서버)

| 항목 | 코드 | 서버 상태 |
|------|------|-----------|
| REF (정답) | `batch["labels"]` → decode | 학습 Val WER에 사용 |
| HYP (인식) | `model.generate()` → decode | 학습 Val WER에 사용 |
| WER 계산 | `evaluation/metrics.py` → `jiwer.wer` | `_validate()`에서 호출 |
| B0 baseline | `openai/whisper-small` | `evaluation/run_baselines.py` |
| B1 fine-tuned | 체크포인트 경로 | `elderly_command\best` |
| B0→B1 개선폭 | `compute_ttt_improvement()` | **`evaluation/results` 없음 — 미실행** |

---

## 발표용 코드 인용 (배치·WER)

### 1) 설정 — batch 4, accum 4

`configs/config_server.yaml` (서버 실측 반영):

```yaml
finetune:
  learning_rate: 5.0e-5
  batch_size: 4
  gradient_accumulation_steps: 4   # 유효 배치 = 16
  num_epochs: 2
  num_workers: 2
  eval_steps: 2000
```

### 2) DataLoader에 batch_size 전달

`train/finetune.py`:

```python
self.train_loader, self.val_loader = build_dataloaders_from_manifests(
    train_manifest=self.cfg["train_manifest"],
    val_manifest=self.cfg["val_manifest"],
    processor=self.model.processor,
    batch_size=cfg["finetune"]["batch_size"],
    num_workers=cfg["finetune"].get("num_workers", 2),
)
```

### 3) Gradient accumulation (유효 배치 16)

`train/finetune.py`:

```python
accum_steps = self.cfg["finetune"].get("gradient_accumulation_steps", 1)
# ...
loss = output.loss / accum_steps
# ...
if (step + 1) % accum_steps == 0:
    self.scaler.step(self.optimizer)
    self.scheduler.step()
    self.global_step += 1
    if self.global_step % self.cfg["finetune"]["eval_steps"] == 0:
        val_wer = self._validate()
        if val_wer < self.best_val_wer:
            self.best_val_wer = val_wer
            self.model.save(str(self.output_dir / "best"))
```

### 4) REF / HYP → WER

`train/finetune.py` → `evaluation/metrics.py`:

```python
# REF = labels decode, HYP = generate decode
metrics = compute_wer_cer(all_refs, all_hyps)
return metrics["wer"]
```

---

## baseline WER 측정 (발표에 개선폭 넣을 때)

서버에서 (경로는 환경에 맞게 수정):

```cmd
python -m evaluation.run_baselines ^
  --split_dir C:\TTT-data\processed\elderly_command_split ^
  --finetuned_model C:\TTT-data\checkpoints\elderly_command\best ^
  --output_dir C:\Users\dns-server2\TTT-Dialect\evaluation\results
```

결과: `evaluation/results/b0_baseline.csv`, `b1_finetuned.csv`, `improvement_summary.json`

---

## 발표 슬라이드용 한 줄

> AI Hub **노인 명령어** 36만 train / 27.5만 val → Whisper-small **2 epoch**, batch **4×4=16** → Val WER **13.4% → 10.9% (best)**
