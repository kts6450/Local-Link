# 📚 docs — 기술·발표 자료

평가·발표 준비용 문서입니다. GitHub 루트 [README.md](../README.md) 에서 프로젝트 전체 개요를 먼저 보세요.

---

## 문서 목록

| 문서 | 누가 보면 좋은지 | 내용 |
|------|------------------|------|
| **[STT_파인튜닝_발표슬라이드.md](./STT_파인튜닝_발표슬라이드.md)** | STT·ML 평가자 | 학습 설정, WER, 전사 샘플, OpenAI API·Web Speech 비교표 |

---

## STT 한 페이지 요약

```
openai/whisper-small
        ↓  AI Hub (노인 명령어 + 중·노년 방언, ~1517h)
   Fine-tuned checkpoint (922MB)
        ↓  로컬링크 webapp
   Web Speech → Whisper FT → ASR 교정 → 상품 폼
```

| 지표 | 값 |
|------|-----|
| elderly_command Val WER | **20.64%** |
| combined Val WER | **24.90%** |

운영 연결: [MODEL_SETUP.md](../MODEL_SETUP.md)
