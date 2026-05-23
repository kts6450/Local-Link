# Whisper 체크포인트 연결 (로컬링크)

## 로컬에 있는 모델

| `TTT_MODEL_ID` | 설명 |
|----------------|------|
| `elderly_command` | AI Hub 노인 명령어 (최근 학습) |
| `gangwon` | 중·노년 방언 — 강원 |
| `combined` | 중·노년 방언 — 강원+경상 combined |

경로는 `models/inference/<id>` junction → `model/` · `models_archive/`.

## 1. `.env` (저장소 루트)

```env
TTT_ASR_BACKEND=
TTT_MODEL_ID=elderly_command
# TTT_MODEL_PATH=   # 직접 지정 시 프리셋보다 우선
```

모델 전환: `TTT_MODEL_ID=gangwon` 또는 `combined` → **백엔드 재시작**.

## 2. 로컬 uvicorn

```powershell
cd webapp\backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload
```

확인: http://localhost:8088/api/voice/status  
- `asr_is_dummy`: false  
- `model_loaded_path`: 체크포인트 절대 경로  
- `using_openai_whisper_small_fallback`: false  

## 3. Docker Compose

`.env`:

```env
TTT_ASR_BACKEND=
TTT_MODEL_ID=elderly_command
TTT_MODEL_DIR=./models/inference/elderly_command
TTT_MODEL_PATH=/models
```

```bash
docker compose up --build
```

## 4. UI만 빠르게 (모델 없음)

```env
TTT_ASR_BACKEND=dummy
```
