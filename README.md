# 로컬링크 Local Link

동네 장터 웹앱 — 판매자가 물건·숙박을 올리고, 구매자가 주문·모의 결제까지.

## 구조

```
├── webapp/
│   ├── backend/          FastAPI (마켓플레이스, 주문, 음성, 인증)
│   ├── frontend/         React + Vite + Tailwind
│   ├── docker/           nginx 설정
│   └── README.md         상세 실행·배포
├── .env.example          API 키·Whisper·마스터 계정
├── docker-compose.yml    Docker 풀스택
├── MODEL_SETUP.md        Whisper 체크포인트 연결
└── setup-env.sh          .env 초기 생성
```

## 빠른 시작

```bash
# 1) 환경 변수
./setup-env.sh
# .env 에 ANTHROPIC_API_KEY, OPENAI_API_KEY 입력

# 2) 백엔드
cd webapp/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload

# 3) 프론트 (다른 터미널)
cd webapp/frontend
npm install
npm run dev
```

브라우저: **http://localhost:5173**

## Docker

```bash
docker compose up --build
# → http://localhost:8080
```

개발용 핫 리로드: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`

## 음성 인식 (Whisper)

| `.env` | 동작 |
|--------|------|
| `TTT_ASR_BACKEND=dummy` | 가짜 인식 (모델 없음) |
| `TTT_ASR_BACKEND=` (비움) | Whisper 사용 |
| `TTT_MODEL_PATH=openai/whisper-small` | Hub 기본 모델 |
| `TTT_MODEL_PATH=/path/to/checkpoint` | 파인튜닝 체크포인트 |

코드: `webapp/backend/services/whisper_asr.py`  
상태 확인: `GET /api/voice/status`

## 역할

- **구매자** — 회원가입 → 쇼핑 · 장바구니 · 결제
- **판매자** — 물건 올리기 · 음성/AI · 주문 처리
- **마스터** — `.env` 마스터 계정 · 어드민

자세한 API·기능은 `webapp/README.md` 참고.
