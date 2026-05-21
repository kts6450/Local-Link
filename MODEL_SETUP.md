# 음성 ASR: 학습 모델만 넣으면 끝나게 하기

로컬링크 웹앱은 Hugging Face 형식의 **Whisper 체크포인트**를 `.env`의 `TTT_MODEL_PATH`로 지정하면 `webapp/backend/services/whisper_asr.py`에서 로드합니다.

## 1. 체크포인트에 꼭 있어야 하는 것

학습 결과물 폴더(**한 디렉터리 안에 모두**)에 최소 다음이 있어야 합니다.

- `config.json`
- `preprocessor_config.json`
- 모델 가중치 등(`model.safetensors` 또는 `pytorch_model.bin` 등 transformers가 읽는 파일)

`git lfs`로 받은 Hugging Face 저장소를 그대로 두어도 됩니다.

## 2. Docker Compose로 띄울 때

1. 호스트에 체크포인트를 풀어 둡니다. 예: `./models/inference/my-whisper-ko`
2. 프로젝트 루트 `.env` (또는 셸에서 export):

   ```bash
   # Whisper 쓰려면 dummy가 아니어야 함 (비우거나 주석)
   TTT_ASR_BACKEND=

   # 호스트 디렉터리 → 컨테이너 /models 로 마운트
   TTT_MODEL_DIR=./models/inference/my-whisper-ko

   # 컨테이너 안 경로 (compose 기본과 맞추려면 /models)
   TTT_MODEL_PATH=/models
   ```

3. `docker compose up --build`
4. 확인: `curl -s http://localhost:8088/api/voice/status | jq`

   - `asr_is_dummy`가 `false`
   - `local_whisper_checkpoint_ok`가 `true`(로컬 마운트가 유효할 때)
   - `using_openai_whisper_small_fallback`가 `true`면 **로컬 경로가 비었거나 필수 파일이 없어** `openai/whisper-small`로 폴백한 상태입니다.

## 3. 백엔드를 로컬에서 직접 띄울 때

`demo` 를 import path에 두고 있는 것과 동일하게 `TTT_MODEL_PATH`만 **호스트 절대/상대 경로**로 지정하면 됩니다.

```bash
export TTT_ASR_BACKEND=
export TTT_MODEL_PATH=/path/to/my-whisper-ko
# 또는 허브 id
export TTT_MODEL_PATH=openai/whisper-small
```

## 4. 모델 없이 UI만 볼 때

```bash
TTT_ASR_BACKEND=dummy
```

## 5. 참고 코드

- 경로 해석·폴백: `webapp/backend/services/whisper_asr.py`
- 상태 JSON: `GET /api/voice/status`
- Compose 마운트: `docker-compose.yml` 의 `TTT_MODEL_DIR` → `/models`
