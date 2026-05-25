import type { ListingTab } from "../../lib/listingTabs";
import type { ListingGuide } from "../../types";

const EXPERIENCE_HINTS = ["체험", "축제", "투어", "견학", "수확", "낚시", "만들기", "잡기", "갯벌", "캠핑"];

function looksLikeExperience(listingTab: ListingTab, title: string | undefined): boolean {
  if (listingTab === "experience") return true;
  if (listingTab === "lodging") return false;
  const t = (title ?? "").toLowerCase();
  return EXPERIENCE_HINTS.some((h) => t.includes(h));
}

export function ListingGuidePreview({
  guide,
  listingTab = "product",
  title,
}: {
  guide: ListingGuide;
  listingTab?: ListingTab;
  title?: string;
}) {
  const isExp = looksLikeExperience(listingTab, title);
  const isMarketProduct = listingTab === "product" && !isExp;

  const highlights = guide.highlights ?? [];
  // 마켓 상품에는 체험 일정·만남장소가 어울리지 않으므로 화면에서도 숨긴다.
  const steps = isMarketProduct ? [] : (guide.steps ?? []);
  const included = guide.included ?? [];
  const notIncluded = guide.not_included ?? [];
  const precautions = guide.precautions ?? [];
  const showMeeting = !isMarketProduct && (guide.meeting_place || guide.address);
  const showAddressOnly = isMarketProduct && guide.address;

  const highlightsTitle = isMarketProduct
    ? "상품 특징"
    : isExp
      ? "체험 포인트"
      : "이용 포인트";

  return (
    <div className="rounded-2xl border border-shop-teal/20 bg-white p-4 sm:p-5 space-y-4 text-sm">
      <h3 className="font-bold text-base text-slate-900">이용 안내 미리보기</h3>

      {highlights.length > 0 && (
        <section>
          <p className="font-semibold text-shop-tealDark mb-2">{highlightsTitle}</p>
          <ul className="list-disc pl-5 space-y-1 text-slate-700">
            {highlights.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        </section>
      )}

      {steps.length > 0 && (
        <section>
          <p className="font-semibold text-shop-tealDark mb-2">진행 순서</p>
          <ol className="space-y-2">
            {steps.map((st, i) => (
              <li key={i} className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                {st.time ? (
                  <span className="text-xs font-bold text-shop-teal mr-2">{st.time}</span>
                ) : null}
                <span className="font-medium text-slate-900">{st.title}</span>
                {st.body ? <p className="text-slate-600 mt-1">{st.body}</p> : null}
              </li>
            ))}
          </ol>
        </section>
      )}

      {included.length > 0 && (
        <section>
          <p className="font-semibold text-slate-800 mb-1">{isMarketProduct ? "함께 보내는 것" : "포함"}</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {included.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {notIncluded.length > 0 && (
        <section>
          <p className="font-semibold text-slate-800 mb-1">{isMarketProduct ? "포함되지 않은 것" : "불포함"}</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {notIncluded.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {precautions.length > 0 && (
        <section>
          <p className="font-semibold text-slate-800 mb-1">{isMarketProduct ? "보관·취급 안내" : "유의사항"}</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {precautions.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {guide.refund_policy ? (
        <section>
          <p className="font-semibold text-slate-800 mb-1">교환·반품·환불</p>
          <p className="text-slate-700 leading-relaxed">{guide.refund_policy}</p>
        </section>
      ) : null}

      {showMeeting && (
        <section className="text-slate-700">
          {guide.meeting_place ? <p>만남: {guide.meeting_place}</p> : null}
          {guide.address ? <p>주소: {guide.address}</p> : null}
        </section>
      )}

      {showAddressOnly && (
        <section className="text-slate-700">
          <p>발송지: {guide.address}</p>
        </section>
      )}

      {highlights.length === 0 &&
        steps.length === 0 &&
        included.length === 0 &&
        !guide.refund_policy && (
          <p className="text-slate-500">이용 안내 항목이 비어 있습니다. AI를 다시 실행해 보세요.</p>
        )}
    </div>
  );
}
