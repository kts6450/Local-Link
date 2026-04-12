"""
패스트푸드·카페 음성 주문 키오스크 데모
======================================
노인·방언 화자가 실제로 사용할 수 있는 키오스크 UX를 구현합니다.

    - 음성 입력 → B0(기본) / B1(파인튜닝) / TTT(개인화) 3단계 비교 패널
    - 오인식 2회 이상 시 터치 입력 자동 Fallback
    - 키오스크 TTS 안내 (gTTS)

실행:
    streamlit run app/kiosk.py
"""

import io
import sys
import os
import uuid
import random

import numpy as np
import streamlit as st
import soundfile as sf
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 선택적 의존성 ──────────────────────────────────────────────
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

try:
    from audiorecorder import audiorecorder
    HAS_AUDIORECORDER = True
except ImportError:
    HAS_AUDIORECORDER = False

from models.base_whisper import KoreanWhisperModel
from models.ttt_adapter import TTTAdapter, UserProfile

# ══════════════════════════════════════════════════════════════
# 설정
# ══════════════════════════════════════════════════════════════
SAMPLE_RATE       = 16_000
PROFILE_DIR       = "./data/user_profiles"
B0_CHECKPOINT     = "openai/whisper-small"      # 기본 Whisper (파인튜닝 없음)
B1_CHECKPOINT     = "./checkpoints/finetune/best"  # 방언·노인 파인튜닝 모델
FALLBACK_THRESHOLD = 2   # 연속 오인식 N회 이상 → 터치 Fallback 자동 활성화

# ══════════════════════════════════════════════════════════════
# 메뉴 데이터
# ══════════════════════════════════════════════════════════════
MENU: dict[str, list[dict]] = {
    "음료": [
        {"name": "아메리카노",  "price": 4_500, "emoji": "☕",
         "keywords": ["아메리카노", "아메리", "아메"]},
        {"name": "카페라떼",    "price": 5_000, "emoji": "🥛",
         "keywords": ["라떼", "카페라떼", "라뗴", "카페 라떼"]},
        {"name": "녹차라떼",    "price": 5_500, "emoji": "🍵",
         "keywords": ["녹차", "녹차라떼", "녹차 라떼"]},
        {"name": "유자차",      "price": 5_000, "emoji": "🍋",
         "keywords": ["유자", "유자차"]},
        {"name": "쌍화차",      "price": 5_000, "emoji": "🌿",
         "keywords": ["쌍화", "쌍화차"]},
        {"name": "식혜",        "price": 4_500, "emoji": "🥤",
         "keywords": ["식혜", "식혀"]},
    ],
    "식사": [
        {"name": "김치찌개",    "price": 8_000, "emoji": "🍲",
         "keywords": ["김치찌개", "김치 찌개", "김치"]},
        {"name": "비빔밥",      "price": 9_000, "emoji": "🥗",
         "keywords": ["비빔밥", "비빔 밥", "비빔"]},
        {"name": "순두부찌개",  "price": 8_500, "emoji": "🥘",
         "keywords": ["순두부", "순두부찌개", "순두부 찌개"]},
        {"name": "된장찌개",    "price": 8_000, "emoji": "🍜",
         "keywords": ["된장", "된장찌개", "된장 찌개"]},
    ],
    "빵·간식": [
        {"name": "토스트",      "price": 4_000, "emoji": "🍞",
         "keywords": ["토스트"]},
        {"name": "도넛",        "price": 3_000, "emoji": "🍩",
         "keywords": ["도넛", "도나스", "도너츠"]},
        {"name": "샌드위치",    "price": 5_500, "emoji": "🥪",
         "keywords": ["샌드위치", "샌드", "샌드 위치"]},
    ],
}

QUANTITY_MAP: dict[str, int] = {
    "하나": 1, "한": 1, "한개": 1, "일개": 1,
    "둘": 2, "두": 2, "두개": 2, "이개": 2,
    "셋": 3, "세": 3, "세개": 3, "삼개": 3,
    "넷": 4, "네": 4, "네개": 4, "사개": 4,
    "다섯": 5, "오개": 5,
}
CONFIRM_KEYWORDS = ["주문", "결제", "확인", "완료", "이걸로", "이거로", "주문할게", "주문해", "다 됐"]
CANCEL_KEYWORDS  = ["취소", "지워", "빼줘", "빼", "처음", "다시", "아니", "없애"]


# ══════════════════════════════════════════════════════════════
# 의도 분석
# ══════════════════════════════════════════════════════════════
def parse_order_intent(text: str) -> dict:
    result: dict = {"action": "unknown", "item": None, "quantity": 1}
    for kw, qty in QUANTITY_MAP.items():
        if kw in text:
            result["quantity"] = qty
            break
    for kw in CONFIRM_KEYWORDS:
        if kw in text:
            result["action"] = "confirm"
            return result
    for kw in CANCEL_KEYWORDS:
        if kw in text:
            result["action"] = "cancel"
            return result
    all_items = [item for items in MENU.values() for item in items]
    for item in all_items:
        for kw in item["keywords"]:
            if kw in text:
                result["action"] = "add"
                result["item"] = item
                return result
    return result


# ══════════════════════════════════════════════════════════════
# TTS
# ══════════════════════════════════════════════════════════════
def tts_bytes(text: str) -> bytes | None:
    if not HAS_GTTS:
        return None
    try:
        buf = io.BytesIO()
        gTTS(text=text, lang="ko", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def play_tts(text: str) -> None:
    audio = tts_bytes(text)
    if audio:
        st.audio(audio, format="audio/mp3", autoplay=True)


# ══════════════════════════════════════════════════════════════
# 모델 로드 — B0(기본) + B1/TTT(파인튜닝+적응) 동시 로드
# ══════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="AI 음성 인식 모델 불러오는 중...")
def load_models():
    # B0: 항상 기본 Whisper (파인튜닝 없음)
    b0 = KoreanWhisperModel(B0_CHECKPOINT)
    b0.model.eval()

    # B1: 파인튜닝 모델 (없으면 B0와 동일)
    b1_path = B1_CHECKPOINT if Path(B1_CHECKPOINT).exists() else B0_CHECKPOINT
    b1 = KoreanWhisperModel(b1_path)
    b1.model.eval()

    adapter = TTTAdapter(
        base_model=b1,
        profile_dir=PROFILE_DIR,
        top_k_layers=2,
        lr=1e-4,
        adaptation_steps=30,
    )
    has_finetune = Path(B1_CHECKPOINT).exists()
    return b0, b1, adapter, has_finetune


# ══════════════════════════════════════════════════════════════
# 오디오 캡처
# ══════════════════════════════════════════════════════════════
def capture_audio(key: str) -> tuple[np.ndarray | None, bytes | None]:
    if HAS_AUDIORECORDER:
        try:
            clip = audiorecorder("🔴 말씀해 주세요", "⏹ 중지", key=key)
            if len(clip) == 0:
                return None, None
            audio_np = np.array(clip.get_array_of_samples()).astype(np.float32)
            audio_np /= np.iinfo(clip.array_type).max
            return audio_np, clip.export().read()
        except Exception:
            pass

    audio_file = st.audio_input("🎙️ 마이크로 말씀해 주세요", key=f"{key}_input")
    if audio_file is None:
        return None, None
    raw = audio_file.read()
    arr, sr = sf.read(io.BytesIO(raw), dtype="float32")
    if arr.ndim > 1:
        arr = arr.mean(axis=1)
    if sr != SAMPLE_RATE:
        import librosa
        arr = librosa.resample(arr, orig_sr=sr, target_sr=SAMPLE_RATE)
    return arr.astype(np.float32), raw


# ══════════════════════════════════════════════════════════════
# STT — B0 / B1 / TTT 세 가지 동시 추론
# ══════════════════════════════════════════════════════════════
def transcribe_all(
    audio_np: np.ndarray,
    b0: KoreanWhisperModel,
    b1: KoreanWhisperModel,
    adapter: TTTAdapter,
    user_id: str,
    profile,
    has_finetune: bool,
) -> dict[str, str]:
    """B0 / B1 / TTT 세 가지 인식 결과를 한 번에 반환"""
    feat_b0 = b0.processor.feature_extractor(
        audio_np, sampling_rate=SAMPLE_RATE, return_tensors="pt"
    ).input_features[0]
    feat_b1 = b1.processor.feature_extractor(
        audio_np, sampling_rate=SAMPLE_RATE, return_tensors="pt"
    ).input_features[0]

    text_b0 = b0.transcribe(feat_b0.unsqueeze(0))[0] or ""
    text_b1 = b1.transcribe(feat_b1.unsqueeze(0))[0] or ""

    if profile and profile.calibration_done:
        text_ttt = adapter.transcribe(user_id, feat_b1) or ""
    else:
        text_ttt = text_b1   # 캘리브레이션 전엔 B1과 동일

    return {
        "b0":  text_b0,
        "b1":  text_b1,
        "ttt": text_ttt,
        "has_finetune": has_finetune,
        "has_ttt": bool(profile and profile.calibration_done),
    }


# ══════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════
KIOSK_CSS = """
<style>
/* ── 전체 배경·폰트 ── */
html, body, [data-testid="stApp"] {
    font-size: 20px !important;
    background: #eef2ff !important;
}
[data-testid="collapsedControl"] { display: none !important; }

/* 모든 텍스트 기본 강제 흰 배경 + 진한 글씨 */
p, span, label, div { color: #111827; }

/* ── 헤더 ── */
.kiosk-header {
    background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
    color: white; text-align: center;
    padding: 1.5rem 2rem; border-radius: 16px;
    margin-bottom: 1.4rem;
    box-shadow: 0 4px 20px rgba(37,99,235,.35);
}
.kiosk-header h1 { font-size: 2.4rem; margin: 0; font-weight: 800; color: white !important; }
.kiosk-header p  { font-size: 1.2rem; margin: .3rem 0 0; opacity: .95; color: white !important; }

/* ── 음성 입력 영역 강조 ── */
[data-testid="stAudioInput"] {
    background: white !important;
    border: 3px solid #2563eb !important;
    border-radius: 14px !important;
    padding: .5rem !important;
}
/* 녹음 버튼 텍스트 */
[data-testid="stAudioInput"] * { color: #1e3a8a !important; }

/* ── 섹션 제목 ── */
h3 { font-size: 1.6rem !important; font-weight: 800 !important; color: #1e3a8a !important; }
h4 { font-size: 1.35rem !important; font-weight: 700 !important; color: #1e40af !important; }

/* ── 안내 캡션 ── */
[data-testid="stCaptionContainer"] p {
    font-size: 1.05rem !important;
    color: #374151 !important;
    font-weight: 500 !important;
}

/* ── B0/B1/TTT 비교 패널 ── */
.compare-wrap { display:flex; gap:.8rem; margin:.8rem 0; }
.compare-col  { flex:1; border-radius:14px; padding:1rem; text-align:center; min-height:100px; }
.compare-col.b0  { background:#f1f5f9; border:2px solid #94a3b8; }
.compare-col.b1  { background:#dbeafe; border:2px solid #3b82f6; }
.compare-col.ttt { background:#dcfce7; border:2px solid #22c55e; }
.compare-badge   { display:inline-block; font-size:.82rem; font-weight:700; padding:3px 12px; border-radius:20px; margin-bottom:.5rem; }
.badge-b0  { background:#475569; color:white; }
.badge-b1  { background:#1d4ed8; color:white; }
.badge-ttt { background:#15803d; color:white; }
.compare-text   { font-size:1.15rem; font-weight:700; color:#111827 !important; word-break:keep-all; line-height:1.4; }
.compare-result { margin-top:.4rem; font-size:1.3rem; }
.result-ok  { color:#15803d !important; }
.result-err { color:#dc2626 !important; }

/* ── Fallback 배너 ── */
.fallback-banner {
    background: linear-gradient(135deg,#fef3c7,#fde68a);
    border:2px solid #f59e0b; border-radius:14px;
    padding:1.1rem 1.5rem; margin:.8rem 0; text-align:center;
}
.fallback-banner p     { font-size:1.4rem !important; font-weight:800 !important; color:#92400e !important; margin:0; }
.fallback-banner small { font-size:1.1rem !important; color:#b45309 !important; }

/* ── 액션 결과 ── */
.action-ok  { background:#f0fdf4; color:#15803d !important; border:2px solid #86efac; border-radius:12px; padding:.8rem 1.2rem; font-size:1.3rem !important; font-weight:700; text-align:center; margin:.5rem 0; }
.action-err { background:#fef2f2; color:#b91c1c !important; border:2px solid #fca5a5; border-radius:12px; padding:.8rem 1.2rem; font-size:1.3rem !important; font-weight:700; text-align:center; margin:.5rem 0; }

/* ── 메뉴 카드 ── */
.menu-card {
    background: white; border-radius:16px; padding:1.1rem;
    text-align:center; box-shadow:0 3px 12px rgba(0,0,0,.10);
    border:2px solid #e2e8f0; margin-bottom:.8rem;
    transition: border-color .15s, transform .15s;
}
.menu-card:hover { border-color:#2563eb; transform:translateY(-2px); }
.m-emoji { font-size:3.2rem; display:block; margin-bottom:.4rem; }
.m-name  { font-size:1.5rem; font-weight:800; color:#111827 !important; }
.m-price { font-size:1.25rem; color:#1d4ed8 !important; font-weight:700; margin-top:.3rem; }

/* ── 담기 버튼 크게 ── */
div[data-testid="column"] button {
    font-size: 1.2rem !important;
    min-height: 56px !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
}

/* ── 장바구니 ── */
.cart-row {
    background:white; border-radius:12px;
    padding:1rem 1.3rem; margin-bottom:.6rem;
    display:flex; justify-content:space-between;
    align-items:center; font-size:1.2rem;
    box-shadow:0 2px 8px rgba(0,0,0,.08);
    color:#111827 !important;
}
.cart-total {
    background:#dbeafe; border-radius:14px;
    padding:1.2rem 1.5rem; font-size:1.8rem;
    font-weight:900; text-align:right;
    color:#1e3a8a !important; margin-top:.8rem;
    border:2px solid #93c5fd;
}

/* ── 완료 화면 ── */
.complete-wrap {
    text-align:center; padding:2.5rem 2rem;
    background:linear-gradient(135deg,#ecfdf5,#d1fae5);
    border-radius:20px; border:2px solid #6ee7b7;
}
.order-num { font-size:5.5rem; font-weight:900; color:#15803d !important; line-height:1; }

/* ── 단계바 ── */
[data-testid="stHorizontalBlock"] { margin-bottom:.5rem; }
</style>
"""


# ══════════════════════════════════════════════════════════════
# 단계 표시 바
# ══════════════════════════════════════════════════════════════
def render_steps(step: int) -> None:
    labels = ["메뉴 선택", "주문 확인", "주문 완료"]
    cols = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, labels)):
        n = i + 1
        if n < step:
            circle = '<div style="display:inline-flex;width:34px;height:34px;border-radius:50%;background:#059669;color:white;font-weight:700;font-size:1rem;justify-content:center;align-items:center">✓</div>'
            color, fw = "#059669", "400"
        elif n == step:
            circle = f'<div style="display:inline-flex;width:34px;height:34px;border-radius:50%;background:#2563eb;color:white;font-weight:700;font-size:1rem;justify-content:center;align-items:center">{n}</div>'
            color, fw = "#2563eb", "700"
        else:
            circle = f'<div style="display:inline-flex;width:34px;height:34px;border-radius:50%;background:#e2e8f0;color:#94a3b8;font-weight:700;font-size:1rem;justify-content:center;align-items:center">{n}</div>'
            color, fw = "#94a3b8", "400"
        col.markdown(
            f'<div style="text-align:center">{circle}<br/>'
            f'<span style="color:{color};font-size:.95rem;font-weight:{fw}">{label}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("<br/>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# B0 / B1 / TTT 비교 패널
# ══════════════════════════════════════════════════════════════
def render_compare_panel(results: dict) -> None:
    """B0 / B1 / TTT 3단 비교 카드"""
    b0_text  = results["b0"]  or "(인식 없음)"
    b1_text  = results["b1"]  or "(인식 없음)"
    ttt_text = results["ttt"] or "(인식 없음)"

    has_ft  = results["has_finetune"]
    has_ttt = results["has_ttt"]

    # B1이 B0보다 나은지 간단히 체크 (길이 또는 다른 결과)
    b1_better  = has_ft and b1_text != b0_text
    ttt_better = has_ttt and ttt_text != b1_text

    b0_icon  = "✅" if parse_order_intent(b0_text)["action"] != "unknown" else "❌"
    b1_icon  = "✅" if parse_order_intent(b1_text)["action"] != "unknown" else "❌"
    ttt_icon = "✅" if parse_order_intent(ttt_text)["action"] != "unknown" else "❌"

    b1_label  = "B1 방언·노인 파인튜닝" if has_ft  else "B1 (미학습)"
    ttt_label = "TTT ✨ 내 목소리 적응" if has_ttt else "TTT (캘리브레이션 전)"

    st.markdown(
        f'''<div class="compare-wrap">
          <div class="compare-col b0">
            <span class="compare-badge badge-b0">B0 기본 Whisper</span><br/>
            <div class="compare-text">"{b0_text}"</div>
            <div class="compare-result {'result-ok' if b0_icon=='✅' else 'result-err'}">{b0_icon}</div>
          </div>
          <div class="compare-col b1">
            <span class="compare-badge badge-b1">{b1_label}</span><br/>
            <div class="compare-text">"{b1_text}"</div>
            <div class="compare-result {'result-ok' if b1_icon=='✅' else 'result-err'}">{b1_icon}{"&nbsp;↑개선" if b1_better else ""}</div>
          </div>
          <div class="compare-col ttt">
            <span class="compare-badge badge-ttt">{ttt_label}</span><br/>
            <div class="compare-text">"{ttt_text}"</div>
            <div class="compare-result {'result-ok' if ttt_icon=='✅' else 'result-err'}">{ttt_icon}{"&nbsp;↑최적" if ttt_better else ""}</div>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════
# 터치 Fallback 패널 (연속 오인식 시 자동 표시)
# ══════════════════════════════════════════════════════════════
def render_touch_fallback() -> None:
    """오인식이 반복될 때 표시하는 터치 빠른선택 패널"""
    st.markdown(
        '<div class="fallback-banner">'
        '<p>🤚 음성 인식이 어려우신가요?</p>'
        '<small>아래 버튼을 눌러 직접 선택해 주세요</small>'
        '</div>',
        unsafe_allow_html=True,
    )
    play_tts("음성 인식이 어려우시면 아래 버튼을 눌러 선택해 주세요.")

    all_items = [item for items in MENU.values() for item in items]
    # 4열 그리드
    cols = st.columns(4)
    for i, item in enumerate(all_items):
        with cols[i % 4]:
            if st.button(
                f"{item['emoji']}\n{item['name']}\n{item['price']:,}원",
                key=f"fallback_{item['name']}",
                use_container_width=True,
            ):
                _add_to_cart(item, 1)
                st.session_state.voice_action_msg = (
                    f"{item['emoji']} {item['name']}을 담았습니다!"
                )
                st.session_state.voice_fails = 0   # Fallback 해제
                play_tts(f"{item['name']} 담았습니다.")
                st.rerun()


# ══════════════════════════════════════════════════════════════
# 화면 1: 메뉴 선택
# ══════════════════════════════════════════════════════════════
def screen_menu(b0, b1, adapter, has_finetune: bool) -> None:
    render_steps(1)

    col_main, col_cart = st.columns([2, 1], gap="large")

    # ── 오른쪽: 장바구니 ─────────────────────────────────────
    with col_cart:
        st.markdown("### 🛒 장바구니")
        cart = st.session_state.cart

        if not cart:
            st.markdown(
                '<div style="text-align:center;color:#9ca3af;font-size:1.2rem;padding:1.5rem 0">비어 있습니다</div>',
                unsafe_allow_html=True,
            )
        else:
            total = 0
            for idx, ci in enumerate(cart):
                sub = ci["price"] * ci["qty"]
                total += sub
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(
                        f'<div class="cart-row">'
                        f'<span>{ci["emoji"]} <b>{ci["name"]}</b><br/>'
                        f'<small style="color:#6b7280">{ci["qty"]}개 × {ci["price"]:,}원</small></span>'
                        f'<span style="font-weight:700">{sub:,}원</span></div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("✕", key=f"del_{idx}", use_container_width=True):
                        st.session_state.cart.pop(idx)
                        st.rerun()

            st.markdown(f'<div class="cart-total">합계 {total:,}원</div>', unsafe_allow_html=True)
            st.markdown("")
            if st.button("✅ 주문 확인하기", type="primary", use_container_width=True):
                st.session_state.kiosk_screen = "cart"
                st.rerun()
            if st.button("🗑️ 전체 취소", use_container_width=True):
                st.session_state.cart = []
                st.session_state.voice_action_msg = ""
                st.rerun()

    # ── 왼쪽: 음성 입력 + 비교 패널 ──────────────────────────
    with col_main:
        st.markdown("### 🎙️ 음성으로 주문하세요")
        st.caption("예시: '아메리카노 두 잔이요'  /  '김치찌개 주세요'  /  '주문할게요'")

        # ── 오인식 Fallback 자동 활성화 ──────────────────────
        if st.session_state.voice_fails >= FALLBACK_THRESHOLD:
            render_touch_fallback()
            st.divider()

        # ── 음성 입력 ─────────────────────────────────────────
        audio_np, _ = capture_audio(key=f"menu_{st.session_state.voice_key}")

        if audio_np is not None:
            with st.spinner("B0 / B1 / TTT 인식 중..."):
                results = transcribe_all(
                    audio_np, b0, b1, adapter,
                    st.session_state.user_id,
                    st.session_state.profile,
                    has_finetune,
                )
            st.session_state.last_compare = results
            _handle_voice(results["ttt"], b1, adapter)

        # ── 비교 패널 (직전 결과 유지) ────────────────────────
        if st.session_state.last_compare:
            render_compare_panel(st.session_state.last_compare)

        # ── 액션 결과 메시지 ─────────────────────────────────
        if st.session_state.voice_action_msg:
            is_ok = any(w in st.session_state.voice_action_msg
                        for w in ["담았", "취소", "장바구니"])
            cls = "action-ok" if is_ok else "action-err"
            st.markdown(
                f'<div class="{cls}">{st.session_state.voice_action_msg}</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── 일반 터치 메뉴 그리드 ────────────────────────────
        for category, items in MENU.items():
            st.markdown(f"#### {category}")
            cols = st.columns(min(len(items), 3))
            for i, item in enumerate(items):
                with cols[i % 3]:
                    st.markdown(
                        f'<div class="menu-card">'
                        f'<span class="m-emoji">{item["emoji"]}</span>'
                        f'<div class="m-name">{item["name"]}</div>'
                        f'<div class="m-price">{item["price"]:,}원</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("＋ 담기", key=f"add_{item['name']}", use_container_width=True):
                        _add_to_cart(item, 1)
                        st.session_state.voice_fails = 0
                        st.session_state.voice_action_msg = (
                            f"{item['emoji']} {item['name']} 담기 완료!"
                        )
                        play_tts(f"{item['name']} 담았습니다.")
                        st.rerun()


def _handle_voice(ttt_text: str, b1, adapter) -> None:
    """TTT 인식 결과로 의도 파악 → 세션 처리"""
    intent = parse_order_intent(ttt_text)

    if intent["action"] == "add" and intent["item"]:
        item, qty = intent["item"], intent["quantity"]
        _add_to_cart(item, qty)
        st.session_state.voice_action_msg = (
            f"{item['emoji']} {item['name']} {qty}개를 장바구니에 담았습니다!"
        )
        st.session_state.voice_fails = 0
        play_tts(f"{item['name']} {qty}개 담았습니다.")

    elif intent["action"] == "confirm":
        if st.session_state.cart:
            st.session_state.voice_fails = 0
            st.session_state.kiosk_screen = "cart"
        else:
            st.session_state.voice_action_msg = "장바구니가 비어 있습니다. 먼저 메뉴를 선택해 주세요."
            st.session_state.voice_fails += 1
            play_tts("장바구니가 비어 있습니다.")

    elif intent["action"] == "cancel":
        if st.session_state.cart:
            removed = st.session_state.cart.pop()
            st.session_state.voice_action_msg = f"'{removed['name']}'을 취소했습니다."
            st.session_state.voice_fails = 0
            play_tts(f"{removed['name']} 취소했습니다.")
        else:
            st.session_state.voice_action_msg = "장바구니가 비어 있습니다."
            st.session_state.voice_fails += 1

    else:
        # 오인식 — 실패 카운터 증가
        st.session_state.voice_fails += 1
        st.session_state.voice_action_msg = (
            f"'{ttt_text}' — 인식이 어렵습니다. "
            f"다시 말씀하시거나 아래 버튼을 눌러주세요. "
            f"({st.session_state.voice_fails}/{FALLBACK_THRESHOLD})"
        )
        if st.session_state.voice_fails < FALLBACK_THRESHOLD:
            play_tts("다시 말씀해 주세요.")

    st.session_state.voice_key += 1
    st.rerun()


def _add_to_cart(item: dict, qty: int) -> None:
    for ci in st.session_state.cart:
        if ci["name"] == item["name"]:
            ci["qty"] += qty
            return
    st.session_state.cart.append(
        {"name": item["name"], "price": item["price"], "emoji": item["emoji"], "qty": qty}
    )


# ══════════════════════════════════════════════════════════════
# 화면 2: 주문 확인
# ══════════════════════════════════════════════════════════════
def screen_cart(b0, b1, adapter, has_finetune: bool) -> None:
    render_steps(2)
    st.markdown("### 주문 내역을 확인해 주세요")

    if not st.session_state.cart:
        st.warning("장바구니가 비어 있습니다.")
        if st.button("← 메뉴로 돌아가기"):
            st.session_state.kiosk_screen = "menu"
            st.rerun()
        return

    total = 0
    for ci in st.session_state.cart:
        sub = ci["price"] * ci["qty"]
        total += sub
        st.markdown(
            f'<div class="cart-row">'
            f'<span style="font-size:1.8rem">{ci["emoji"]}</span>'
            f'<span style="font-size:1.25rem;font-weight:600;flex:1;margin:0 1rem">{ci["name"]}</span>'
            f'<span style="color:#6b7280;font-size:1.1rem">{ci["qty"]}개</span>'
            f'<span style="font-size:1.25rem;font-weight:700;color:#1e40af;margin-left:1rem">{sub:,}원</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="cart-total">💳 최종 결제 금액: {total:,}원</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### 🎙️ 음성으로 확인하세요")
    st.caption("'결제할게요' 또는 '취소' 라고 말씀해 주세요")

    audio_np, _ = capture_audio(key=f"cart_{st.session_state.voice_key}")
    if audio_np is not None:
        with st.spinner("인식 중..."):
            results = transcribe_all(
                audio_np, b0, b1, adapter,
                st.session_state.user_id, st.session_state.profile, has_finetune,
            )
        render_compare_panel(results)
        intent = parse_order_intent(results["ttt"])
        st.session_state.voice_key += 1
        if intent["action"] == "confirm":
            _complete_order()
        elif intent["action"] == "cancel":
            st.session_state.kiosk_screen = "menu"
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 메뉴로 돌아가기", use_container_width=True):
            st.session_state.kiosk_screen = "menu"
            st.rerun()
    with col2:
        if st.button("💳 결제하기", type="primary", use_container_width=True):
            _complete_order()


def _complete_order() -> None:
    st.session_state.order_number = str(random.randint(1, 99)).zfill(2)
    st.session_state.kiosk_screen = "complete"
    st.rerun()


# ══════════════════════════════════════════════════════════════
# 화면 3: 주문 완료
# ══════════════════════════════════════════════════════════════
def screen_complete() -> None:
    render_steps(3)

    order_num = st.session_state.order_number
    total = sum(ci["price"] * ci["qty"] for ci in st.session_state.cart)

    play_tts(f"주문이 완료되었습니다. 대기 번호는 {order_num}번입니다. 잠시만 기다려 주세요.")

    st.markdown(
        f'''<div class="complete-wrap">
        <div style="font-size:5rem;line-height:1">✅</div>
        <div style="font-size:2rem;font-weight:800;color:#059669;margin:.6rem 0">
            주문이 완료되었습니다!</div>
        <div style="font-size:1.15rem;color:#374151;margin-top:1rem">대기 번호</div>
        <div class="order-num">{order_num}번</div>
        <div style="font-size:1.6rem;font-weight:700;color:#1e40af;margin-top:1rem">
            결제 금액: {total:,}원</div>
        <div style="font-size:1.1rem;color:#6b7280;margin-top:.6rem">
            번호가 호출되면 카운터에서 수령해 주세요</div>
        </div>''',
        unsafe_allow_html=True,
    )

    st.markdown("")
    with st.expander("📋 주문 내역 보기"):
        for ci in st.session_state.cart:
            st.markdown(
                f"- {ci['emoji']} **{ci['name']}** × {ci['qty']}개 "
                f"= **{ci['price']*ci['qty']:,}원**"
            )
        st.markdown(f"---\n**합계: {total:,}원**")

    st.markdown("")
    if st.button("🏠 처음으로 돌아가기", type="primary", use_container_width=True):
        st.session_state.cart = []
        st.session_state.last_text = ""
        st.session_state.voice_action_msg = ""
        st.session_state.last_compare = None
        st.session_state.voice_fails = 0
        st.session_state.kiosk_screen = "menu"
        st.rerun()


# ══════════════════════════════════════════════════════════════
# 메인 진입점
# ══════════════════════════════════════════════════════════════
def main() -> None:
    st.set_page_config(
        page_title="음성 주문 키오스크",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(KIOSK_CSS, unsafe_allow_html=True)

    b0, b1, adapter, has_finetune = load_models()

    defaults: dict = {
        "kiosk_screen":     "menu",
        "cart":             [],
        "user_id":          str(uuid.uuid4())[:8],
        "profile":          None,
        "voice_key":        0,
        "last_text":        "",
        "last_compare":     None,
        "voice_action_msg": "",
        "voice_fails":      0,
        "order_number":     "01",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if st.session_state.profile is None:
        st.session_state.profile = UserProfile.load(
            st.session_state.user_id, PROFILE_DIR
        )

    adapted = (
        st.session_state.profile is not None
        and st.session_state.profile.calibration_done
    )
    ft_tag = "🔵 B1 방언·노인 학습 적용" if has_finetune else "⚪ B0 기본 모델"
    ttt_tag = "🟢 TTT 개인화 적용" if adapted else "⏳ TTT 캘리브레이션 전"

    st.markdown(
        f'''<div class="kiosk-header">
        <h1>🎙️ 음성 주문 키오스크</h1>
        <p>{ft_tag} &nbsp;|&nbsp; {ttt_tag}</p>
        </div>''',
        unsafe_allow_html=True,
    )

    screen = st.session_state.kiosk_screen
    if screen == "menu":
        screen_menu(b0, b1, adapter, has_finetune)
    elif screen == "cart":
        screen_cart(b0, b1, adapter, has_finetune)
    elif screen == "complete":
        screen_complete()


if __name__ == "__main__":
    main()
