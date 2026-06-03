# docs — 기술·발표 자료

로컬링크 / TTT-Dialect 프로젝트의 **Git에 포함된 문서** 모음입니다.

## 목록

| 문서 | 용도 |
|------|------|
| [STT_파인튜닝_발표슬라이드.md](./STT_파인튜닝_발표슬라이드.md) | Whisper-small AI Hub 파인튜닝 — 학습 설정, WER, 전사 샘플, OpenAPI·Web Speech 비교표 (PPT 복붙용) |

## 우리 STT 한 줄 요약

- **베이스:** `openai/whisper-small`
- **학습 데이터:** AI Hub 노인 명령어 + 중·노년 방언 (강원·경상, combined ~1517h)
- **성능:** Val WER **20.6%** (elderly_command) ~ **24.9%** (combined)
- **앱 적용:** Web Speech 1차 → 서버 FT Whisper 2차 → 규칙·LLM ASR 교정 3차

운영·실행은 저장소 루트 [README.md](../README.md), Whisper 연결은 [MODEL_SETUP.md](../MODEL_SETUP.md) 를 보세요.
