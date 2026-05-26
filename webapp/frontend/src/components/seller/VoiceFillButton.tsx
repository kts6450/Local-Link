import { useEffect, useRef, useState } from "react";

import { api } from "../../lib/api";
import { startRecording } from "../../lib/recorder";

interface Props {
  /** 인식된 텍스트를 받는 콜백. 보통 `setX(t)` 처럼 상태 setter 를 그대로 넘긴다. */
  onText: (text: string) => void;
  /** 결과 텍스트를 다듬을 때 (예: 숫자만 뽑기). 미지정이면 원문 그대로. */
  postProcess?: (text: string) => string;
  /** 토너 컬러: emerald(기본)·amber·violet 등 tailwind 라벨 일부. */
  tone?: "emerald" | "amber" | "violet" | "slate";
  /** 더 큰 버튼이 필요할 때 lg, 기본은 sm. */
  size?: "sm" | "lg";
  /** 마이크 옆에 들릴 짧은 안내 문구 (스크린리더용·툴팁용). */
  hint?: string;
  /** 외부에서 비활성화 (다른 마이크가 녹음 중일 때 등). */
  disabled?: boolean;
  /** 한 번에 하나만 녹음되도록 부모가 잠금 토글 — 선택. */
  onActiveChange?: (active: boolean) => void;
}

const TONE_CLASSES: Record<NonNullable<Props["tone"]>, { base: string; recording: string }> = {
  emerald: {
    base: "bg-white border-emerald-300 text-emerald-700 hover:bg-emerald-50",
    recording: "bg-rose-500 border-rose-600 text-white animate-pulse",
  },
  amber: {
    base: "bg-white border-amber-300 text-amber-700 hover:bg-amber-50",
    recording: "bg-rose-500 border-rose-600 text-white animate-pulse",
  },
  violet: {
    base: "bg-white border-violet-300 text-violet-700 hover:bg-violet-50",
    recording: "bg-rose-500 border-rose-600 text-white animate-pulse",
  },
  slate: {
    base: "bg-white border-slate-300 text-slate-600 hover:bg-slate-50",
    recording: "bg-rose-500 border-rose-600 text-white animate-pulse",
  },
};

/**
 * 입력 칸 옆에 붙는 작은 마이크 버튼.
 * - 누르면 녹음 시작 → 다시 누르면 멈추고 ASR → onText 콜백으로 결과 전달.
 * - 8초가 지나면 자동 정지 (실수 방지).
 * - postProcess 로 숫자·단위만 추출하는 등 후가공 가능.
 */
export function VoiceFillButton({
  onText,
  postProcess,
  tone = "emerald",
  size = "sm",
  hint = "이 칸을 말로 채우기",
  disabled,
  onActiveChange,
}: Props) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const handleRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 컴포넌트 언마운트 시 안전하게 정리.
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      // 진행 중 녹음이 있으면 마이크 release 만 하고 결과는 버린다.
      void handleRef.current?.stop().catch(() => undefined);
    };
  }, []);

  const stopAndTranscribe = async () => {
    const handle = handleRef.current;
    handleRef.current = null;
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setRecording(false);
    onActiveChange?.(false);
    if (!handle) return;
    setBusy(true);
    try {
      const blob = await handle.stop();
      if (!blob || blob.size < 800) {
        // 너무 짧으면 무시 (실수 클릭 등)
        return;
      }
      const r = await api.transcribeAudio(blob);
      const text = (r?.text || r?.raw || "").trim();
      if (text) {
        onText(postProcess ? postProcess(text) : text);
      }
    } catch (err) {
      // 사용자에게 굳이 모달 띄우지 않고 콘솔에만 — 다시 누르면 된다.
      console.warn("[VoiceFillButton] ASR 실패", err);
    } finally {
      setBusy(false);
    }
  };

  const startNow = async () => {
    if (recording || busy || disabled) return;
    try {
      const handle = await startRecording();
      handleRef.current = handle;
      setRecording(true);
      onActiveChange?.(true);
      // 8초 자동 정지 — 어르신이 누른 줄 잊으셔도 안전하게.
      timeoutRef.current = setTimeout(() => {
        void stopAndTranscribe();
      }, 8000);
    } catch (err) {
      console.warn("[VoiceFillButton] 마이크 권한/시작 실패", err);
    }
  };

  const tones = TONE_CLASSES[tone];
  const sizeCls = size === "lg" ? "w-11 h-11 text-xl" : "w-9 h-9 text-base";

  return (
    <button
      type="button"
      aria-label={hint}
      title={hint}
      disabled={disabled || busy}
      onClick={() => (recording ? void stopAndTranscribe() : void startNow())}
      className={[
        "shrink-0 inline-flex items-center justify-center rounded-full border-2 transition-colors",
        sizeCls,
        recording ? tones.recording : tones.base,
        disabled || busy ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
      ].join(" ")}
    >
      {busy ? (
        <span
          className="block h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin"
          aria-hidden
        />
      ) : recording ? (
        <span aria-hidden>■</span>
      ) : (
        <span aria-hidden>🎤</span>
      )}
    </button>
  );
}
