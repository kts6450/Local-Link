# 파인튜닝 Whisper 체크포인트 (junction)

| 프리셋 (`TTT_MODEL_ID`) | 실제 위치 |
|-------------------------|-----------|
| `elderly_command` | `model/elderly_command/best` — 노인 명령어 |
| `gangwon` | `models_archive/gangwon/best` — 강원 방언 |
| `combined` | `models_archive/combined/best` — 강원+경상 combined |

`.env` 예:

```env
TTT_ASR_BACKEND=
TTT_MODEL_ID=elderly_command
```

모델 바꿀 때: `TTT_MODEL_ID=gangwon` 또는 `combined` 로 바꾸고 **uvicorn 재시작**.

Docker: `TTT_MODEL_DIR=./models/inference/elderly_command` + `TTT_MODEL_PATH=/models`

상세: [MODEL_SETUP.md](../../MODEL_SETUP.md)
