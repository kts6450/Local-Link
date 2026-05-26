import { useEffect } from "react";

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

export function SellerVoicePanel({
  step,
  listingTab,
}: {
  step: number;
  listingTab: ListingTab;
}) {
  const lastAction = useSellerFormVoice((s) => s.lastAction);
  const startMode = useSellerFormVoice((s) => s.startMode);
  const setStartMode = useSellerFormVoice((s) => s.setStartMode);
  const isFormEmpty = useSellerFormVoice((s) => s.isFormEmpty);
  const snapshotForm = useSellerFormVoice((s) => s.snapshotForm);
  const reset = useConversation((s) => s.reset);
  const appendAssistant = useConversation((s) => s.appendAssistant);

  const hints = VOICE_BY_STEP[step] ?? VOICE_BY_STEP[1];

  // 폼에 정보가 들어 있는데 사용자가 아직 시작 방식을 고르지 않은 경우 → 두 버튼 표시.
  const formEmpty = isFormEmpty();
  const showChoice = !formEmpty && startMode === null;

  // 폼이 비어 있으면 굳이 선택지를 강요할 필요 없으므로 startMode 를 자동으로 fresh.
  useEffect(() => {
    if (formEmpty && startMode === null) {
      setStartMode("fresh");
    }
  }, [formEmpty, startMode, setStartMode]);

  const handleContinue = () => {
    setStartMode("continue");
    const f = snapshotForm();
    const parts: string[] = [];
    if (f.title) parts.push(`이름은 «${f.title}»`);
    if (f.price)
      parts.push(`가격은 ${Number(f.price).toLocaleString("ko-KR")}원`);
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
    appendAssistant(
      "네, 처음부터 다시 시작할게요. " + WELCOME_SELLER
    );
  };

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
          <p className="text-sm font-semibold text-amber-900 mb-1">
            어떻게 시작할까요?
          </p>
          <p className="text-xs text-amber-800/90 mb-3">
            화면에 이미 채우신 내용이 있어요.
            <br />
            그대로 이어서 도와드릴까요, 아니면 처음부터 다시 시작할까요?
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={handleContinue}
              className="rounded-xl bg-shop-teal text-white font-semibold py-3 px-3 hover:brightness-110 active:brightness-95 transition shadow-sm leading-tight"
            >
              📝 채운 내용으로
              <br />
              <span className="text-xs font-medium opacity-90">이어서 진행</span>
            </button>
            <button
              type="button"
              onClick={handleFresh}
              className="rounded-xl bg-white border border-slate-300 text-slate-700 font-semibold py-3 px-3 hover:bg-slate-50 active:bg-slate-100 transition leading-tight"
            >
              🔄 처음부터
              <br />
              <span className="text-xs font-medium text-slate-500">새로 시작</span>
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
          {startMode === "continue" && (
            <p className="mt-3 text-xs text-emerald-800 leading-relaxed">
              💡 채워두신 내용은 음성 도우미가 이미 알고 있어요. 바뀐 부분만 말씀하셔도 됩니다.
            </p>
          )}
          {step === 2 && (
            <p className="mt-3 text-xs text-slate-500 leading-relaxed">
              이름·가격을 먼저 적어 두시면 AI가 소개 글과 이용 안내를 채워 드립니다.
            </p>
          )}
          {step === 3 && (
            <p className="mt-3 text-xs text-slate-500 leading-relaxed">
              「사진 만들어 줘」라고 하시면 대표 사진을 AI가 그려 드립니다.
            </p>
          )}
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
