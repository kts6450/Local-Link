import type { ListingTab } from "../../lib/listingTabs";
import type { ListingGuide, ListingGuideStep } from "../../types";

const EXPERIENCE_HINTS = [
  "체험",
  "축제",
  "투어",
  "견학",
  "수확",
  "낚시",
  "만들기",
  "잡기",
  "갯벌",
  "캠핑",
];

function looksLikeExperience(listingTab: ListingTab, title: string | undefined): boolean {
  if (listingTab === "experience") return true;
  if (listingTab === "lodging") return false;
  const t = (title ?? "").toLowerCase();
  return EXPERIENCE_HINTS.some((h) => t.includes(h));
}

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToLines(items: string[] | undefined): string {
  return (items ?? []).join("\n");
}

function patch(guide: ListingGuide, next: Partial<ListingGuide>): ListingGuide {
  return { ...guide, ...next };
}

function StringListField({
  label,
  hint,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  hint?: string;
  value: string[] | undefined;
  onChange: (items: string[]) => void;
  placeholder?: string;
}) {
  return (
    <section>
      <label className="font-semibold text-slate-800 block mb-1">{label}</label>
      {hint ? <p className="text-[11px] text-slate-500 mb-1">{hint}</p> : null}
      <textarea
        className="input-field text-sm min-h-[88px]"
        value={listToLines(value)}
        onChange={(e) => onChange(linesToList(e.target.value))}
        placeholder={placeholder}
      />
      <p className="text-[11px] text-slate-400 mt-1">한 줄에 하나씩 적어 주세요.</p>
    </section>
  );
}

export function ListingGuideEditor({
  guide,
  listingTab = "product",
  title,
  onChange,
}: {
  guide: ListingGuide;
  listingTab?: ListingTab;
  title?: string;
  onChange: (guide: ListingGuide) => void;
}) {
  const isExp = looksLikeExperience(listingTab, title);
  const isMarketProduct = listingTab === "product" && !isExp;

  const highlightsTitle = isMarketProduct
    ? "상품 특징"
    : isExp
      ? "체험 포인트"
      : "이용 포인트";

  const steps = isMarketProduct ? [] : (guide.steps ?? []);

  const updateStep = (index: number, patchStep: Partial<ListingGuideStep>) => {
    const next = [...(guide.steps ?? [])];
    next[index] = { ...next[index], ...patchStep };
    onChange(patch(guide, { steps: next }));
  };

  const addStep = () => {
    onChange(
      patch(guide, {
        steps: [...(guide.steps ?? []), { title: "", body: "" }],
      })
    );
  };

  const removeStep = (index: number) => {
    const next = (guide.steps ?? []).filter((_, i) => i !== index);
    onChange(patch(guide, { steps: next.length ? next : undefined }));
  };

  return (
    <div className="rounded-2xl border border-shop-teal/20 bg-white p-4 sm:p-5 space-y-4 text-sm">
      <div>
        <h3 className="font-bold text-base text-slate-900">이용 안내 편집</h3>
        <p className="text-xs text-slate-500 mt-1">
          AI가 작성한 내용도 아래에서 바로 수정할 수 있어요.
        </p>
      </div>

      <StringListField
        label={highlightsTitle}
        value={guide.highlights}
        onChange={(highlights) =>
          onChange(patch(guide, { highlights: highlights.length ? highlights : undefined }))
        }
        placeholder="예: 강릉 앞바다에서 배 타고 낚시"
      />

      {!isMarketProduct ? (
        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold text-slate-800">진행 순서</p>
            <button
              type="button"
              className="text-xs px-2.5 py-1 rounded-full border border-shop-teal/30 text-shop-tealDark hover:bg-shop-tealLight/40"
              onClick={addStep}
            >
              + 순서 추가
            </button>
          </div>
          {steps.length === 0 ? (
            <p className="text-xs text-slate-400">체험·숙박 일정이 있으면 순서를 추가해 주세요.</p>
          ) : (
            <ol className="space-y-3">
              {steps.map((st, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-slate-200 bg-slate-50/80 p-3 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-shop-teal">순서 {i + 1}</span>
                    <button
                      type="button"
                      className="text-xs text-rose-600 hover:underline"
                      onClick={() => removeStep(i)}
                    >
                      삭제
                    </button>
                  </div>
                  <input
                    className="input-field text-sm"
                    value={st.time ?? ""}
                    onChange={(e) => updateStep(i, { time: e.target.value })}
                    placeholder="09:00 (선택)"
                  />
                  <input
                    className="input-field text-sm"
                    value={st.title}
                    onChange={(e) => updateStep(i, { title: e.target.value })}
                    placeholder="제목"
                  />
                  <textarea
                    className="input-field text-sm min-h-[64px]"
                    value={st.body}
                    onChange={(e) => updateStep(i, { body: e.target.value })}
                    placeholder="설명"
                  />
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : null}

      <StringListField
        label={isMarketProduct ? "함께 보내는 것" : "포함"}
        value={guide.included}
        onChange={(included) =>
          onChange(patch(guide, { included: included.length ? included : undefined }))
        }
      />

      <StringListField
        label={isMarketProduct ? "포함되지 않은 것" : "불포함"}
        value={guide.not_included}
        onChange={(not_included) =>
          onChange(patch(guide, { not_included: not_included.length ? not_included : undefined }))
        }
      />

      <StringListField
        label={isMarketProduct ? "보관·취급 안내" : "유의사항"}
        value={guide.precautions}
        onChange={(precautions) =>
          onChange(patch(guide, { precautions: precautions.length ? precautions : undefined }))
        }
      />

      <section>
        <label className="font-semibold text-slate-800 block mb-1">교환·반품·환불</label>
        <textarea
          className="input-field text-sm min-h-[72px]"
          value={guide.refund_policy ?? ""}
          onChange={(e) =>
            onChange(patch(guide, { refund_policy: e.target.value.trim() || undefined }))
          }
          placeholder="취소·환불 규정"
        />
      </section>

      {!isMarketProduct ? (
        <>
          <section>
            <label className="font-semibold text-slate-800 block mb-1">만남 장소</label>
            <input
              className="input-field text-sm"
              value={guide.meeting_place ?? ""}
              onChange={(e) =>
                onChange(patch(guide, { meeting_place: e.target.value.trim() || undefined }))
              }
              placeholder="예: 강릉항 2부두 앞"
            />
          </section>
          <section>
            <label className="font-semibold text-slate-800 block mb-1">주소</label>
            <input
              className="input-field text-sm"
              value={guide.address ?? ""}
              onChange={(e) =>
                onChange(patch(guide, { address: e.target.value.trim() || undefined }))
              }
              placeholder="상세 주소"
            />
          </section>
        </>
      ) : (
        <section>
          <label className="font-semibold text-slate-800 block mb-1">발송지</label>
          <input
            className="input-field text-sm"
            value={guide.address ?? ""}
            onChange={(e) =>
              onChange(patch(guide, { address: e.target.value.trim() || undefined }))
            }
            placeholder="택배 발송지"
          />
        </section>
      )}
    </div>
  );
}
