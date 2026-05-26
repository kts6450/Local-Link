import { clsx } from "clsx";

import { useVoiceSession } from "../hooks/useVoiceSession";
import { useConversation } from "../store/conversation";

/** 판매자 전용 마이크 (Zero UI) */
export function MicButton({ compact = false }: { compact?: boolean }) {
  const { toggle, phase } = useVoiceSession();
  const micLevel = useConversation((s) => s.micLevel);

  const label = {
    idle: "마이크를 눌러 말씀하세요",
    recording: "말씀 끝나면 다시 눌러 주세요",
    thinking: "듣고 있어요…",
    speaking: "안내 음성 재생 중이에요",
    error: "다시 시도",
  }[phase];

  const disabled = phase === "thinking" || phase === "speaking";

  const btnSize = compact ? "w-16 h-16 sm:w-[4.5rem] sm:h-[4.5rem]" : "w-40 h-40 sm:w-44 sm:h-44";
  const wrapSize = compact ? "w-16 h-16 sm:w-[4.5rem] sm:h-[4.5rem]" : "w-40 h-40 sm:w-44 sm:h-44";
  const iconSize = compact ? "text-3xl sm:text-4xl" : "text-6xl sm:text-7xl";

  return (
    <div className={clsx("flex flex-col items-center", compact ? "gap-2 py-0" : "gap-5 py-4")}>
      <div className={clsx("relative flex items-center justify-center", wrapSize)}>
        {phase === "idle" && (
          <span className="absolute inset-0 rounded-full bg-brand-green/20 blur-2xl animate-idle_glow" />
        )}
        {phase === "recording" && (
          <>
            <span className="absolute inset-0 rounded-full bg-hades-danger/30 animate-pulse_ring" />
            <span
              className="absolute inset-0 rounded-full bg-hades-danger/20 animate-pulse_ring"
              style={{ animationDelay: "0.5s" }}
            />
          </>
        )}

        <button
          type="button"
          onClick={toggle}
          disabled={disabled}
          className={clsx(
            "relative rounded-full flex items-center justify-center",
            btnSize,
            iconSize,
            "shadow-xl transition-all duration-300",
            phase === "recording" &&
              "bg-hades-danger text-white scale-105 ring-4 ring-hades-danger/30",
            phase === "thinking" &&
              "bg-slate-100 text-slate-500 cursor-not-allowed border border-slate-200",
            phase === "speaking" &&
              "bg-emerald-100 text-brand-green cursor-not-allowed ring-4 ring-emerald-200/80",
            (phase === "idle" || phase === "error") &&
              "bg-brand-green text-white hover:scale-[1.02] hover:bg-brand-greenLight shadow-lg shadow-emerald-900/15"
          )}
          style={
            phase === "recording"
              ? { transform: `scale(${1.05 + micLevel * 0.15})` }
              : undefined
          }
          aria-label={label}
        >
          {phase === "thinking" ? (
            <span className="animate-pulse">⋯</span>
          ) : phase === "speaking" ? (
            "🔊"
          ) : (
            "🎙️"
          )}
        </button>
      </div>

      {!compact ? (
        <div className="h-8 flex items-center gap-1.5 min-h-8">
          {phase === "recording" &&
            Array.from({ length: 9 }).map((_, i) => {
              const distFromCenter = Math.abs(i - 4) / 4;
              const factor = (1 - distFromCenter * 0.6) * (0.2 + micLevel * 1.6);
              const h = Math.max(0.15, Math.min(1, factor));
              return (
                <span
                  key={i}
                  className="w-2 bg-hades-danger rounded-full transition-all duration-75"
                  style={{
                    height: `${h * 2}rem`,
                  }}
                />
              );
            })}
          {phase === "speaking" &&
            Array.from({ length: 7 }).map((_, i) => (
              <span
                key={i}
                className="w-1.5 bg-brand-green rounded-full animate-wave"
                style={{
                  height: "1.5rem",
                  animationDelay: `${i * 0.1}s`,
                }}
              />
            ))}
        </div>
      ) : (
        <div className="h-4 flex items-center gap-1 min-h-4">
          {phase === "recording" &&
            Array.from({ length: 5 }).map((_, i) => {
              const factor = 0.2 + micLevel * 1.2;
              return (
                <span
                  key={i}
                  className="w-1 bg-hades-danger rounded-full transition-all duration-75"
                  style={{ height: `${Math.max(0.25, Math.min(1, factor))}rem` }}
                />
              );
            })}
        </div>
      )}

      <p
        className={clsx(
          "text-slate-600 text-center leading-snug",
          compact ? "text-xs sm:text-sm max-w-[12rem]" : "text-xl sm:text-2xl max-w-md"
        )}
      >
        {label}
      </p>
    </div>
  );
}
