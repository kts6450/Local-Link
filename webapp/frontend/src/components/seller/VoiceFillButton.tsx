import { useEffect, useRef, useState } from "react";

import { api } from "../../lib/api";
import { startRecording } from "../../lib/recorder";

interface Props {
  /** 최종 인식 텍스트 */
  onText: (text: string) => void;
  /** 말하는 동안 실시간 미리보기 (Web Speech API 사용 시) */
  onInterim?: (text: string) => void;
  postProcess?: (text: string) => string;
  tone?: "emerald" | "amber" | "violet" | "slate";
  size?: "sm" | "lg";
  hint?: string;
  disabled?: boolean;
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

type SpeechResultEvent = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [index: number]: { transcript?: string };
    };
  };
};

type SpeechErrorEvent = { error?: string };

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((ev: SpeechResultEvent) => void) | null;
  onerror: ((ev: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * 입력 칸 옆 마이크 — 말하는 동안 글자가 보이고(브라우저 음성인식), 끝나면 칸에 반영.
 * 브라우저 미지원 시 녹음 → 서버 Whisper ASR 폴백.
 */
export function VoiceFillButton({
  onText,
  onInterim,
  postProcess,
  tone = "emerald",
  size = "sm",
  hint = "이 칸을 말로 채우기",
  disabled,
  onActiveChange,
}: Props) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const handleRef = useRef<{ stop: () => Promise<Blob> } | null>(null);
  const speechRef = useRef<SpeechRecognitionLike | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gotFinalRef = useRef(false);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      speechRef.current?.abort();
      speechRef.current = null;
      void handleRef.current?.stop().catch(() => undefined);
    };
  }, []);

  const applyText = (raw: string, final = true) => {
    const text = (postProcess ? postProcess(raw) : raw).trim();
    if (!text) return;
    if (final) {
      onText(text);
    } else {
      onInterim?.(text);
    }
  };

  const finish = () => {
    setRecording(false);
    setBusy(false);
    onActiveChange?.(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const stopSpeech = () => {
    const rec = speechRef.current;
    speechRef.current = null;
    rec?.stop();
  };

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
    setStatus("인식 중…");
    try {
      const blob = await handle.stop();
      if (!blob || blob.size < 320) {
        setStatus("너무 짧아요. 다시 말해 주세요.");
        return;
      }
      const r = await api.transcribeAudio(blob, 45_000);
      const text = (r?.text || r?.raw || "").trim();
      if (text) {
        applyText(text, true);
        setStatus("반영했어요");
      } else {
        setStatus("잘 못 들었어요. 다시 말해 주세요.");
      }
    } catch (err) {
      console.warn("[VoiceFillButton] ASR 실패", err);
      setStatus("인식 실패. 다시 눌러 주세요.");
    } finally {
      setBusy(false);
      window.setTimeout(() => setStatus(null), 2800);
    }
  };

  const startWithSpeechApi = () => {
    const Ctor = getSpeechRecognition();
    if (!Ctor) return false;

    const rec = new Ctor();
    speechRef.current = rec;
    gotFinalRef.current = false;
    rec.lang = "ko-KR";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (ev) => {
      let interim = "";
      let finalText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        const t = r[0]?.transcript ?? "";
        if (r.isFinal) finalText += t;
        else interim += t;
      }
      if (interim.trim()) {
        setStatus("듣는 중…");
        applyText(interim, false);
      }
      if (finalText.trim()) {
        gotFinalRef.current = true;
        applyText(finalText, true);
        setStatus("반영했어요");
      }
    };

    rec.onerror = () => {
      if (!gotFinalRef.current) {
        setStatus("다시 말해 주세요");
      }
    };

    rec.onend = () => {
      speechRef.current = null;
      finish();
      if (!gotFinalRef.current) {
        window.setTimeout(() => setStatus(null), 2000);
      } else {
        window.setTimeout(() => setStatus(null), 1800);
      }
    };

    try {
      rec.start();
      setRecording(true);
      setStatus("듣는 중… 말씀하세요");
      onActiveChange?.(true);
      timeoutRef.current = setTimeout(() => {
        stopSpeech();
      }, 10_000);
      return true;
    } catch {
      speechRef.current = null;
      return false;
    }
  };

  const startWithRecorder = async () => {
    const handle = await startRecording();
    handleRef.current = handle;
    setRecording(true);
    setStatus("듣는 중… 다시 누르면 끝");
    onActiveChange?.(true);
    timeoutRef.current = setTimeout(() => {
      void stopAndTranscribe();
    }, 10_000);
  };

  const startNow = async () => {
    if (recording || busy || disabled) return;
    setStatus(null);
    if (startWithSpeechApi()) return;
    try {
      await startWithRecorder();
    } catch (err) {
      console.warn("[VoiceFillButton] 마이크 권한/시작 실패", err);
      setStatus("마이크 권한을 확인해 주세요");
      window.setTimeout(() => setStatus(null), 3000);
    }
  };

  const onClick = () => {
    if (recording) {
      if (speechRef.current) {
        stopSpeech();
      } else {
        void stopAndTranscribe();
      }
      return;
    }
    void startNow();
  };

  const tones = TONE_CLASSES[tone];
  const sizeCls = size === "lg" ? "w-11 h-11 text-xl" : "w-9 h-9 text-base";

  return (
    <div className="flex flex-col items-center gap-1 shrink-0">
      <button
        type="button"
        aria-label={hint}
        title={status ? `${hint} — ${status}` : hint}
        disabled={disabled || busy}
        onClick={onClick}
        className={[
          "inline-flex items-center justify-center rounded-full border-2 transition-colors",
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
      {status ? (
        <span className="text-[10px] text-slate-500 max-w-[4.5rem] text-center leading-tight">
          {status}
        </span>
      ) : null}
    </div>
  );
}
