import { useEffect, useRef } from "react";

import { ConversationView } from "../ConversationView";
import { MicButton } from "../MicButton";
import { useSellerFormVoice } from "../../store/sellerFormVoice";
import { useConversation, WELCOME_SELLER } from "../../store/conversation";

import type { ListingTab } from "../../lib/listingTabs";

const VOICE_BY_STEP: Record<number, string[]> = {
  1: [
    "올해 햅쌀 십 키로, 만 이천 원",
    "바닷가 민박 하룻밤 삼만 원",
    "갯벌 체험 두 시간, 인당 이만 원",
  ],
  2: ["AI로 글 써줘", "소개 글 만들어 줘", "설명만 짧게"],
  3: ["대표 사진 만들어 줘", "바다에서 낚시하는 사진"],
  4: ["이대로 올려 주세요", "네, 올려요"],
};

const TAB_HINT: Record<ListingTab, string> = {
  product: "특산품·농산물",
  lodging: "민박·펜션·숙박",
  experience: "체험·투어·낚시",
};

/** 한 역할의 대화만 필터링해서 스크롤 표시 */
function ChatColumn({
  role,
  label,
  align,
}: {
  role: "assistant" | "user";
  label: string;
  align: "left" | "right";
}) {
  const history = useConversation((s) => s.history);
  const phase = useConversation((s) => s.phase);
  const endRef = useRef<HTMLDivElement>(null);

  const turns = history.filter((t) => t.role === role);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history]);

  const isAi = role === "assistant";

  return (
    <div className="flex-1 min-w-0 flex flex-col min-h-0">
      {/* 헤더 */}
      <div
        className={`flex items-center gap-1.5 px-2 pb-1.5 shrink-0 ${
          align === "right" ? "flex-row-reverse" : ""
        }`}
      >
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-white text-[11px] font-bold shadow-sm ${
            isAi
              ? "bg-gradient-to-br from-shop-teal to-emerald-600"
              : "bg-shop-teal"
          }`}
        >
          {isAi ? "🌿" : "나"}
        </span>
        <p
          className={`text-[11px] font-bold tracking-wide ${
            isAi ? "text-shop-tealDark" : "text-slate-700"
          }`}
        >
          {label}
        </p>
        {isAi && (phase === "thinking" || phase === "speaking") && (
          <span className="ml-1 flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="inline-block h-1.5 w-1.5 rounded-full bg-shop-teal animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
        )}
      </div>

      {/* 스크롤 대화 영역 */}
      <div
        className={`flex-1 overflow-y-auto rounded-2xl border px-2.5 py-2 space-y-2 scroll-smooth ${
          isAi
            ? "border-emerald-200 bg-emerald-50/60"
            : "border-slate-200 bg-slate-50/60"
        }`}
      >
        {turns.length === 0 ? (
          <p className="text-[11px] text-slate-400 text-center pt-2">
            {isAi ? "말씀하시면 바로 도와드려요" : "마이크를 눌러 말씀하세요"}
          </p>
        ) : (
          turns.map((t, idx) => (
            <div key={idx}>
              <p
                className={`text-xs leading-relaxed whitespace-pre-wrap break-words ${
                  isAi ? "text-slate-800" : "text-slate-900 text-right"
                }`}
              >
                {t.content}
              </p>
              {idx < turns.length - 1 && (
                <div
                  className={`mt-1.5 border-t ${
                    isAi ? "border-emerald-100" : "border-slate-200"
                  }`}
                />
              )}
            </div>
          ))
        )}
        <div ref={endRef} className="h-px shrink-0" aria-hidden />
      </div>
    </div>
  );
}

export function SellerVoicePanel({
  step,
  listingTab,
  variant = "dock",
}: {
  step: number;
  listingTab: ListingTab;
  variant?: "panel" | "dock";
}) {
  const lastAction = useSellerFormVoice((s) => s.lastAction);
  const startMode = useSellerFormVoice((s) => s.startMode);
  const setStartMode = useSellerFormVoice((s) => s.setStartMode);
  const isFormEmpty = useSellerFormVoice((s) => s.isFormEmpty);
  const snapshotForm = useSellerFormVoice((s) => s.snapshotForm);
  const appendAssistant = useConversation((s) => s.appendAssistant);

  const hints = VOICE_BY_STEP[step] ?? VOICE_BY_STEP[1];
  const formEmpty = isFormEmpty();

  // 폼 상태에 따라 자동으로 startMode 결정 — 선택 UI 없음
  useEffect(() => {
    if (startMode !== null) return;
    if (formEmpty) {
      setStartMode("fresh");
    } else {
      setStartMode("continue");
      const f = snapshotForm();
      const parts: string[] = [];
      if (f.title) parts.push(`이름은 «${f.title}»`);
      if (f.price) parts.push(`가격은 ${Number(f.price).toLocaleString("ko-KR")}원`);
      if (f.location) parts.push(`지역은 ${f.location}`);
      appendAssistant(
        `네, 지금까지 채우신 내용으로 이어서 도와드릴게요. ${
          parts.length > 0 ? parts.join(", ") + "로 알고 있습니다. " : ""
        }더 고치실 게 있으면 말씀하시고, 없으시면 「이대로 올려 주세요」 라고 말씀하세요.`
      );
    }
  }, [formEmpty, startMode, setStartMode, snapshotForm, appendAssistant]);

  // ── panel variant (사이드바용) ──────────────────────────────
  if (variant === "panel") {
    return (
      <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-b from-emerald-50/90 to-white p-5 sm:p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-shop-teal text-2xl shadow-inner">
            🎙️
          </span>
          <div>
            <h2 className="text-lg font-bold text-slate-900">말로 하기</h2>
            <p className="text-sm text-slate-600">
              {TAB_HINT[listingTab]} · 마이크만 누르고 말씀하세요
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-emerald-100 bg-white/80 p-4 mb-4">
          <p className="text-sm font-semibold text-emerald-900 mb-2">이렇게 말해 보세요</p>
          <ul className="space-y-1.5">
            {hints.map((h) => (
              <li
                key={h}
                className="text-sm text-slate-700 pl-3 border-l-2 border-emerald-300"
              >
                「{h}」
              </li>
            ))}
          </ul>
        </div>

        <MicButton />

        {lastAction && (
          <p className="mt-3 text-center text-sm text-shop-tealDark font-medium">
            {lastAction === "ai_write" && "AI 글 작성을 실행했어요"}
            {lastAction === "ai_image" && "AI 사진 만들기를 실행했어요"}
          </p>
        )}

        <ConversationView />
      </div>
    );
  }

  // ── dock variant (하단 고정 바) ──────────────────────────────
  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-emerald-200/80 bg-gradient-to-t from-white via-white/98 to-emerald-50/30 backdrop-blur-md shadow-[0_-8px_32px_rgba(16,185,129,0.1)]">
      <div className="max-w-6xl mx-auto px-3 sm:px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">

        {/* 3-컬럼: [AI 대화창] [마이크] [나의 대화] */}
        <div className="flex items-stretch gap-3" style={{ height: "180px" }}>

          {/* 왼쪽 — 로컬링크 AI */}
          <ChatColumn role="assistant" label="로컬링크 AI" align="left" />

          {/* 가운데 — 마이크 */}
          <div className="flex flex-col items-center justify-center shrink-0 gap-2 pb-1">
            <MicButton compact />
            {lastAction && (
              <span className="text-[10px] text-emerald-700 font-medium text-center leading-tight">
                {lastAction === "ai_write" ? "✨ AI 글\n적용됨" : "🖼️ AI 사진\n실행"}
              </span>
            )}
          </div>

          {/* 오른쪽 — 나의 대화 */}
          <ChatColumn role="user" label="나의 대화" align="right" />

        </div>
      </div>
    </div>
  );
}
