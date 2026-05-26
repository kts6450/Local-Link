import { useEffect, useRef } from "react";
import { clsx } from "clsx";

import { useConversation } from "../store/conversation";

type Props = {
  /** sheet: 하단 도크용 · peek: 한 줄 미리보기 */
  variant?: "default" | "sheet" | "peek";
  emptyHint?: string;
  className?: string;
};

export function ConversationView({
  variant = "default",
  emptyHint = "마이크를 누르고 편하게 말씀해 보세요. 짧게 말해도 괜찮아요.",
  className,
}: Props) {
  const { history, errorMsg } = useConversation();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (variant === "peek") return;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history, errorMsg, variant]);

  if (errorMsg) {
    return (
      <div
        className={clsx(
          "rounded-2xl border border-red-200 bg-red-50 p-4 flex gap-3 items-start",
          className
        )}
      >
        <span className="text-xl shrink-0" aria-hidden>
          ⚠️
        </span>
        <p className="text-red-800 text-sm leading-relaxed">{errorMsg}</p>
      </div>
    );
  }

  const turns = history.filter(
    (t, i) => !(i === 0 && t.role === "assistant" && history.length === 1)
  );

  if (turns.length === 0) {
    if (variant === "peek") return null;
    return (
      <div
        className={clsx(
          "rounded-2xl border border-dashed border-emerald-200/80 bg-gradient-to-br from-emerald-50/50 to-white p-6 text-center",
          className
        )}
      >
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-2xl mb-3">
          💬
        </span>
        <p className="text-slate-600 text-sm leading-relaxed">{emptyHint}</p>
      </div>
    );
  }

  if (variant === "peek") {
    const last = turns[turns.length - 1];
    const label = last.role === "user" ? "내 말" : "도우미";
    return (
      <p className={clsx("text-sm text-slate-600 truncate", className)}>
        <span className="font-semibold text-shop-tealDark">{label}</span>
        <span className="text-slate-400 mx-1.5">·</span>
        {last.content}
      </p>
    );
  }

  const isSheet = variant === "sheet";

  return (
    <div
      className={clsx(
        "flex flex-col gap-3 overflow-y-auto pr-0.5 scroll-smooth",
        isSheet ? "max-h-[min(42vh,360px)]" : "max-h-72",
        className
      )}
    >
      {turns.map((turn, idx) => {
        const isUser = turn.role === "user";
        return (
          <div
            key={idx}
            className={clsx("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}
          >
            <span
              className={clsx(
                "shrink-0 h-9 w-9 rounded-full flex items-center justify-center text-base shadow-sm",
                isUser
                  ? "bg-shop-teal text-white text-xs font-bold"
                  : "bg-white border border-emerald-200 text-lg"
              )}
              aria-hidden
            >
              {isUser ? "나" : "🌿"}
            </span>
            <div
              className={clsx(
                "min-w-0 max-w-[85%] rounded-2xl px-3.5 py-2.5 shadow-sm",
                isUser
                  ? "bg-shop-teal text-white rounded-tr-md"
                  : "bg-white border border-slate-100 rounded-tl-md"
              )}
            >
              <p
                className={clsx(
                  "text-[11px] font-semibold mb-1",
                  isUser ? "text-emerald-100" : "text-shop-tealDark"
                )}
              >
                {isUser ? "내 말" : "로컬링크 도우미"}
              </p>
              <p
                className={clsx(
                  "text-sm leading-relaxed whitespace-pre-wrap break-words",
                  isUser ? "text-white" : "text-slate-800"
                )}
              >
                {turn.content}
              </p>
            </div>
          </div>
        );
      })}
      <div ref={endRef} className="h-px shrink-0" aria-hidden />
    </div>
  );
}
