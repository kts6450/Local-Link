import { useCallback, useRef, useState } from "react";

import { api } from "../../lib/api";
import type { ListingTab, OcrListingDraft } from "../../lib/listingTabs";
import { tabLabel } from "../../lib/listingTabs";
import { useSellerFormVoice } from "../../store/sellerFormVoice";
import { VoiceFillButton } from "./VoiceFillButton";

const FIELD_LABELS: Record<string, string> = {
  title: "이름",
  price: "가격(원)",
  quantity: "수량·중량",
  location: "지역(시·군)",
  description: "설명·특이사항",
  notes: "메모",
  unit: "단위",
  origin: "원산지·생산지",
  producer: "생산자·농가",
  shelf_life: "유통기한",
  storage_method: "보관 방법",
  customer_name: "고객명",
  date_time: "날짜·시간",
  contact_phone: "연락처",
  highlights: "판매 특장점",
};

/** OCR 결과에서 바로 고칠 수 있는 필드 (표시 순서) */
const EDITABLE_FIELD_KEYS = [
  "title",
  "price",
  "quantity",
  "location",
  "description",
  "notes",
  "producer",
  "shelf_life",
  "storage_method",
  "origin",
  "unit",
] as const;

const MULTILINE_KEYS = new Set<string>(["description", "notes"]);

function extractDigits(s: string) {
  const m = s.match(/(\d{1,8})/);
  return m ? m[1] : "";
}

function cleanShort(s: string) {
  return s
    .replace(/[.!?。·]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// 영어/기술 용어가 섞인 LLM 메시지를 어르신이 알아보기 쉬운 한국어로 바꿔 보여준다.
const FRIENDLY_REPLACEMENTS: ReadonlyArray<readonly [RegExp, string]> = [
  [/\blisting_tab\b/gi, "등록 종류"],
  [/\bhint_tab\b/gi, "선택한 탭"],
  [/\bproduct\b/gi, "상품"],
  [/\blodging\b/gi, "숙박"],
  [/\bexperience\b/gi, "체험"],
  [/\bprice\b/gi, "가격"],
  [/\bnotes?\b/gi, "메모"],
  [/\bdescription\b/gi, "설명"],
  [/\bquantity\b/gi, "수량"],
  [/\blocation\b/gi, "지역"],
  [/\btitle\b/gi, "이름"],
  [/\bhighlights?\b/gi, "특장점"],
  [/업데이트/g, "정리"],
  [/분류함/g, "분류했어요"],
  [/힌트는/g, "선택은"],
];

function humanize(text: string): string {
  let out = text;
  for (const [re, rep] of FRIENDLY_REPLACEMENTS) {
    out = out.replace(re, rep);
  }
  return out.replace(/\s+/g, " ").trim();
}

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
  const [activeVoiceField, setActiveVoiceField] = useState<string | null>(null);
  const highlighted = useSellerFormVoice((s) => s.highlight === "note_ocr");

  const voiceLockHandlers = useCallback(
    (key: string) => ({
      disabled: activeVoiceField !== null && activeVoiceField !== key,
      onActiveChange: (active: boolean) => setActiveVoiceField(active ? key : null),
    }),
    [activeVoiceField]
  );

  const updateField = useCallback((key: string, value: string) => {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        fields: {
          ...prev.fields,
          [key]: {
            ...prev.fields[key],
            value,
            needs_review: false,
            confidence: 1,
          },
        },
      };
    });
  }, []);

  const visibleFields = draft
    ? EDITABLE_FIELD_KEYS.filter((key) => {
        const f = draft.fields?.[key];
        if (!f) return false;
        return f.value != null && String(f.value).trim() !== "";
      })
    : [];

  const hasReview = visibleFields.some((key) => {
    const f = draft?.fields?.[key];
    return f?.needs_review || (f?.confidence ?? 1) < 0.7;
  });

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
    <div
      className={`rounded-3xl border p-5 sm:p-6 shadow-sm mb-5 transition-[box-shadow,transform,border-color] duration-300 ${
        highlighted
          ? "border-amber-400 bg-gradient-to-b from-amber-100 to-amber-50/60 shadow-[0_0_0_4px_rgba(245,158,11,0.25)] animate-pulse"
          : "border-amber-200/90 bg-gradient-to-b from-amber-50/90 to-white"
      }`}
    >
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
            <div className="flex items-center gap-2">
              {draft.ocr_engine?.includes("clova") ? (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-800 font-semibold">
                  CLOVA OCR
                </span>
              ) : null}
              <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                신뢰도 {Math.round((draft.confidence_overall || 0) * 100)}%
              </span>
            </div>
          </div>

          {draft.a2a_steps && draft.a2a_steps.length > 0 && (
            <div className="rounded-lg border border-emerald-100 bg-emerald-50/70 px-3 py-2 space-y-1">
              <p className="text-sm font-semibold text-emerald-800">
                ✅ AI가 한 번 더 살펴봤어요
              </p>
              {draft.a2a_steps.flatMap((s) => s.applied ?? []).length > 0 && (
                <p className="text-xs text-emerald-900/80">
                  바로잡은 항목:{" "}
                  {Array.from(
                    new Set(
                      draft.a2a_steps.flatMap((s) =>
                        (s.applied ?? []).map(
                          (k) => FIELD_LABELS[k] ?? k
                        )
                      )
                    )
                  ).join(", ")}
                </p>
              )}
              {draft.a2a_steps.flatMap((s) => s.fixes ?? []).length > 0 && (
                <ul className="text-xs text-emerald-900/80 list-disc pl-5 space-y-0.5">
                  {Array.from(
                    new Set(
                      draft.a2a_steps
                        .flatMap((s) => s.fixes ?? [])
                        .map((f) => humanize(String(f)))
                        .filter(Boolean)
                    )
                  )
                    .slice(0, 3)
                    .map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                </ul>
              )}
            </div>
          )}

          {hasReview && (
            <p className="text-xs text-orange-900 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
              주황색 「확인 필요」 항목은 옆 🎤 로 말해서 고치거나, 칸에 적어 주세요. 고친 뒤
              「폼에 채우기」를 누르세요.
            </p>
          )}

          {draft.warnings?.map((w, i) => (
            <p key={i} className="text-xs text-amber-900 bg-amber-50 rounded-lg px-3 py-2">
              {humanize(String(w))}
            </p>
          ))}

          {draft.raw_text?.trim() && (
            <p className="text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-2 whitespace-pre-wrap max-h-24 overflow-y-auto">
              인식 텍스트: {draft.raw_text.trim().slice(0, 400)}
            </p>
          )}

          <ul className="space-y-3 text-sm">
            {visibleFields.map((key) => {
              const f = draft.fields[key];
              if (!f) return null;
              const review = f.needs_review || (f.confidence ?? 1) < 0.7;
              const label = FIELD_LABELS[key] ?? key;
              const strVal = String(f.value ?? "");
              const voiceHint =
                key === "price"
                  ? "가격을 숫자로 말하기"
                  : `${label} 말로 입력·고치기`;

              return (
                <li
                  key={key}
                  className={`rounded-lg px-3 py-2 border ${
                    review
                      ? "border-orange-300 bg-orange-50"
                      : "border-slate-100 bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-slate-500 text-xs font-semibold">{label}</span>
                    {review && (
                      <span className="text-[10px] font-semibold text-orange-700">
                        확인 필요
                      </span>
                    )}
                  </div>
                  <div className="flex items-start gap-2">
                    {MULTILINE_KEYS.has(key) ? (
                      <textarea
                        className="input-field text-sm flex-1 min-h-[72px] resize-y"
                        value={strVal}
                        onChange={(e) => updateField(key, e.target.value)}
                      />
                    ) : (
                      <input
                        className="input-field text-sm flex-1"
                        value={strVal}
                        inputMode={key === "price" ? "numeric" : "text"}
                        onChange={(e) =>
                          updateField(
                            key,
                            key === "price"
                              ? e.target.value.replace(/\D/g, "")
                              : e.target.value
                          )
                        }
                      />
                    )}
                    <VoiceFillButton
                      tone={review ? "amber" : "slate"}
                      hint={voiceHint}
                      onInterim={(t) => {
                        if (key === "price") {
                          const d = extractDigits(t);
                          if (d) updateField(key, d);
                        } else {
                          updateField(key, t);
                        }
                      }}
                      onText={(t) => {
                        if (key === "price") {
                          const d = extractDigits(t);
                          if (d) updateField(key, d);
                        } else {
                          updateField(key, cleanShort(t));
                        }
                      }}
                      {...voiceLockHandlers(`ocr_${key}`)}
                    />
                  </div>
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
