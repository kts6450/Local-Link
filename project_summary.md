# 🌿 로컬링크 (LocalLink) 프로젝트 최종 아키텍처 및 구현 요약서

본 문서는 농어촌 직거래 및 민박·체험 플랫폼인 **로컬링크(LocalLink)**의 전체 아키텍처와 핵심 AI 기술 구성, 그리고 최근 추가된 ML 학습용 데이터셋 구축 및 UI 성능 최적화 내역을 일목요연하게 정리한 공식 요약서입니다.

---

## 📂 1. 전체 디렉토리 구조 및 핵심 파일 역할

```
c:\final_project
├── webapp
│   ├── backend
│   │   ├── main.py                     # FastAPI 진입점 및 미들웨어 설정
│   │   ├── routers
│   │   │   ├── auth.py                 # 사용자 가입/로그인 및 마스터 권한 제어
│   │   │   ├── admin.py                # 회원, 상품 삭제 및 ML 용 데이터셋 ZIP/CSV 추출 API
│   │   │   └── voice.py                # Whisper ASR, A2A 교정 및 TTS 안내 API
│   │   ├── services
│   │   │   ├── asr.py                  # 오디오 PCM 디코딩 및 Whisper 로컬 모델 인프라
│   │   │   ├── asr_correction.py       # A2A 멀티 에이전트 오타/지명 순차 검증 파이프라인
│   │   │   ├── whisper_asr.py          # Whisper 모델 래퍼 및 로컬/더미 ASR 분기 처리
│   │   │   └── llm.py                  # Claude 기반 대화 처리 및 룰 기반 오프라인 엔진
│   │   └── db
│   │       ├── database.py             # SQLAlchemy DB 커넥션 및 세션 설정
│   │       └── models.py               # User, Listing, VoiceLog, OcrLog 테이블 스키마
│   └── frontend
│       └── src
│           ├── components
│           │   ├── seller
│           │   │   ├── VoiceFillButton.tsx   # 입력창 옆 작은 마이크 (실시간 인식 + 배경 저장)
│           │   │   └── VoiceChatSheet.tsx    # 대화식 등록 보조 드로어 컴포넌트
│           │   └── MicButton.tsx             # 중앙 하단 메인 마이크 컨트롤러
│           ├── hooks
│           │   └── useVoiceSession.ts        # 음성 비서와의 대화 세션 상태 관리 (1.1배속 재생)
│           └── pages
│               └── admin
│                   └── AdminPage.tsx         # 어드민 엑셀(CSV) 추출 및 일괄 압축 ZIP 연동
```

---

## 🎙️ 2. 핵심 AI 기술 및 대화형 파이프라인

로컬링크는 IT 기기에 서툰 어르신들을 배려하여 설계된 **Zero UI**를 제공하며, 이를 위해 복잡한 오타 교정 및 슬롯 수집 아키텍처를 가집니다.

### ① 음성 인식 및 지능형 교정 (ASR & A2A Correction)
1. **ASR (Whisper)**: 브라우저가 녹음하여 전송한 WAV 오디오 파일을 서버의 로컬 `openai/whisper-small` 또는 파인튜닝 체크포인트를 사용해 한글 텍스트로 풀어냅니다.
2. **A2A (Agent-to-Agent) 검증 체인**: 단순 오타나 유사음 지명 오인식(예: 값평 ➡️ 가평, 김재 ➡️ 김제)을 수정하기 위해 4단계 순차 에이전트 검증을 통과시킵니다.
   - **에이전트 A (Claude Corrector)**: 문맥 오타 교정 초안 생성
   - **에이전트 B (Claude Auditor)**: 초안의 과보정이나 누락 감사
   - **에이전트 C (OpenAI Verifier)**: 독립적인 3차 교차 검토
   - **에이전트 D (Gemini Verifier)**: 최종 4차 확인 및 교정 완료

### ② 대화형 폼 빌더 (Dialogue Agent & Slot Filling)
* [llm.py](file:///c:/final_project/webapp/backend/services/llm.py) 내의 대화 모델이 사용자가 이전에 입력해 둔 값(OCR 정보 등)을 기억하며 대화를 이끌어 나갑니다.
* 상품 종류(`listing_type`), 카테고리(`category`), 상품명(`title`), 가격(`price`), 정원(`stock`), 지역(`location`) 등의 필수 항목이 모두 채워지면 마지막 요약 확인 절차를 거친 뒤 쇼핑몰에 바로 등록합니다.

---

## 📊 3. 모델 학습용 데이터셋 관리 및 일괄 다운로드 시스템

어드민 페이지에서 실서비스를 통해 모인 판매자들의 실제 한국어 음성(WAV) 및 손글씨 메모 이미지(JPG)를 라벨링 데이터셋 패키지로 즉시 추출할 수 있는 기능을 탑재했습니다.

```
[ ZIP 파일 내부 구성 ]                     [ 학습용 매핑 엑셀 (CSV) ]
├── voice_logs_all.zip                  ├── voice_logs_all.csv
│   ├── voice_user1_2026_05_27_log1.wav ──────> 매핑명 컬럼값과 파일명이 100% 일치
│   └── voice_user2_2026_05_27_log2.wav 
└── ocr_logs_all.zip                    ├── ocr_logs_all.csv
    ├── ocr_user1_2026_05_27_log1_1.jpg ──────> 매핑명 컬럼값과 이미지명이 100% 일치
    └── ocr_user1_2026_05_27_log1_2.jpg
```

* **일괄 ZIP 다운로드**: 서버 표준 `zipfile`을 활용하여 수천 개의 오디오 및 이미지 데이터를 프론트엔드 오버헤드 없이 스트리밍 압축 파일로 다운로드합니다.
* **전체 데이터베이스 CSV 스트리밍**: 20개씩 끊어내는 페이지네이션의 제약 없이, 클릭 한 번에 데이터베이스 내의 모든 로그 행을 매핑 정보와 함께 UTF-8 BOM CSV 파일로 받아옵니다.
* **일치성 매핑 (Pairing)**: CSV의 `매핑명` 컬럼 값과 다운로드받은 ZIP 내부 파일 이름이 완벽하게 동기화되어 머신러닝 분석용 Python 스크립트에서 파일명만으로 라벨 텍스트(ASR 원문, 보정문, OCR 텍스트 등)를 즉시 매핑시킬 수 있습니다.
* **개별 유저 라벨링**: 마스터 관리자가 특정 오디오나 이미지를 개별적으로 내려받을 때, 직접 입력한 분류 태그(`apple`, `korean_beef` 등)가 파일명 맨 앞에 라벨로 자동 부착되도록 팝업 다운로드 기능을 연동했습니다.

---

## ⚡ 4. 성능 최적화 구현 내역 (Tuning & Latency Fix)

### ① 입력창 옆 마이크 (작은 마이크) 반응 속도 최적화
* **기존 문제**: 작은 마이크로 한 단어만 말해도 ASR 결과 기록을 위해 4단계 에이전트(Sonnet) 교정이 순차로 돌아가면서 8초 이상의 지연 시간이 존재했고, 자동 침묵 감지가 되지 않아 두 번 클릭해야 했습니다.
* **개선 (0초 레이턴시)**:
  - **이중 경로(Dual-path)** 기술을 도입하여, 음성 입력 시 브라우저 내장 **Web Speech API를 동시에 켜서 실시간 텍스트 인식 및 침묵 자동 종료**를 즉각(0.1초) 지원하여 입력창을 채워줍니다.
  - 동시에 녹음된 실제 오디오 WAV 파일은 사용자의 제어권을 차단하지 않고 **백그라운드 비동기로 서버에 업로드**하므로, 관리자 페이지용 음성 로그는 0초의 체감 대기 속도로 온전히 기록됩니다.
  - 서버 단의 `/api/voice/asr` API는 무거운 LLM 교정을 생략하고 가벼운 규칙 보정(`rules_only=True`)만 타도록 분기하여 처리 지연 시간을 최소화했습니다.

### ② 음성 안내 재생 속도 조율 (1.1배속)
* 어르신에게 대답하는 음성 도우미의 답변 말 속도가 너무 느려 시연 및 입력 흐름이 답답해지는 것을 해소하기 위해, [useVoiceSession.ts](file:///c:/final_project/webapp/frontend/src/hooks/useVoiceSession.ts) 내의 `playTTS` 재생기를 수정했습니다.
* HTML5 Audio의 `playbackRate` 및 `defaultPlaybackRate`를 `1.1`로 튜닝하여, 웅얼거림이나 유치함을 배제하고 시연 및 조작 효율을 극대화한 **1.1배속 최적 속도**로 동작합니다.

### ③ 메인 페이지 전체(All) 탭 필터링 버그 해결
* **기존 문제**: 메인 페이지에서 '전체' 탭을 선택했음에도 불구하고, 내부 그리드 필터(`gridFilters`)가 특산품 카테고리(`kind: "product"`, `theme: "market"`)로 강제 고정되어 있어 다른 카테고리(스테이, 체험 등)가 노출되지 않는 버그가 있었습니다.
* **개선**:
  - [ShopPage.tsx](file:///c:/final_project/webapp/frontend/src/pages/ShopPage.tsx)에서 랜딩 뷰(`isLandingView`)일 때 강제 오버라이드하던 필터 로직을 제거하고, 전체 필터(`filters`) 상태가 온전히 적용되도록 수정하였습니다.
  - 이를 통해 '전체' 탭 클릭 시 농어촌 특산품, 스테이, 체험 상품 모두가 누락 없이 그리드에 정상적으로 렌더링되도록 조치하였습니다.
