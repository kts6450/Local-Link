# 로컬링크 (Local Link) · TTT-Dialect

농어촌 **직거래 마켓플레이스** 웹앱과, **한국어 노인·방언 음성 인식(STT)** 연구를 한 저장소입니다.

- **로컬링크** — 판매자가 특산·스테이·체험을 올리고, 구매자가 장바구니·모의 결제까지 (어르신 UX 중심)
- **TTT-Dialect** — AI Hub 데이터로 `Whisper-small` 파인튜닝, Test-Time Training(TTT) 실험 코드

---

## 최근 업데이트 (2026-05)

| 영역 | 내용 |
|------|------|
| **역할 분리** | 공급자 = 판매 전용, 구매 = 구매자 계정 (`RequireConsumer`) |
| **상품 유형** | 특산 / 스테이 / 체험 탭·필터·주문·마이페이지 문구 분리 |
| **음성 입력** | Web Speech 실시간 미리보기 + 서버 Whisper FT 폴백 + ASR 교정(A2A) |
| **노트 OCR** | CLOVA OCR + Claude 폼 구조화 |
| **AI 등록** | Claude 설명, OpenAI gpt-image 대표 사진, SNS 홍보 초안 |
| **셀러 대시보드** | 본인 주문·상품 집계(KST), SNS는 본인 상품만 선택 |
| **문서** | [STT 파인튜닝 발표 원고](docs/STT_파인튜닝_발표슬라이드.md) |

---

## 저장소 구조

```
├── webapp/
│   ├── backend/              FastAPI — 마켓, 주문, 음성, OCR, 인증
│   └── frontend/             React + Vite + Tailwind
├── models/inference/         Whisper FT 프리셋 (junction → model/, models_archive/)
├── docs/                     발표·기술 메모
├── .env.example              API 키·Whisper·OCR·마스터 계정
├── MODEL_SETUP.md            파인튜닝 체크포인트 연결
├── docker-compose.yml        Docker 풀스택
└── setup-env.sh              .env 초기 생성
```

---

## 빠른 시작

### 1. 환경 변수

```bash
./setup-env.sh
# .env 편집 — ANTHROPIC_API_KEY, OPENAI_API_KEY, (선택) CLOVA_OCR_*
```

UI만 빠르게 보려면 `TTT_ASR_BACKEND=dummy` 로 Whisper 로딩을 건너뛸 수 있습니다.

### 2. 백엔드

```bash
cd webapp/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload
```

### 3. 프론트

```bash
cd webapp/frontend
npm install
npm run dev
```

브라우저: **http://localhost:5173** (`/api` → Vite 프록시 → 8088)

### 상태 확인

| URL | 용도 |
|-----|------|
| `GET /api/voice/status` | ASR 모델·교정·LLM 키 상태 |
| `GET /api/marketplace/ai/capabilities` | 설명·이미지·OCR 가능 여부 |

---

## 역할

| 역할 | 할 수 있는 것 |
|------|----------------|
| **구매자** | 쇼핑몰 · 장바구니 · 결제 · 마이페이지 |
| **공급자** | 대시보드 · 상품 등록(음성/OCR/AI) · 주문 처리 · SNS 홍보 — **쇼핑몰 접근 없음** |
| **마스터** | `.env` 계정 · 어드민 · (선택) 쇼핑몰·판매자 화면 모두 |

---

## 주요 기능

### 음성 (판매자 · 구매자)

1. **브라우저** — Web Speech API (`ko-KR`), 말하는 동안 칸에 실시간 반영  
2. **서버** — 파인튜닝 Whisper (`TTT_MODEL_ID`: `elderly_command` \| `gangwon` \| `combined`)  
3. **후처리** — 지명·농산 표기 규칙 + Claude/OpenAI/Gemini A2A 교정 (`TTT_ASR_CORRECTION=max`)

코드: `webapp/backend/services/whisper_asr.py`, `asr_correction.py`  
프론트: `VoiceFillButton.tsx`, `SellerVoicePanel.tsx`

### 노트 OCR (판매자)

손글씨·메모 사진 → CLOVA OCR → Claude가 상품 폼 항목 추출  
`LOCAL_LINK_OCR_PROVIDER=clova` (기본)

### AI 상품 등록

- 설명 자동 작성 (Claude)
- 대표 사진 (OpenAI `gpt-image-1.5` 등, 실패 시 Pollinations 폴백)
- SNS 홍보 문구 초안 (인스타·페이스북용, 쇼핑몰 미게시)

### 주문

- 유형별 UI: 특산(배송) / 스테이(숙박 기간) / 체험(참가·일정)
- 결제: `POST /api/orders/{id}/mock-pay` — **데모용 모의 결제**

---

## 음성 인식 (Whisper FT)

| `.env` | 동작 |
|--------|------|
| `TTT_ASR_BACKEND=dummy` | 가짜 인식 (모델 없음) |
| `TTT_ASR_BACKEND=` (비움) | Whisper 사용 |
| `TTT_MODEL_ID=elderly_command` | 노인 명령어 FT (권장) |
| `TTT_MODEL_ID=gangwon` / `combined` | 방언 specialist / 혼합 |

학습 요약 (AI Hub, `openai/whisper-small` 기준):

| 모델 | Val WER (서버 로그) |
|------|---------------------|
| elderly_command best | **20.64%** |
| combined epoch_02 | **24.90%** |

자세한 발표용 표·코드·비교: **[docs/STT_파인튜닝_발표슬라이드.md](docs/STT_파인튜닝_발표슬라이드.md)**  
체크포인트 경로·Docker: **[MODEL_SETUP.md](MODEL_SETUP.md)**

TTT(사용자별 캘리브레이션) 데모 코드는 있으나 **webapp에는 아직 미통합** — 로드맵 단계.

---

## Docker

```bash
docker compose up --build
# UI http://localhost:8080  ·  API http://localhost:8088/health
```

개발 핫 리로드: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`

---

## 문서

| 파일 | 설명 |
|------|------|
| [webapp/README.md](webapp/README.md) | API·시연 시나리오·배포 메모 |
| [MODEL_SETUP.md](MODEL_SETUP.md) | Whisper 체크포인트 `.env` 연결 |
| [.env.example](.env.example) | 전체 환경 변수 주석 |
| [docs/README.md](docs/README.md) | docs 폴더 안내 |
| [docs/STT_파인튜닝_발표슬라이드.md](docs/STT_파인튜닝_발표슬라이드.md) | STT 파인튜닝 발표 원고 |

---

## 라이선스·데이터

- AI Hub 방언·노인 음성 데이터는 연구·학습 목적 사용 (데이터셋 약관 준수)
- API 키·`.env`는 git에 올리지 않음
