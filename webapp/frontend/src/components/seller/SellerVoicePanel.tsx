import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";

import { ConversationView } from "../ConversationView";
import { MicButton } from "../MicButton";
import { VoiceChatSheet } from "./VoiceChatSheet";
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
  const reset = useConversation((s) => s.reset);
  const appendAssistant = useConversation((s) => s.appendAssistant);
  const historyLen = useConversation((s) => s.history.length);
  const phase = useConversation((s) => s.phase);
  const [chatOpen, setChatOpen] = useState(false);
  const prevHistoryLen = useRef(historyLen);

  const hints = VOICE_BY_STEP[step] ?? VOICE_BY_STEP[1];
  const formEmpty = isFormEmpty();
  const showChoice = !formEmpty && startMode === null;

  useEffect(() => {
    if (formEmpty && startMode === null) {
      setStartMode("fresh");
    }
  }, [formEmpty, startMode, setStartMode]);

  useEffect(() => {
    if (historyLen > prevHistoryLen.current && historyLen > 1) {
      setChatOpen(true);
    }
    prevHistoryLen.current = historyLen;
  }, [historyLen]);

  useEffect(() => {
    if (phase === "thinking" || phase === "speaking") {
      setChatOpen(true);
    }
  }, [phase]);

  const handleContinue = () => {
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
  };

  const handleFresh = () => {
    setStartMode("fresh");
    reset("seller");
    appendAssistant("네, 처음부터 다시 시작할게요. " + WELCOME_SELLER);
  };

  const choiceBlock = showChoice ? (
    <div className="rounded-xl border border-amber-200 bg-amber-50/95 px-3 py-2 mb-2">
      <p className="text-xs font-semibold text-amber-900 mb-2">
        화면에 채운 내용이 있어요. 어떻게 시작할까요?
      </p>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={handleContinue}
          className="rounded-lg bg-shop-teal text-white text-xs font-semibold py-2 px-2 hover:brightness-110"
        >
          채운 내용으로 이어서
        </button>
        <button
          type="button"
          onClick={handleFresh}
          className="rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-semibold py-2 px-2 hover:bg-slate-50"
        >
          처음부터 새로
        </button>
      </div>
    </div>
  ) : null;

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

        {showChoice ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 mb-4">
            <p className="text-sm font-semibold text-amber-900 mb-1">어떻게 시작할까요?</p>
            <p className="text-xs text-amber-800/90 mb-3">
              화면에 이미 채우신 내용이 있어요.
              <br />
              그대로 이어서 도와드릴까요, 아니면 처음부터 다시 시작할까요?
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={handleContinue}
                className="rounded-xl bg-shop-teal text-white font-semibold py-3 px-3 hover:brightness-110"
              >
                📝 채운 내용으로 이어서
              </button>
              <button
                type="button"
                onClick={handleFresh}
                className="rounded-xl bg-white border border-slate-300 text-slate-700 font-semibold py-3 px-3 hover:bg-slate-50"
              >
                🔄 처음부터 새로
              </button>
            </div>
          </div>
        ) : (
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
        )}

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

  return (
    <>
      <VoiceChatSheet open={chatOpen} onToggle={() => setChatOpen((v) => !v)} step={step} />

      <div className="fixed inset-x-0 bottom-0 z-50 border-t border-emerald-200/80 bg-gradient-to-t from-white via-white/98 to-emerald-50/30 backdrop-blur-md shadow-[0_-8px_32px_rgba(16,185,129,0.1)]">
        <div className="max-w-6xl mx-auto px-3 sm:px-4 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          {choiceBlock}

          <div className="flex items-end gap-2 sm:gap-4">
            <div className="hidden sm:block min-w-[6.5rem] shrink-0 pb-1">
              <p className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <span className="text-base" aria-hidden>
                  🎙️
                </span>
                말로 하기
              </p>
              <p className="text-[11px] text-slate-500 leading-snug mt-0.5">
                {TAB_HINT[listingTab]}
              </p>
            </div>

            <div className="flex-1 flex justify-center min-w-0">
              <MicButton compact />
            </div>

            <div className="flex flex-col items-end gap-1.5 shrink-0 pb-1 min-w-[5rem] sm:min-w-[6.5rem]">
              <button
                type="button"
                onClick={() => setChatOpen((v) => !v)}
                className={clsx(
                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors",
                  chatOpen
                    ? "bg-shop-teal text-white"
                    : "bg-emerald-50 text-shop-tealDark border border-emerald-200 hover:bg-emerald-100"
                )}
              >
                <span aria-hidden>💬</span>
                {chatOpen ? "대화 접기" : historyLen > 1 ? "대화 펼치기" : "대화"}
              </button>
              {lastAction ? (
                <span className="text-[10px] text-emerald-700 text-right leading-tight">
                  {lastAction === "ai_write" ? "✨ AI 글 적용됨" : "🖼️ AI 사진 실행"}
                </span>
              ) : (
                <span className="text-[10px] text-slate-400 text-right leading-tight hidden sm:block max-w-[8rem] truncate">
                  「{hints[0]}」
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
