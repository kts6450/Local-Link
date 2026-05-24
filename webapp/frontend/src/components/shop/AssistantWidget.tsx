import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../lib/api";
import { listingFallbackPhoto } from "../../lib/listingDisplay";
import type { AssistantCard, AssistantTurn } from "../../types";

const SUGGESTIONS = [
  "강원도 가족 스테이 추천해 줘",
  "5만원 이하 선물용 특산품",
  "주말 체험 클래스 인기 있는 거",
  "제주도 감귤 베스트",
];

const GREETING: AssistantTurn = {
  role: "assistant",
  content:
    "안녕하세요. 로컬링크 쇼핑 도우미예요. 찾으시는 상품·스테이·체험을 자연어로 말씀해 주세요. 평점 높은 베스트도 골라 드릴게요.",
};

export function AssistantWidget() {
  const [open, setOpen] = useState(false);
  const [pulse, setPulse] = useState(true);
  const [turns, setTurns] = useState<AssistantTurn[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    inputRef.current?.focus();
  }, [open, turns.length, busy]);

  async function send(text: string) {
    const user = text.trim();
    if (!user || busy) return;
    setPulse(false);
    setBusy(true);
    setInput("");
    const next: AssistantTurn[] = [...turns, { role: "user", content: user }];
    setTurns(next);
    try {
      const history = next
        .filter((t) => t.role === "user" || t.role === "assistant")
        .slice(-10)
        .map((t) => ({ role: t.role, content: t.content }));
      const r = await api.assistantChat({ user_text: user, history });
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: r.reply, cards: r.recommendations },
      ]);
    } catch (e) {
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "지금 도우미가 잠깐 쉬고 있어요. 잠시 후 다시 시도해 주세요. 검색창으로도 찾으실 수 있어요.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => {
            setOpen(true);
            setPulse(false);
          }}
          aria-label="쇼핑 도우미 열기"
          className="fixed bottom-6 right-6 sm:bottom-8 sm:right-8 z-40 group"
        >
          {pulse && (
            <>
              <span className="absolute inset-0 rounded-full bg-brand-ink/30 animate-ping" />
              <span className="absolute inset-0 rounded-full bg-brand-ink/20 animate-pulse" />
            </>
          )}
          <span className="relative flex h-16 w-16 sm:h-[68px] sm:w-[68px] items-center justify-center rounded-full bg-brand-ink text-white shadow-card-hover hover:scale-105 transition-transform">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
            </svg>
          </span>
          <span className="absolute -top-2 -right-2 inline-flex items-center justify-center min-w-[1.5rem] h-6 px-1.5 rounded-full bg-amber-400 text-brand-ink text-[11px] font-extrabold border-2 border-brand-cream shadow-soft">
            AI
          </span>
        </button>
      )}

      {open && (
        <div className="fixed bottom-6 right-6 sm:bottom-8 sm:right-8 z-40 w-[min(420px,calc(100vw-3rem))] h-[min(640px,calc(100vh-6rem))] flex flex-col rounded-[1.75rem] bg-white border border-brand-line shadow-card-hover overflow-hidden assistant-pop">
          <header className="flex items-center justify-between px-5 py-4 bg-brand-ink text-white">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/15">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
              </span>
              <div>
                <p className="font-bold text-base leading-tight">로컬링크 도우미</p>
                <p className="text-white/70 text-xs">실시간 추천 · 자연어 검색</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="닫기"
              className="rounded-full p-2 hover:bg-white/10 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </header>

          <div ref={scrollerRef} className="flex-1 overflow-y-auto px-5 py-4 bg-brand-cream/40 space-y-4">
            {turns.map((t, i) => (
              <div key={i} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] ${t.role === "user" ? "" : "space-y-3 w-full"}`}>
                  <p
                    className={
                      t.role === "user"
                        ? "rounded-2xl rounded-br-md bg-brand-ink text-white px-4 py-2.5 text-sm leading-relaxed shadow-soft"
                        : "rounded-2xl rounded-bl-md bg-white border border-brand-line/70 px-4 py-3 text-sm text-brand-ink leading-relaxed shadow-soft"
                    }
                  >
                    {t.content}
                  </p>
                  {t.role === "assistant" && t.cards && t.cards.length > 0 ? (
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {t.cards.map((c) => (
                        <AssistantCardItem key={c.id} card={c} />
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            ))}
            {busy ? (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md bg-white border border-brand-line/70 px-4 py-3 shadow-soft inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-brand-ink/60 animate-bounce" />
                  <span className="h-2 w-2 rounded-full bg-brand-ink/60 animate-bounce" style={{ animationDelay: "120ms" }} />
                  <span className="h-2 w-2 rounded-full bg-brand-ink/60 animate-bounce" style={{ animationDelay: "240ms" }} />
                </div>
              </div>
            ) : null}
          </div>

          {turns.length <= 1 && !busy ? (
            <div className="px-5 pt-2 pb-1 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void send(s)}
                  className="text-xs font-semibold rounded-full border border-brand-line bg-white px-3 py-1.5 text-brand-ink hover:bg-brand-warm transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          ) : null}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              void send(input);
            }}
            className="flex items-center gap-2 px-5 py-3 border-t border-brand-line bg-white"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="무엇을 찾고 계세요?"
              className="flex-1 rounded-full border border-brand-line bg-brand-cream/50 px-4 py-2.5 text-sm placeholder:text-hades-muted/70 focus:outline-none focus:ring-2 focus:ring-brand-ink/20 focus:bg-white transition-colors"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-brand-ink text-white disabled:opacity-40 hover:bg-brand-ink/90 active:scale-95 transition-all"
              aria-label="전송"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M22 2 11 13" />
                <path d="M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
            </button>
          </form>
        </div>
      )}
    </>
  );
}

function AssistantCardItem({ card }: { card: AssistantCard }) {
  const cat =
    card.kind === "lodging"
      ? "스테이"
      : card.category === "experience"
        ? "체험"
        : "특산";
  const fallback = listingFallbackPhoto({
    id: card.id,
    kind: card.kind,
    category: card.category,
  });
  return (
    <li className="rounded-2xl border border-brand-line bg-white overflow-hidden shadow-soft hover:shadow-card transition-shadow">
      <Link to={`/listing/${card.id}`} className="block no-underline text-inherit">
        <div className="relative aspect-[4/3] bg-brand-warm">
          <img
            src={card.cover_image_url || fallback}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
            onError={(e) => {
              const el = e.currentTarget;
              if (el.src !== fallback) el.src = fallback;
            }}
          />
          <span className="absolute top-2 left-2 rounded-full bg-white/95 px-2.5 py-1 text-[10px] font-bold text-brand-ink shadow-soft">
            {cat}
          </span>
        </div>
        <div className="p-3">
          <p className="font-bold text-sm text-brand-ink line-clamp-2 leading-snug">
            {card.title}
          </p>
          <div className="mt-1.5 flex items-center justify-between">
            <p className="text-sm font-bold text-brand-ink tabular-nums">
              {card.price.toLocaleString()}
              <span className="text-[10px] font-semibold text-hades-muted ml-0.5">원</span>
            </p>
            <span className="text-[11px] text-hades-muted tabular-nums inline-flex items-center gap-0.5">
              <span className="text-amber-500">★</span>
              <span className="font-bold text-brand-ink">
                {(card.rating || 0).toFixed(1)}
              </span>
              <span>({card.review_count})</span>
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}
