import type { ListingGuide } from "../../types";

export function ListingGuidePreview({ guide }: { guide: ListingGuide }) {
  const highlights = guide.highlights ?? [];
  const steps = guide.steps ?? [];
  const included = guide.included ?? [];
  const notIncluded = guide.not_included ?? [];
  const precautions = guide.precautions ?? [];

  return (
    <div className="rounded-2xl border border-shop-teal/20 bg-white p-4 sm:p-5 space-y-4 text-sm">
      <h3 className="font-bold text-base text-slate-900">이용 안내 미리보기</h3>

      {highlights.length > 0 && (
        <section>
          <p className="font-semibold text-shop-tealDark mb-2">체험·상품 포인트</p>
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
          <p className="font-semibold text-slate-800 mb-1">포함</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {included.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {notIncluded.length > 0 && (
        <section>
          <p className="font-semibold text-slate-800 mb-1">불포함</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {notIncluded.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {precautions.length > 0 && (
        <section>
          <p className="font-semibold text-slate-800 mb-1">유의사항</p>
          <ul className="list-disc pl-5 text-slate-700 space-y-0.5">
            {precautions.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {guide.refund_policy ? (
        <section>
          <p className="font-semibold text-slate-800 mb-1">환불·교환</p>
          <p className="text-slate-700 leading-relaxed">{guide.refund_policy}</p>
        </section>
      ) : null}

      {(guide.meeting_place || guide.address) && (
        <section className="text-slate-700">
          {guide.meeting_place ? <p>만남: {guide.meeting_place}</p> : null}
          {guide.address ? <p>주소: {guide.address}</p> : null}
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
