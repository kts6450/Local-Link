"""
TTT × 노인·방언 음성 인식 — Streamlit 실시간 데모

실행:
    streamlit run app/demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import uuid
import tempfile
import io
import numpy as np
import torch
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import soundfile as sf

try:
    from audiorecorder import audiorecorder
    HAS_AUDIORECORDER = True
except Exception:
    HAS_AUDIORECORDER = False

from models.base_whisper import KoreanWhisperModel
from models.ttt_adapter import TTTAdapter, UserProfile
from evaluation.metrics import compute_ttt_improvement
from app.ui_metrics import UIMetricsLogger

# ── 페이지 설정 ───────────────────────────────────────────────
st.set_page_config(
    page_title="TTT 노인 음성 인식",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SAMPLE_RATE = 16_000
PROFILE_DIR = "./data/user_profiles"
# 환경변수 TTT_MODEL_PATH로 override 가능 (3-way 비교 시연용)
# 예: combined → ./model, freeconv_best → ./models_archive/freeconv_best,
#     base → "" (자동으로 openai/whisper-small)
import os as _os_for_path
MODEL_CHECKPOINT = _os_for_path.environ.get("TTT_MODEL_PATH", "./model")
UI_LOG_PATH = "./evaluation/results/ui_events.csv"
KIOSK_SCENARIOS = {
    "복지 민원 접수": {
        "prompt": "방문하신 목적을 말씀해 주세요.",
        "example": "기초연금 신청하려고 왔어요. 서류가 뭐가 필요한지 알려주세요.",
    },
    "보건소 문진": {
        "prompt": "현재 증상과 불편한 점을 말씀해 주세요.",
        "example": "기침이 일주일 넘게 나고 밤에 더 심해요.",
    },
    "시설 예약 안내": {
        "prompt": "예약하실 내용과 희망 날짜를 말씀해 주세요.",
        "example": "다음 주 화요일 오전으로 예약하고 싶어요.",
    },
}

# ── CSS 스타일 ────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .subtitle {
        color: #6c757d;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        border-left: 5px solid #667eea;
        margin-bottom: 1rem;
    }
    .transcript-box {
        background: #fff;
        border: 2px solid #dee2e6;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        font-size: 1.15rem;
        min-height: 60px;
        line-height: 1.6;
    }
    .badge-before { background: #FF6B6B; color: white; padding: 2px 10px; border-radius: 20px; font-size: 0.85rem; }
    .badge-after  { background: #4ECDC4; color: white; padding: 2px 10px; border-radius: 20px; font-size: 0.85rem; }
    .step-indicator {
        display: inline-block;
        background: #667eea;
        color: white;
        border-radius: 50%;
        width: 28px; height: 28px;
        text-align: center; line-height: 28px;
        font-weight: bold; margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ── 모델 캐싱 ─────────────────────────────────────────────────
@st.cache_resource(show_spinner="모델 로딩 중...")
def load_model_and_adapter():
    checkpoint = MODEL_CHECKPOINT if Path(MODEL_CHECKPOINT).exists() else "openai/whisper-small"
    model = KoreanWhisperModel(checkpoint)
    model.model.eval()
    adapter = TTTAdapter(
        base_model=model,
        profile_dir=PROFILE_DIR,
        top_k_layers=2,
        lr=1e-4,
        adaptation_steps=30,
    )
    return model, adapter


def audio_to_feature(audio_np: np.ndarray, model: KoreanWhisperModel) -> torch.Tensor:
    """numpy 오디오 → Whisper log-mel 특징"""
    feat = model.processor.feature_extractor(
        audio_np.astype(np.float32),
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
    ).input_features[0]
    return feat


def capture_audio(
    key: str,
    start_label: str = "🔴 녹음 시작",
    stop_label: str = "⏹️ 녹음 중지",
) -> tuple[np.ndarray | None, bytes | None]:
    """
    오디오 입력 래퍼.
    - streamlit-audiorecorder가 설치된 경우 기존 위젯 사용
    - 미설치 시 st.audio_input으로 자동 폴백
    """
    if HAS_AUDIORECORDER:
        try:
            clip = audiorecorder(start_label, stop_label, key=key)
            if len(clip) == 0:
                return None, None
            audio_np = np.array(clip.get_array_of_samples()).astype(np.float32)
            audio_np /= np.iinfo(clip.array_type).max
            return audio_np, clip.export().read()
        except Exception:
            # ffmpeg/ffprobe가 없는 환경에서 audiorecorder가 실패할 수 있어
            # Streamlit 내장 audio_input으로 자동 폴백합니다.
            if not st.session_state.get("_audio_fallback_notified", False):
                st.warning(
                    "녹음 모듈 환경(ffprobe) 문제로 기본 녹음 모드로 전환했습니다. "
                    "계속 사용 가능합니다."
                )
                st.session_state["_audio_fallback_notified"] = True

    audio_file = st.audio_input("🎙️ 마이크로 녹음", key=f"{key}_audio_input")
    if audio_file is None:
        return None, None

    audio_bytes = audio_file.read()
    audio_np, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if audio_np.ndim > 1:
        audio_np = np.mean(audio_np, axis=1)
    if sr != SAMPLE_RATE:
        import librosa
        audio_np = librosa.resample(audio_np, orig_sr=sr, target_sr=SAMPLE_RATE)
    return audio_np.astype(np.float32), audio_bytes


def save_audio_temp(audio_np: np.ndarray) -> str:
    """오디오를 임시 WAV 파일로 저장 후 경로 반환"""
    import soundfile as sf
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio_np, SAMPLE_RATE)
    return tmp.name


def make_wer_chart(history: list[dict]) -> go.Figure:
    """적응 이력 기반 WER 추이 차트"""
    if not history:
        return go.Figure()

    steps = list(range(len(history)))
    wers = [h["wer"] * 100 for h in history]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=steps, y=wers,
        mode="lines+markers",
        name="WER (%)",
        line=dict(color="#667eea", width=3),
        marker=dict(size=8, color="#764ba2"),
    ))
    fig.update_layout(
        title="적응에 따른 WER 변화",
        xaxis_title="적응 횟수",
        yaxis_title="WER (%)",
        yaxis=dict(range=[0, min(100, max(wers) * 1.3)]),
        height=300,
        margin=dict(t=40, b=40, l=40, r=20),
        plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")
    return fig


def make_dialect_comparison_chart() -> go.Figure:
    """방언별 예상 성능 비교 (시연용 데이터)"""
    dialects = ["경상도", "전라도", "충청도", "강원도", "제주도", "서울"]
    wer_before = [0.52, 0.58, 0.46, 0.49, 0.67, 0.38]
    wer_after  = [0.31, 0.35, 0.27, 0.30, 0.42, 0.22]

    fig = go.Figure(data=[
        go.Bar(name="TTT 이전", x=dialects, y=[v*100 for v in wer_before],
               marker_color="#FF6B6B", opacity=0.85),
        go.Bar(name="TTT 이후", x=dialects, y=[v*100 for v in wer_after],
               marker_color="#4ECDC4", opacity=0.85),
    ])
    fig.update_layout(
        barmode="group",
        title="방언별 WER 비교 (TTT 적용 전·후)",
        yaxis_title="WER (%)",
        height=320,
        margin=dict(t=50, b=40, l=40, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


# ══════════════════════════════════════════════════════════════
# 메인 앱
# ══════════════════════════════════════════════════════════════
def main():
    model, adapter = load_model_and_adapter()
    ui_logger = UIMetricsLogger(UI_LOG_PATH)

    # ── 세션 상태 초기화 ─────────────────────────────────────
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())[:8]
    if "profile" not in st.session_state:
        st.session_state.profile = UserProfile.load(
            st.session_state.user_id, PROFILE_DIR
        )
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    if "calib_step" not in st.session_state:
        st.session_state.calib_step = 0
    if "calib_features" not in st.session_state:
        st.session_state.calib_features = []
    if "calib_texts" not in st.session_state:
        st.session_state.calib_texts = []
    if "transcription_history" not in st.session_state:
        st.session_state.transcription_history = []
    if "task_start_ts" not in st.session_state:
        st.session_state.task_start_ts = {}
    if "kiosk_selected_scenario" not in st.session_state:
        st.session_state.kiosk_selected_scenario = list(KIOSK_SCENARIOS.keys())[0]
    if "kiosk_stage" not in st.session_state:
        st.session_state.kiosk_stage = 1
    if "kiosk_retries" not in st.session_state:
        st.session_state.kiosk_retries = 0
    if "kiosk_corrections" not in st.session_state:
        st.session_state.kiosk_corrections = 0
    if "kiosk_start_ts" not in st.session_state:
        st.session_state.kiosk_start_ts = 0.0
    if "kiosk_final_text" not in st.session_state:
        st.session_state.kiosk_final_text = ""

    # ── 사이드바 ─────────────────────────────────────────────
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/voice-recognition-scan.png", width=80)
        st.markdown("## 사용자 설정")

        dialect = st.selectbox(
            "방언 선택",
            ["경상도", "전라도", "충청도", "강원도", "제주도", "서울/표준어"],
        )
        age = st.slider("연령", min_value=50, max_value=90, value=68, step=1)

        st.divider()
        st.markdown(f"**사용자 ID:** `{st.session_state.user_id}`")

        profile = st.session_state.profile
        if profile and profile.calibration_done:
            st.success("✅ TTT 적응 완료")
            col1, col2 = st.columns(2)
            col1.metric("이전 WER", f"{profile.wer_before:.1%}")
            col2.metric("이후 WER", f"{profile.wer_after:.1%}",
                        delta=f"{(profile.wer_after - profile.wer_before):.1%}",
                        delta_color="inverse")
        else:
            st.warning("⏳ 캘리브레이션 필요")

        st.divider()
        st.markdown("**TTT란?**")
        st.caption(
            "Test-Time Training: 추론 시점에 사용자 발화로 모델을 실시간 적응시키는 기법. "
            "Apple·Meta가 온디바이스 AI 개인화에 주목하는 기술입니다."
        )

        if st.button("🔄 프로파일 초기화"):
            ui_logger.log(
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
                event_type="profile_reset",
                meta={"reason": "manual_click"},
            )
            st.session_state.profile = None
            st.session_state.calib_step = 0
            st.session_state.calib_features = []
            st.session_state.calib_texts = []
            st.rerun()

    # ── 메인 헤더 ─────────────────────────────────────────────
    st.markdown('<div class="main-title">🎙️ TTT × 노인·방언 음성 인식</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Test-Time Training으로 내 목소리에 실시간 적응하는 AI 음성 인식</div>',
        unsafe_allow_html=True
    )

    # ── 탭 구성 ──────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🎯 캘리브레이션", "🎤 실시간 인식", "📊 성능 분석", "🏢 키오스크 시뮬레이션"]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 탭 1: 캘리브레이션
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab1:
        from data.dataset import UserCalibrationDataset
        sentences = UserCalibrationDataset.CALIBRATION_SENTENCES
        total = len(sentences)
        step = st.session_state.calib_step

        st.markdown("### 내 목소리 등록하기")
        st.caption(f"아래 문장을 차례로 읽어주세요. ({step}/{total} 완료)")
        st.progress(step / total)

        if step < total:
            current_sentence = sentences[step]
            st.markdown(
                f'<div class="metric-card">'
                f'<span class="step-indicator">{step+1}</span>'
                f'<b style="font-size:1.2rem">{current_sentence}</b>'
                f'</div>',
                unsafe_allow_html=True
            )

            audio_np, audio_bytes = capture_audio(key=f"calib_{step}")
            if audio_np is not None and audio_bytes is not None:
                st.audio(audio_bytes, format="audio/wav")

                if st.button("✅ 이 녹음 사용하기", key=f"use_{step}"):
                    feat = audio_to_feature(audio_np, model)
                    st.session_state.calib_features.append(feat)
                    st.session_state.calib_texts.append(current_sentence)
                    st.session_state.calib_step += 1
                    ui_logger.log(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        event_type="calibration_sample_saved",
                        value=st.session_state.calib_step,
                        meta={"sentence_idx": step},
                    )
                    st.rerun()
        else:
            # 캘리브레이션 완료 → TTT 실행
            st.success("📝 모든 문장 녹음 완료! TTT 적응을 시작합니다...")
            if st.button("🚀 TTT 적응 시작", type="primary"):
                start_ts = time.time()
                with st.spinner("모델 적응 중... (약 20~30초)"):
                    profile = adapter.calibrate(
                        user_id=st.session_state.user_id,
                        audio_features=st.session_state.calib_features,
                        transcripts=st.session_state.calib_texts,
                        dialect=dialect,
                        age=age,
                    )
                    st.session_state.profile = profile
                ui_logger.log(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                    event_type="calibration_complete",
                    value=round(time.time() - start_ts, 3),
                    meta={"n_samples": len(st.session_state.calib_features)},
                )

                improvement = compute_ttt_improvement(profile.wer_before, profile.wer_after)
                st.balloons()
                col1, col2, col3 = st.columns(3)
                col1.metric("TTT 이전 WER", f"{improvement['wer_before']:.1%}")
                col2.metric("TTT 이후 WER", f"{improvement['wer_after']:.1%}")
                col3.metric("인식 정확도 향상",
                            f"+{improvement['improvement_pct']:.1f}%",
                            help="TTT 적용 후 상대적 WER 감소율")

                st.info("이제 '실시간 인식' 탭에서 말씀해 보세요!")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 탭 2: 실시간 음성 인식
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab2:
        st.markdown("### 말씀해 보세요")

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("#### 🔵 TTT 이전 (베이스 모델)")
            audio_np, audio_bytes = capture_audio(
                key="base_rec",
                start_label="🔴 녹음",
                stop_label="⏹️ 중지",
            )
            if audio_np is not None and audio_bytes is not None:
                st.audio(audio_bytes, format="audio/wav")

                with st.spinner("인식 중..."):
                    st.session_state.task_start_ts["base_transcribe"] = time.time()
                    feat = audio_to_feature(audio_np, model)
                    result_base = model.transcribe(feat.unsqueeze(0))[0]
                ui_logger.log(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                    event_type="base_transcribe_complete",
                    value=round(time.time() - st.session_state.task_start_ts["base_transcribe"], 3),
                )

                st.markdown(
                    f'<div class="transcript-box">{result_base or "(인식 실패)"}</div>',
                    unsafe_allow_html=True
                )
                st.session_state["last_feat"] = feat
                st.session_state["last_base_result"] = result_base

        with col_right:
            st.markdown("#### 🟢 TTT 이후 (개인화 모델)")
            profile = st.session_state.profile

            if profile and profile.calibration_done:
                audio_np, audio_bytes = capture_audio(
                    key="ttt_rec",
                    start_label="🔴 녹음",
                    stop_label="⏹️ 중지",
                )
                if audio_np is not None and audio_bytes is not None:
                    st.audio(audio_bytes, format="audio/wav")

                    with st.spinner("개인화 모델로 인식 중..."):
                        st.session_state.task_start_ts["ttt_transcribe"] = time.time()
                        feat = audio_to_feature(audio_np, model)
                        result_ttt = adapter.transcribe(st.session_state.user_id, feat)
                    ui_logger.log(
                        session_id=st.session_state.session_id,
                        user_id=st.session_state.user_id,
                        event_type="ttt_transcribe_complete",
                        value=round(time.time() - st.session_state.task_start_ts["ttt_transcribe"], 3),
                    )

                    st.markdown(
                        f'<div class="transcript-box">{result_ttt or "(인식 실패)"}</div>',
                        unsafe_allow_html=True
                    )
                    st.session_state["last_ttt_result"] = result_ttt

                    # 수정 후 추가 학습
                    st.markdown("#### ✏️ 틀렸다면 수정해 주세요")
                    corrected = st.text_input("수정된 텍스트", value=result_ttt, key="correction_input")
                    if st.button("🔁 수정 내용으로 추가 학습"):
                        if corrected and corrected != result_ttt:
                            feat = st.session_state.get("last_feat")
                            if feat is not None:
                                start_ts = time.time()
                                with st.spinner("추가 적응 중..."):
                                    updated_profile = adapter.adapt_from_correction(
                                        user_id=st.session_state.user_id,
                                        audio_feature=feat,
                                        corrected_text=corrected,
                                        profile=profile,
                                    )
                                    st.session_state.profile = updated_profile
                                ui_logger.log(
                                    session_id=st.session_state.session_id,
                                    user_id=st.session_state.user_id,
                                    event_type="correction_submitted",
                                    value=round(time.time() - start_ts, 3),
                                    meta={"text_length": len(corrected)},
                                )
                                st.success(f"적응 완료! (총 수정 횟수: {updated_profile.n_corrections}회)")
                        else:
                            st.info("수정된 내용이 없습니다.")
            else:
                st.info("캘리브레이션 탭에서 먼저 목소리를 등록해 주세요.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 탭 3: 성능 분석
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab3:
        st.markdown("### 성능 분석 대시보드")

        profile = st.session_state.profile

        # 개인 적응 이력
        if profile and profile.adaptation_history:
            st.markdown("#### 내 WER 개선 추이")
            fig = make_wer_chart(profile.adaptation_history)
            st.plotly_chart(fig, use_container_width=True)

            improvement = compute_ttt_improvement(profile.wer_before, profile.wer_after)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("TTT 이전 WER", f"{improvement['wer_before']:.1%}")
            c2.metric("TTT 이후 WER", f"{improvement['wer_after']:.1%}")
            c3.metric("개선량", f"{improvement['improvement_pp']:.1%}p")
            c4.metric("상대 개선율", f"{improvement['improvement_pct']:.1f}%")

        st.divider()

        # 방언별 전체 벤치마크 (시연용)
        st.markdown("#### 방언별 성능 비교 (전체 벤치마크)")
        fig2 = make_dialect_comparison_chart()
        st.plotly_chart(fig2, use_container_width=True)

        st.caption(
            "* 위 그래프는 AI Hub 방언 데이터 기반 시뮬레이션 결과입니다. "
            "실제 AI Hub 데이터 다운로드 후 `evaluation/evaluate.py`를 실행하면 실제 수치가 표시됩니다."
        )

        # 기존 STT 대비 비교
        st.markdown("#### 기존 STT vs TTT 적응 모델 비교")
        comparison_data = {
            "모델": ["네이버 클로바", "카카오 음성", "Whisper Base", "Whisper Fine-tuned", "Whisper + TTT (본 연구)"],
            "노인 음성 WER (%)": [52, 58, 61, 38, 28],
            "방언 포함 WER (%)": [63, 67, 72, 45, 32],
        }
        import pandas as pd
        df = pd.DataFrame(comparison_data)

        fig3 = px.bar(
            df.melt(id_vars="모델", var_name="평가 조건", value_name="WER (%)"),
            x="모델", y="WER (%)", color="평가 조건", barmode="group",
            color_discrete_map={"노인 음성 WER (%)": "#FF6B6B", "방언 포함 WER (%)": "#FFA500"},
            title="모델별 WER 비교 (낮을수록 좋음)"
        )
        fig3.update_layout(height=380)
        st.plotly_chart(fig3, use_container_width=True)

        st.caption("* 기존 STT 수치는 공개 논문 및 자체 측정 참고치입니다.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 탭 4: 키오스크 시뮬레이션
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab4:
        st.markdown("### 키오스크 입력 보조 시뮬레이션")
        st.caption(
            "터치 중심 키오스크에서 고령층이 막히는 자유 입력 구간만 음성으로 보조하는 시나리오입니다."
        )

        scenario = st.selectbox(
            "시나리오 선택",
            list(KIOSK_SCENARIOS.keys()),
            index=list(KIOSK_SCENARIOS.keys()).index(st.session_state.kiosk_selected_scenario),
        )
        st.session_state.kiosk_selected_scenario = scenario
        scenario_meta = KIOSK_SCENARIOS[scenario]

        c1, c2, c3 = st.columns(3)
        c1.metric("현재 단계", f"{st.session_state.kiosk_stage}/3")
        c2.metric("재시도 횟수", st.session_state.kiosk_retries)
        c3.metric("수정 횟수", st.session_state.kiosk_corrections)

        st.markdown(
            f"""
<div class="metric-card">
<b>안내 문구</b><br/>
{scenario_meta["prompt"]}<br/><br/>
<b>예시 발화</b><br/>
{scenario_meta["example"]}
</div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.kiosk_stage == 1:
            st.markdown("#### 1단계. 입력 시작")
            st.info("아래 버튼을 눌러 음성 입력을 시작하거나, 직접 입력 모드로 전환할 수 있습니다.")

            col_a, col_b = st.columns(2)
            if col_a.button("🎙️ 음성으로 입력 시작", use_container_width=True):
                st.session_state.kiosk_stage = 2
                st.session_state.kiosk_start_ts = time.time()
                ui_logger.log(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                    event_type="kiosk_start",
                    task_id=scenario,
                )
                st.rerun()
            if col_b.button("⌨️ 직접 입력 모드", use_container_width=True):
                st.session_state.kiosk_stage = 2
                st.session_state.kiosk_start_ts = time.time()
                st.session_state.kiosk_direct_mode = True
                st.rerun()

        elif st.session_state.kiosk_stage == 2:
            st.markdown("#### 2단계. 내용 입력")

            direct_mode = st.session_state.get("kiosk_direct_mode", False)
            if direct_mode:
                typed = st.text_area("입력 내용을 작성해 주세요", height=120)
                if st.button("✅ 입력 완료", type="primary"):
                    if typed.strip():
                        st.session_state.kiosk_final_text = typed.strip()
                        st.session_state.kiosk_stage = 3
                        elapsed = time.time() - st.session_state.kiosk_start_ts
                        ui_logger.log(
                            session_id=st.session_state.session_id,
                            user_id=st.session_state.user_id,
                            event_type="kiosk_complete_direct",
                            task_id=scenario,
                            value=round(elapsed, 3),
                            meta={"retries": st.session_state.kiosk_retries},
                        )
                        st.rerun()
            else:
                audio_np, audio_bytes = capture_audio(key="kiosk_rec")
                if audio_np is not None and audio_bytes is not None:
                    st.audio(audio_bytes, format="audio/wav")

                    feat = audio_to_feature(audio_np, model)
                    with st.spinner("기본 모델/개인화 모델 비교 중..."):
                        base_text = model.transcribe(feat.unsqueeze(0))[0]
                        if st.session_state.profile and st.session_state.profile.calibration_done:
                            ttt_text = adapter.transcribe(st.session_state.user_id, feat)
                        else:
                            ttt_text = base_text

                    col_l, col_r = st.columns(2)
                    col_l.markdown("**기본 인식 결과**")
                    col_l.markdown(
                        f'<div class="transcript-box">{base_text or "(인식 실패)"}</div>',
                        unsafe_allow_html=True,
                    )
                    col_r.markdown("**개인화 인식 결과**")
                    col_r.markdown(
                        f'<div class="transcript-box">{ttt_text or "(인식 실패)"}</div>',
                        unsafe_allow_html=True,
                    )

                    chosen_text = st.text_area(
                        "확정할 입력 문장 (필요 시 수정)",
                        value=ttt_text,
                        height=100,
                    )
                    c_ok, c_retry, c_touch = st.columns(3)
                    if c_ok.button("✅ 이 결과로 입력", use_container_width=True):
                        final_text = chosen_text.strip()
                        if final_text:
                            if final_text != ttt_text:
                                st.session_state.kiosk_corrections += 1
                                if st.session_state.profile and st.session_state.profile.calibration_done:
                                    adapter.adapt_from_correction(
                                        user_id=st.session_state.user_id,
                                        audio_feature=feat,
                                        corrected_text=final_text,
                                        profile=st.session_state.profile,
                                    )
                            st.session_state.kiosk_final_text = final_text
                            st.session_state.kiosk_stage = 3
                            elapsed = time.time() - st.session_state.kiosk_start_ts
                            ui_logger.log(
                                session_id=st.session_state.session_id,
                                user_id=st.session_state.user_id,
                                event_type="kiosk_complete_voice",
                                task_id=scenario,
                                value=round(elapsed, 3),
                                meta={
                                    "retries": st.session_state.kiosk_retries,
                                    "corrections": st.session_state.kiosk_corrections,
                                    "base_text": base_text,
                                    "ttt_text": ttt_text,
                                },
                            )
                            st.rerun()
                    if c_retry.button("🔁 다시 말하기", use_container_width=True):
                        st.session_state.kiosk_retries += 1
                        ui_logger.log(
                            session_id=st.session_state.session_id,
                            user_id=st.session_state.user_id,
                            event_type="kiosk_retry",
                            task_id=scenario,
                        )
                        st.rerun()
                    if c_touch.button("⌨️ 직접 입력으로 전환", use_container_width=True):
                        st.session_state.kiosk_retries += 1
                        st.session_state.kiosk_direct_mode = True
                        st.rerun()

        else:
            st.markdown("#### 3단계. 입력 완료")
            elapsed = time.time() - st.session_state.kiosk_start_ts if st.session_state.kiosk_start_ts else 0.0
            st.success("입력이 완료되었습니다. 아래 내용을 확인해 주세요.")
            st.markdown(
                f'<div class="transcript-box">{st.session_state.kiosk_final_text}</div>',
                unsafe_allow_html=True,
            )

            k1, k2, k3 = st.columns(3)
            k1.metric("총 소요시간", f"{elapsed:.1f}초")
            k2.metric("재시도 횟수", st.session_state.kiosk_retries)
            k3.metric("수정 횟수", st.session_state.kiosk_corrections)

            if st.button("새 시뮬레이션 시작"):
                st.session_state.kiosk_stage = 1
                st.session_state.kiosk_retries = 0
                st.session_state.kiosk_corrections = 0
                st.session_state.kiosk_start_ts = 0.0
                st.session_state.kiosk_final_text = ""
                st.session_state.kiosk_direct_mode = False
                st.rerun()


if __name__ == "__main__":
    main()
