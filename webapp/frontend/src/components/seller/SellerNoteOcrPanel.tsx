import { useRef, useState } from "react";

import { api } from "../../lib/api";
import type { ListingTab, OcrListingDraft } from "../../lib/listingTabs";
import { tabLabel } from "../../lib/listingTabs";

const FIELD_LABELS: Record<string, string> = {
  title: "이름",
  price: "가격(원)",
  quantity: "수량·중량",
  location: "지역·원산지",
  description: "설명·특이사항",
  notes: "메모",
  customer_name: "고객명",
  date_time: "날짜·시간",
  contact_phone: "연락처",
};

type Props = {
  listingTab: ListingTab;
  onApply: (draft: OcrListingDraft) => void;
};

export function SellerNoteOcrPanel({ listingTab, onApply }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<OcrListingDraft | null>(null);
  const [previews, setPreviews] = useState<string[]>([]);

  const onPick = async (files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    setBusy(true);
    try {
      const picked = Array.from(files)
        .filter((f) => f.type.startsWith("image/"))
        .slice(0, 5);
      if (!picked.length) {
        setError("이미지 파일만 올릴 수 있어요.");
        return;
      }
      const dataUrls = await Promise.all(
        picked.map(
          (f) =>
            new Promise<string>((resolve, reject) => {
              const r = new FileReader();
              r.onload = () => resolve(String(r.result || ""));
              r.onerror = () => reject(new Error("read fail"));
              r.readAsDataURL(f);
            })
        )
      );
      setPreviews(dataUrls);
      const images_base64 = dataUrls.map((u) =>
        u.includes(",") ? u.split(",", 2)[1] : u
      );
      const result = await api.ocrListingDraft({
        images_base64,
        hint_tab: listingTab,
      });
      setDraft(result);
    } catch (e) {
      setDraft(null);
      setError(e instanceof Error ? e.message : "OCR에 실패했어요.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const clear = () => {
    setDraft(null);
    setPreviews([]);
    setError(null);
  };

  return (
    <div className="rounded-3xl border border-amber-200/90 bg-gradient-to-b from-amber-50/90 to-white p-5 sm:p-6 shadow-sm mb-5">
      <div className="flex items-center gap-3 mb-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-2xl">
          📷
        </span>
        <div>
          <h2 className="text-lg font-bold text-slate-900">노트 사진으로 채우기</h2>
          <p className="text-sm text-slate-600">메모·포스트잇 촬영 (최대 5장)</p>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => void onPick(e.target.files)}
      />

      <button
        type="button"
        className="w-full btn-primary py-3 bg-amber-600 hover:bg-amber-700 border-amber-700"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {busy ? "읽는 중…" : "갤러리에서 사진 선택"}
      </button>

      {error && (
        <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-100 rounded-xl px-3 py-2">
          {error}
        </p>
      )}

      {previews.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {previews.map((src, i) => (
            <li key={i}>
              <img src={src} alt="" className="w-14 h-14 object-cover rounded-lg border" />
            </li>
          ))}
        </ul>
      )}

      {draft && (
        <div className="mt-4 rounded-2xl border border-amber-100 bg-white/90 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-slate-800">
              OCR 결과 · {tabLabel(draft.listing_tab)} 추천
            </p>
            <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
              신뢰도 {Math.round((draft.confidence_overall || 0) * 100)}%
            </span>
          </div>

          {draft.warnings?.map((w, i) => (
            <p key={i} className="text-xs text-amber-900 bg-amber-50 rounded-lg px-3 py-2">
              {w}
            </p>
          ))}

          {draft.raw_text?.trim() && (
            <p className="text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2 whitespace-pre-wrap max-h-24 overflow-y-auto">
              인식 텍스트: {draft.raw_text.trim().slice(0, 400)}
            </p>
          )}

          <ul className="space-y-2 text-sm">
            {Object.entries(draft.fields || {}).map(([key, f]) => {
              if (f?.value == null || f.value === "") return null;
              const review = f.needs_review || (f.confidence ?? 1) < 0.7;
              return (
                <li
                  key={key}
                  className={`rounded-lg px-3 py-2 border ${
                    review
                      ? "border-orange-300 bg-orange-50"
                      : "border-slate-100 bg-slate-50"
                  }`}
                >
                  <span className="text-slate-500">{FIELD_LABELS[key] ?? key}</span>
                  {review && (
                    <span className="ml-2 text-xs font-semibold text-orange-700">
                      확인 필요
                    </span>
                  )}
                  <p className="font-medium text-slate-900 mt-0.5">{String(f.value)}</p>
                </li>
              );
            })}
          </ul>

          {draft.missing_required?.length > 0 && (
            <p className="text-xs text-red-700">
              필수 누락: {draft.missing_required.join(", ")} — 직접 입력해 주세요.
            </p>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              className="btn-primary py-2.5 px-4 flex-1 min-w-[120px]"
              onClick={() => onApply(draft)}
            >
              폼에 채우기
            </button>
            <button type="button" className="btn-ghost py-2.5 px-4" onClick={clear}>
              다시
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
