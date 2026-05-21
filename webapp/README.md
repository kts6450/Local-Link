# 로컬링크 (Local Link) — 농어촌 특산품 직거래 마켓

어르신 **판매자**가 음성·화면으로 **상품·숙박**을 올리고, **구매자**가 같은 목록에서 담아 **가짜 결제(모의)**까지 이어지는 풀스택 데모입니다.  
음성 비서는 Claude API(`ANTHROPIC_API_KEY`)가 있을 때 전체 대화로 동작합니다. 키가 없어도 **판매자(seller) 모드**는 간단한 한국어 규칙(가격·지역·상품/숙박)으로 Zero UI 데모가 가능합니다.

## 구조

```
webapp/
├── backend/                 # FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── marketplace.py   # 브랜드, 목록 CRUD
│   │   ├── orders.py        # 주문 + POST …/mock-pay (가짜 결제)
│   │   └── voice.py         # /turn?mode=consumer|seller
│   ├── services/
│   │   ├── llm.py           # 구매/판매 프롬프트 + 슬롯 추출
│   │   ├── listings_store.py
│   │   ├── orders_store.py
│   │   ├── asr.py, tts.py
│   └── data/
│       ├── brand.json
│       ├── listings.seed.json
│       └── runtime/         # 기본 gitignore — 목록·주문 persistence
├── frontend/                # Vite + React Router
│   └── public/logo-local-link.png  # CI 로고
└── docker/ … Dockerfiles
```

## 로컬 실행

### 환경변수 (저장소 루트 `.env`)

```bash
# 저장소 루트에서 (최초 1회)
./setup-env.sh
# → .env 생성 후 편집기로 ANTHROPIC_API_KEY, OPENAI_API_KEY 붙여넣기
```

| 변수 | 용도 |
|------|------|
| `ANTHROPIC_API_KEY` | 음성 도우미, 판매 글 «설명 자동 작성» |
| `OPENAI_API_KEY` | 판매 글 «대표 사진 AI 생성» |
| `TTT_ASR_BACKEND=dummy` | Whisper 로딩 생략 (빠른 로컬 실행) |

백엔드는 `main.py`가 **저장소 루트**의 `.env`를 자동 로드합니다. 키를 바꾼 뒤에는 uvicorn을 한 번 재시작하세요.

학습한 Whisper 체크포인트만 넣어서 ASR을 돌리는 단계는 저장소 루트의 **[MODEL_SETUP.md](../MODEL_SETUP.md)** 에 정리해 두었습니다. `GET /api/voice/status`로 폴백·로컬 체크포인트 유효 여부를 확인할 수 있습니다.

판매 글 **AI 설명**은 `ANTHROPIC_API_KEY`가 없을 때도 간단한 고정 문장으로 채워집니다. **AI 대표 이미지**는 `OPENAI_API_KEY`(DALL·E 3)가 있어야 합니다.

### 백엔드

```bash
cd webapp/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload
```

### 프론트

```bash
cd webapp/frontend
npm install
npm run dev
```

http://localhost:5173 — `/api` 는 Vite 프록시 → 8088.

## Docker

저장소 루트:

```bash
docker compose up --build
```

- UI: http://localhost:8080  
- API: http://localhost:8088/health  

`webapp/backend/data/runtime` 에 목록·주문 JSON이 쌓입니다. 운영 시엔 볼륨 마운트 또는 DB로 교체하세요.

## 운영 배포 메모

1. **HTTPS** — 앞단 nginx/caddy 등에서 TLS 종료 후 `proxy_pass` 로 백엔드(8088)·정적(프론트) 연결.
2. **CORS** — 실제 도메인을 `CORS_EXTRA_ORIGINS=https://your.domain` 로 넘기거나, 같은 오리진으로 nginx만 노출.
3. **프로세스** — 개발은 uvicorn; 상용은 예:  
   `gunicorn main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8088` (의존성에 gunicorn 추가 후).
4. **결제** — 현재 `POST /api/orders/{id}/mock-pay` 는 항상 성공하는 **데모용**입니다. PG 연동 시 이 엔드포인트를 교체하세요.

## 시연 시나리오

- **구매자:** 쇼핑 탭에서 목록 확인 → 장바구니 → 이름·연락처 → 모의 결제. 또는 마이크로 물건 id·인원·연락처를 말해 한 번에 주문.
- **판매자:** 판매자 탭에서 마이크 또는 큰 입력 폼으로 상품/숙박 등록 → 목록에 즉시 반영.
