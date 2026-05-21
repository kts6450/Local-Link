import { ConversationView } from "../ConversationView";
import { MicButton } from "../MicButton";
import { useSellerFormVoice } from "../../store/sellerFormVoice";

const VOICE_BY_STEP: Record<number, string[]> = {
  1: ["상품 팔아요", "민박 빌려줘요", "올해 햅쌀 십 키로, 만 이천 원"],
  2: ["AI로 글 써줘", "소개 글 만들어 줘", "설명만 짧게"],
  3: ["대표 사진 만들어 줘", "바다에서 낚시하는 사진"],
  4: ["이대로 올려 주세요", "네, 올려요"],
};

export function SellerVoicePanel({ step }: { step: number }) {
  const lastAction = useSellerFormVoice((s) => s.lastAction);
  const hints = VOICE_BY_STEP[step] ?? VOICE_BY_STEP[1];

  return (
    <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-b from-emerald-50/90 to-white p-5 sm:p-6 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-shop-teal text-2xl shadow-inner">
          🎙️
        </span>
        <div>
          <h2 className="text-lg font-bold text-slate-900">말로 하기</h2>
          <p className="text-sm text-slate-600">마이크만 누르고 편하게 말씀하세요</p>
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
