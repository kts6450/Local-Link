import { clsx } from "clsx";

import { ConversationView } from "../ConversationView";
import { useConversation } from "../../store/conversation";

type Props = {
  open: boolean;
  onToggle: () => void;
  step: number;
};

/** 마이크 도크 바로 위 — 접으면 한 줄 미리보기, 펼치면 전체 대화 */
export function VoiceChatSheet({ open, onToggle, step }: Props) {
  const historyLen = useConversation((s) => s.history.length);
  const hasChat = historyLen > 1;

  const sheetBottom =
    "bottom-[calc(5.75rem+env(safe-area-inset-bottom,0px))] sm:bottom-[calc(6.25rem+env(safe-area-inset-bottom,0px))]";
  const sheetAlign =
    "mx-3 sm:mx-4 max-w-xl sm:max-w-2xl sm:ml-auto sm:mr-6 lg:mr-[max(1.5rem,calc(50vw-36rem))]";

  return (
    <>
      <div
        className={clsx(
          "fixed inset-x-0 z-40 transition-all duration-300 ease-out",
          sheetBottom,
          open
            ? "opacity-100 translate-y-0 pointer-events-auto"
            : "opacity-0 translate-y-4 pointer-events-none"
        )}
        aria-hidden={!open}
      >
        <div className={sheetAlign}>
          <div className="rounded-t-3xl border border-b-0 border-emerald-200/90 bg-gradient-to-b from-white via-white to-emerald-50/40 shadow-[0_-12px_40px_rgba(16,185,129,0.15)] overflow-hidden">
            <button
              type="button"
              onClick={onToggle}
              className="w-full flex justify-center pt-2.5 pb-1 hover:bg-slate-50/50"
              aria-label="대화 접기"
            >
              <span className="h-1 w-12 rounded-full bg-slate-300" />
            </button>
            <div className="flex items-center justify-between gap-3 px-4 pb-3 border-b border-emerald-100/80">
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-shop-teal to-emerald-600 text-white text-lg shadow-md">
                  🌿
                </span>
                <div className="min-w-0">
                  <p className="font-bold text-slate-900 text-sm">음성 도우미 대화</p>
                  <p className="text-[11px] text-slate-500">
                    {step}단계 · {Math.max(0, historyLen - 1)}개 메시지
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onToggle}
                className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                접기
              </button>
            </div>
            <div className="px-3 py-3 sm:px-4 sm:py-4 bg-gradient-to-b from-transparent to-emerald-50/20">
              <ConversationView variant="sheet" />
            </div>
          </div>
        </div>
      </div>

      {!open && hasChat && (
        <button
          type="button"
          onClick={onToggle}
          className={clsx(
            "fixed inset-x-0 z-40 text-left",
            sheetBottom,
            sheetAlign,
            "rounded-2xl border border-emerald-200 bg-white/95 backdrop-blur-md",
            "px-3.5 py-2.5 shadow-lg hover:border-shop-teal/50 hover:shadow-xl transition-all",
            "flex items-center gap-3 group"
          )}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-100 to-teal-50 text-base shadow-inner">
            💬
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold text-shop-tealDark tracking-wide mb-0.5">
              최근 대화 · 눌러서 전체 보기
            </p>
            <ConversationView variant="peek" />
          </div>
          <span
            className="shrink-0 flex h-7 w-7 items-center justify-center rounded-full bg-emerald-50 text-shop-tealDark text-xs group-hover:bg-shop-teal group-hover:text-white transition-colors"
            aria-hidden
          >
            ▲
          </span>
        </button>
      )}
    </>
  );
}
