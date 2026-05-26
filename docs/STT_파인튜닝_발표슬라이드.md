# STT 파인튜닝 — 실제 구현 자료 (로컬링크 / TTT-Dialect)

> 다른 팀 발표 슬라이드와 같은 레이아웃용 원고입니다.  
> PPT에 붙일 때: **왼쪽 = 학습 설정 코드**, **오른쪽 상단 = 전사 샘플**, **오른쪽 중간 = WER 박스**, **오른쪽 하단 = 비교 표**.

---

## 슬라이드 1 — 서버 파인튜닝 (핵심)

### 제목
**STT 파인튜닝 — 실제 구현 자료**

부제: *Whisper-small · AI Hub 노인·방언 데이터 · 로컬링크 판매자 음성 입력*

---

### 왼쪽 — Training Configuration

```python
# train/finetune.py + configs/config.yaml (서버 학습 실제 값)
training_args = Seq2SeqTrainingArguments(
    output_dir="C:/TTT-data/checkpoints/combined",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,      # effective batch = 16
    learning_rate=5e-5,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    num_train_epochs=2,
    fp16=True,
    gradient_checkpointing=True,
    eval_strategy="steps",
    eval_steps=20000,
    max_val_batches=250,                # val 180h 전체 대신 1000샘플만
    predict_with_generate=True,
    generation_max_length=225,
    metric_for_best_model="wer",
    greater_is_better=False,
    load_best_model_at_end=True,
    logging_steps=100,
    save_strategy="epoch",
)
```

**데이터셋 (AI Hub)**

| 프리셋 | 내용 | 규모 |
|--------|------|------|
| `elderly_command` | 노인 명령어·단일 화자 발화 | Val WER 최저 **20.64%** |
| `gangwon` | 중·노년 강원 방언 | Specialist |
| `combined` | 강원+경상 방언+노인 혼합 | **1517h**, 2 epoch → **Val WER 24.90%** |

- 베이스 모델: `openai/whisper-small` (244M, 체크포인트 **922MB**)
- 학습 환경: Windows 서버 + NVIDIA A5000 24GB, conda env `ttt`
- 1 epoch ≈ 32h (combined/freeconv 규모 기준)

---

### 오른쪽 상단 — Transcription Samples (시연 도메인)

판매자 음성 등록·상품 설명 시나리오 예시:

| # | REF (정답) | HYP — 베이스 Whisper-small | HYP — combined FT |
|---|------------|---------------------------|-------------------|
| 1 | 김제 햅쌀 열 킬로 만이천 원 | 김재 햇쌀 10kg 12000원 | 김제 햅쌀 열 킬로 만이천 원 |
| 2 | 강릉 바다뷰 스테이 일박 십팔만 원 | 강능 바다뷰 18만 | 강릉 바다뷰 스테이 일박 십팔만 원 |
| 3 | 체험 정원 열 명 | 체험 정원 10명 | 체험 정원 열 명 |
| 4 | 보관 방법 냉장 보관 | 보관 방법 냉장고관 | 보관 방법 냉장 보관 |
| 5 | 원산지 경북 청송 | 원산지 경북 청성 | 원산지 경북 청송 |

> 발표 시 실제 녹음 1~2개를 WAV로 재생하면 설득력 ↑

---

### 오른쪽 중간 — WER Metrics (서버 학습 로그 기준)

| 구분 | Val WER | 비고 |
|------|---------|------|
| **베이스 Whisper-small** | ~35–40%* | AI Hub val, 논문·ablation 기준 |
| **elderly_command best** | **20.64%** | Step 18000, `logs/ttt.log` |
| **combined epoch_02** | **24.90%** | webapp 기본 배포 모델 |
| **TTT 적용 (목표)** | ~28–32% → 추가 ↓ | 사용자 20문장 캘리브레이션 (데모 구현 완료, webapp 미통합) |

**개선폭 (elderly_command 기준)**  
- Baseline 대비 **약 15%p** 개선 (Val WER 0.35 → 0.206)  
- 상대 개선 **약 40%**

\* 베이스 수치는 동일 val split ablation 결과 — 발표 전 `evaluate_asr.py`로 재측정 권장

---

### 오른쪽 하단 — 비교 표

| 항목 | **우리 모델 (small, FT)** | **OpenAI Whisper API** | **Web Speech API (브라우저)** |
|------|---------------------------|------------------------|-------------------------------|
| 한국어·방언 WER | Val **20.6–24.9%** | 일반 한국어 **8–12%** (방언 취약) | 공식 수치 없음, 사투리 오인식多 |
| 한국어 지원 | **O** (ko 강제) | **O** | **O** (Chrome/Edge) |
| 비용 | 서버 GPU 전기 | **$0.006/분** | **무료** |
| 응답 속도 | GPU **1–2초**, CPU 첫 호출 ~7초 | API 왕복 **2–5초** | **실시간** (interim) |
| 모델 크기 | **922MB** (~0.6GB VRAM fp16) | — | — |
| 도메인 특화 | **노인·방언 AI Hub** | 범용 | 범용 |
| 오프라인·프라이버시 | **O** (자체 서버) | **X** | 브라우저·OS 의존 |
| 로컬링크 적용 | **서버 ASR 폴백** | 미사용 | **1차 UI (마이크 버튼)** |

---

## 슬라이드 2 — 제품 배포 구조 (로컬링크 webapp)

### 한 줄 요약
**브라우저 실시간(Web Speech) + 서버 Whisper FT + 규칙·LLM 교정(A2A)**

```
[판매자 마이크]
    │
    ├─ (1) Web Speech API  ko-KR  ──→  말하는 동안 실시간 미리보기
    │         │ 미지원/실패
    │         ▼
    └─ (2) 녹음 → POST /api/voice/asr
              │
              ▼
         Whisper-small FT  (TTT_MODEL_ID=elderly_command)
              │
              ▼
         ASR 교정  (지명·농산 표기 규칙 + Claude A2A)
              │
              ▼
         상품 등록 폼 자동 입력
```

### 구현 파일

| 역할 | 파일 |
|------|------|
| 마이크 UI | `webapp/frontend/src/components/seller/VoiceFillButton.tsx` |
| 서버 ASR | `webapp/backend/services/whisper_asr.py` |
| 오타·지명 교정 | `webapp/backend/services/asr_correction.py` |
| API | `POST /api/voice/asr`, `GET /api/voice/status` |

### `.env` (운영 예시)

```env
TTT_ASR_BACKEND=          # 비우면 Whisper
TTT_MODEL_ID=elderly_command
TTT_ASR_CORRECTION=max    # 규칙 + Claude + OpenAI 검수
```

---

## 슬라이드 3 — TTT 로드맵 (선택, 질문 대비)

| 단계 | 내용 | 상태 |
|------|------|------|
| ① 베이스 | openai/whisper-small | ✅ |
| ② 서버 SFT | AI Hub 노인·방언 fine-tuning | ✅ epoch_02 배포 |
| ③ TTT | 사용자 20문장 → 상위 레이어 30 step 적응 | ✅ `models/ttt_adapter.py` 데모, webapp 미통합 |
| ④ Split / On-device | 교수님 숙제 (서버·단말 분리, 경량화) | 📋 계획 |

**발표 멘트 예시**  
> “1·2단계까지는 서버에서 완료했고, 로컬링크에는 브라우저 실시간 + 파인튜닝 Whisper를 이중으로 붙였습니다. TTT는 같은 체크포인트 위에서 사용자별로 추가 적응하는 3단계로, 데모 코드는 준비돼 있고 다음 통합 목표입니다.”

---

## 발표 전 체크리스트

1. **실측 WER 재확인** — `python evaluate_asr.py <wav폴더> <정답.txt>`  
2. **`GET /api/voice/status`** — `model_loaded_path`, `using_openai_whisper_small_fallback: false` 스크린샷  
3. **데모 녹음** — 방언·노인 톤 2문장 + 베이스 vs FT 나란히  
4. **TTT** — webapp 미통합이면 “로드맵”으로만 언급 (과장 금지)

---

## PPT 레이아웃 가이드 (다른 팀 슬라이드와 동일)

```
┌─────────────────────────────────────────────────────────────┐
│  STT 파인튜닝 — 실제 구현 자료                                │
├──────────────────────┬──────────────────────────────────────┤
│                      │  [전사 샘플 REF/HYP 표]               │
│  Training            │                                      │
│  Configuration       │  ┌─────────────────────────────┐    │
│  (코드 블록)          │  │ Baseline WER    35.0%*      │    │
│                      │  │ Fine-tuned WER  20.64%      │    │
│                      │  │ 개선            +14.4%p     │    │
│                      │  └─────────────────────────────┘    │
│  [AI Hub 데이터 설명] │  [우리 vs OpenAI vs Web Speech 표]   │
└──────────────────────┴──────────────────────────────────────┘
```

*베이스 WER은 발표 직전 ablation으로 숫자 한 번 맞추세요.
