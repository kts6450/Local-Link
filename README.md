<p align="center">
  <img src="webapp/frontend/public/logo-mark.svg" alt="로컬링크" width="72" />
</p>

<h1 align="center">로컬링크 · Local Link</h1>

<p align="center">
  <strong>농어촌 직거래 마켓플레이스</strong> + <strong>노인·방언 맞춤 음성 인식(STT)</strong><br/>
  어르신 판매자가 <em>말하고·찍고</em> 올리고, 구매자가 <em>담고·주문</em>하는 풀스택 데모
</p>

<p align="center">
  <a href="#eval-guide">시연 가이드</a> ·
  <a href="#features">기능</a> ·
  <a href="#stt">STT</a> ·
  <a href="#quickstart">실행</a> ·
  <a href="docs/STT_파인튜닝_발표슬라이드.md">발표 자료</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white" alt="React" />
  <img src="https://img.shields.io/badge/FastAPI-0.1xx-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Whisper--small-FT-412991?logo=openai&logoColor=white" alt="Whisper" />
  <img src="https://img.shields.io/badge/Claude-API-D97757" alt="Claude" />
  <img src="https://img.shields.io/badge/CLOVA-OCR-03C75A" alt="CLOVA" />
</p>

---

## 한눈에 보기

| | 로컬링크 (웹앱) | TTT-Dialect (연구) |
|---|----------------|-------------------|
| **목표** | 지역 특산·숙박·체험 **직거래 UX** | AI Hub **노인·방언 STT** 정확도 향상 |
| **사용자** | 구매자 / 공급자 / 운영자 | 연구·발표·추가 FT 실험 |
| **차별점** | 음성·OCR·AI **Zero-UI 등록**, 역할 분리, 유형별 주문 | Whisper-small **도메인 FT** + TTT 로드맵 |

> **평가 포인트:** 단순 쇼핑몰이 아니라, *어르신·사투리 환경*을 전제로 **음성→글자→상품 등록**까지 이어지는 **엔드투엔드 시스템**입니다.

---

## 목차

1. [평가·시연 가이드 (3분)](#eval-guide)
2. [핵심 기능](#features)
3. [시스템 구조](#architecture)
4. [역할별 화면](#roles)
5. [STT 연구 요약](#stt)
6. [기술 스택](#tech-stack)
7. [빠른 시작](#quickstart)
8. [문서·참고](#docs)

---

<a id="eval-guide"></a>

## 평가·시연 가이드 (3분)

아래 순서대로 보면 **기능 범위**와 **기술 깊이**를 빠르게 확인할 수 있습니다.

| 순서 | 화면 | 확인할 것 | 예상 시간 |
|:---:|------|-----------|:---------:|
| 1 | `http://localhost:5173` 쇼핑몰 | 특산 / 스테이 / 체험 필터, 상품 카드 | 30초 |
| 2 | **구매자** 가입 → 장바구니 → 모의 결제 | 주문·마이페이지 (유형별 문구) | 1분 |
| 3 | **공급자** 가입 → `/seller/dashboard` | 쇼핑몰 미노출, 대시보드·통계 | 30초 |
| 4 | **상품 등록** | 마이크 실시간 입력 · 노트 OCR · AI 설명·사진 | 1분 |
| 5 | API `GET /api/voice/status` | 로드된 Whisper 체크포인트·교정 파이프라인 | 20초 |

**공급자 계정**으로 로그인하면 쇼핑몰 대신 **판매 대시보드**로 이동합니다. (구매는 구매자 계정으로 따로 가입)

```bash
# 백엔드 기동 후 — 한 줄로 상태 확인
curl http://127.0.0.1:8088/api/voice/status
curl http://127.0.0.1:8088/api/marketplace/ai/capabilities
```

---

<a id="features"></a>

## 핵심 기능

### 판매자 — 말로·찍어서 등록 (Zero UI)

```
🎤 Web Speech (실시간)  →  실패 시  →  🎙️ Whisper FT (서버)
                                        ↓
                              📍 지명·농산어 규칙 + 🤖 A2A 교정
                                        ↓
                              📝 상품 폼 자동 채움
```

| 기능 | 설명 | 구현 |
|------|------|------|
| 음성 한 칸 채우기 | 말하는 동안 글자 표시, 끝나면 반영 | `VoiceFillButton.tsx` |
| 음성 대화 등록 | 판매 슬롯 추출·확인 | `SellerVoicePanel`, `/api/voice/turn` |
| 노트 OCR | 손글씨·메모 → CLOVA → Claude 구조화 | `note_ocr.py`, `SellerNoteOcrPanel` |
| AI 설명·사진 | Claude 문구 + OpenAI gpt-image | `listing_ai.py`, `llm.py` |
| SNS 홍보 | 인스타·페이스북용 초안 (본인 상품만) | `SellerSnsPage` |

### 구매자 — 쇼핑·주문

| 유형 | 예시 | 주문 UI |
|------|------|---------|
| 🌾 **특산** | 햅쌀, 사과, 수산물 | 배송·수량 |
| 🏡 **스테이** | 한옥·펜션 | 숙박 기간 |
| 🧺 **체험** | 갯벌·다도·서핑 | 참가 인원·일정 |

### 운영·품질

- **역할 분리:** `RequireConsumer` — 공급자는 판매 화면만
- **A2A 파이프라인:** ASR·슬롯·이미지 검수에 Claude + OpenAI + Gemini (키 있을 때)
- **셀러 대시보드:** KST 기준 오늘 주문·처리 대기 (master는 전체 집계)

---

<a id="architecture"></a>

## 시스템 구조

```mermaid
flowchart TB
  subgraph Client["브라우저 (React)"]
    Shop[쇼핑몰 / 장바구니]
    Seller[판매자 대시보드·등록]
    WS[Web Speech API]
  end

  subgraph API["FastAPI :8088"]
    Voice[/api/voice/*]
    Mkt[/api/marketplace/*]
    Orders[/api/orders/*]
  end

  subgraph AI["AI · ASR"]
    Whisper[Whisper-small FT<br/>elderly_command / gangwon / combined]
    Correct[ASR 교정 rules + A2A]
    LLM[Claude · OpenAI · Gemini]
    OCR[CLOVA OCR]
  end

  Shop --> Mkt
  Seller --> Voice
  Seller --> Mkt
  WS -->|폴백 녹음| Voice
  Voice --> Whisper --> Correct --> LLM
  Mkt --> LLM
  Mkt --> OCR
```

### 저장소 구조

```
TTT-Dialect/
├── webapp/
│   ├── backend/          # FastAPI, SQLite, 서비스 레이어
│   └── frontend/         # Vite + React + Tailwind
├── models/inference/     # Whisper FT 프리셋 (→ model/, models_archive/)
├── docs/                 # 발표·STT 기술 문서
├── MODEL_SETUP.md
├── .env.example
└── docker-compose.yml
```

---

<a id="roles"></a>

## 역할별 화면

| 역할 | 진입 | 주요 메뉴 |
|------|------|-----------|
| **구매자** | `/` 쇼핑몰 | 목록 · 장바구니 · 결제 · 마이페이지 |
| **공급자** | `/seller/dashboard` | 대시보드 · 상품 등록 · 주문·알림 · SNS 홍보 |
| **마스터** | `.env` 계정 | 위 + 어드민 · (선택) 쇼핑몰 |

<p align="center"><em>공급자 ↔ 구매자 계정은 분리 — 같은 사람이 사고팔려면 각각 가입</em></p>

---

<a id="stt"></a>

## STT 연구 요약

다른 팀의 **영어 호텔 STT**와 달리, 우리는 **한국어 노인·지역 방언**에 맞춘 파인튜닝입니다.

| 단계 | 내용 | 상태 |
|:---:|------|:----:|
| ① | `openai/whisper-small` 베이스 | ✅ |
| ② | AI Hub 노인·방언 **Supervised FT** (~1517h, 2 epoch) | ✅ 배포 |
| ③ | **TTT** 사용자별 캘리브레이션 | 🔬 데모 코드, webapp 미통합 |

### 성능 (Validation WER, 서버 학습 로그)

| 모델 | Val WER | 용도 |
|------|:-------:|------|
| 베이스 Whisper-small | ~35% | 비교 baseline |
| **elderly_command** | **20.64%** | 노인 명령어 specialist |
| **combined** epoch_02 | **24.90%** | 방언+노인 혼합, webapp 기본 |

**앱에서의 3단 ASR:** Web Speech → Whisper FT → 규칙·LLM 교정

📄 상세 표·학습 설정·발표용 레이아웃 → **[docs/STT_파인튜닝_발표슬라이드.md](docs/STT_파인튜닝_발표슬라이드.md)**

---

<a id="tech-stack"></a>

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | React 18, TypeScript, Vite, Tailwind, Zustand |
| Backend | FastAPI, SQLAlchemy, SQLite |
| ASR | Hugging Face Transformers, Whisper-small FT, librosa |
| LLM | Anthropic Claude, OpenAI, Google Gemini |
| OCR | Naver CLOVA OCR + Claude Vision 폴백 |
| TTS | 서버 MP3 (`/api/voice/tts`) |
| Infra | Docker Compose, nginx (선택) |

---

<a id="quickstart"></a>

## 빠른 시작

### 사전 요구

- Python 3.10+, Node 18+
- (선택) CUDA GPU — Whisper 로컬 추론 가속
- API 키: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` — 음성·AI 등록용  
  (없어도 UI·규칙 기반 데모 가능, `TTT_ASR_BACKEND=dummy` 로 ASR 생략 가능)

### 설치·실행

```bash
# 1) 환경 변수 (저장소 루트)
./setup-env.sh
# .env 편집

# 2) 백엔드
cd webapp/backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload

# 3) 프론트 (다른 터미널)
cd webapp/frontend && npm install && npm run dev
```

| 서비스 | URL |
|--------|-----|
| 웹 UI | http://localhost:5173 |
| API | http://localhost:8088 |
| 헬스 | http://localhost:8088/health |

### Whisper 모델 연결

```env
TTT_ASR_BACKEND=
TTT_MODEL_ID=elderly_command   # gangwon | combined
```

→ **[MODEL_SETUP.md](MODEL_SETUP.md)** · 확인: `GET /api/voice/status`

### Docker

```bash
docker compose up --build
# UI http://localhost:8080  ·  API :8088
```

---

<a id="docs"></a>

## 문서·참고

| 문서 | 대상 |
|------|------|
| [webapp/README.md](webapp/README.md) | API·시연·배포 상세 |
| [docs/STT_파인튜닝_발표슬라이드.md](docs/STT_파인튜닝_발표슬라이드.md) | STT 파인튜닝 발표·평가 |
| [docs/README.md](docs/README.md) | docs 인덱스 |
| [.env.example](.env.example) | 환경 변수 전체 목록 |

---

## 데이터·보안

- AI Hub 방언·노인 음성 — 연구·학습 목적, 데이터셋 약관 준수
- `.env`, API 키, `webapp/backend/data/runtime/` — **git 미포함**
- 결제 `mock-pay` — **데모용**, 실제 PG 미연동

---

<p align="center">
  <sub>로컬링크 — 동네 장터를 음성과 AI로 이어주는 졸업·캡스톤 프로젝트</sub>
</p>
