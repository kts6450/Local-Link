import type { ReactNode } from "react";

import type { Listing, ListingGuide } from "../types";

type CardVariant = "default" | "highlight" | "teal" | "cream";

function GuideCard({
  icon,
  title,
  subtitle,
  variant = "default",
  children,
}: {
  icon: string;
  title: string;
  subtitle?: string;
  variant?: CardVariant;
  children: ReactNode;
}) {
  const shell: Record<CardVariant, string> = {
    default: "bg-white border-brand-line/90",
    highlight: "bg-gradient-to-br from-amber-50/90 to-orange-50/40 border-amber-200/80",
    teal: "bg-gradient-to-br from-shop-tealLight/70 to-emerald-50/50 border-shop-teal/15",
    cream: "bg-gradient-to-br from-brand-cream to-brand-warm/60 border-brand-line/90",
  };

  return (
    <section
      className={`rounded-2xl border p-6 sm:p-7 shadow-soft overflow-visible ${shell[variant]}`}
    >
      <div className="flex items-start gap-4 mb-5">
        <span
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/90 text-2xl shadow-soft ring-1 ring-black/[0.04]"
          aria-hidden
        >
          {icon}
        </span>
        <div className="min-w-0 flex-1 pt-0.5">
          <h3 className="font-bold text-hades-text text-lg sm:text-xl leading-snug">{title}</h3>
          {subtitle ? (
            <p className="mt-1 text-sm sm:text-base text-hades-muted leading-relaxed">{subtitle}</p>
          ) : null}
        </div>
      </div>
      <div className="text-slate-800 leading-relaxed">{children}</div>
    </section>
  );
}

function CheckList({
  items,
  tone,
}: {
  items: string[];
  tone: "included" | "excluded" | "caution";
}) {
  if (items.length === 0) return null;

  const mark =
    tone === "included" ? "✓" : tone === "excluded" ? "−" : "!";
  const markCls =
    tone === "included"
      ? "bg-emerald-100 text-emerald-800"
      : tone === "excluded"
        ? "bg-slate-100 text-slate-500"
        : "bg-amber-100 text-amber-800";

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {items.map((t, i) => (
        <li
          key={i}
          className="flex gap-3 rounded-xl bg-white/70 border border-white/80 px-4 py-3.5 shadow-soft"
        >
          <span
            className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${markCls}`}
            aria-hidden
          >
            {mark}
          </span>
          <span className="text-[0.98rem] sm:text-base leading-relaxed">{t}</span>
        </li>
      ))}
    </ul>
  );
}

/** 상품 정보 탭 — 루플형 체험 포인트·STEP */
export function ListingInfoSections({ listing }: { listing: Listing }) {
  const g = listing.guide;
  const isExperience = listing.kind !== "lodging" && listing.category === "experience";
  const isMarketProduct = listing.kind === "product" && !isExperience;
  // 마켓 상품(택배·픽업)에는 시간표가 어울리지 않으므로 숨긴다.
  const steps = isMarketProduct ? [] : (g?.steps ?? []);
  const highlightsTitle = isExperience ? "체험 포인트" : "상품 특징";

  // 상세 정보 — 종류별 필드. 빈 값은 그리지 않는다.
  const detailRows: { label: string; value?: string | null; icon: string }[] = [];
  const d = listing.details;
  if (isMarketProduct && d) {
    if (d.unit?.trim()) detailRows.push({ label: "단위", value: d.unit, icon: "📦" });
    if (d.origin?.trim()) detailRows.push({ label: "원산지", value: d.origin, icon: "🌾" });
    if (d.producer?.trim())
      detailRows.push({ label: "생산자", value: d.producer, icon: "👨‍🌾" });
    if (d.shelf_life?.trim())
      detailRows.push({ label: "유통기한", value: d.shelf_life, icon: "⏳" });
    if (d.storage_method?.trim())
      detailRows.push({ label: "보관 방법", value: d.storage_method, icon: "🧊" });
  } else if (isExperience && d) {
    if (d.duration?.trim())
      detailRows.push({ label: "소요 시간", value: d.duration, icon: "⏱️" });
    if (d.meeting_point?.trim())
      detailRows.push({ label: "모임 장소", value: d.meeting_point, icon: "📍" });
    if (d.includes?.trim())
      detailRows.push({ label: "포함 사항", value: d.includes, icon: "✅" });
    if (d.what_to_bring?.trim())
      detailRows.push({ label: "준비물", value: d.what_to_bring, icon: "🎒" });
    if (d.min_age?.trim())
      detailRows.push({ label: "참가 연령", value: d.min_age, icon: "👨‍👩‍👧" });
    if (d.weather_policy?.trim())
      detailRows.push({ label: "날씨·취소", value: d.weather_policy, icon: "🌦️" });
  } else if (listing.kind === "lodging" && d) {
    if (d.check_in?.trim())
      detailRows.push({ label: "체크인", value: d.check_in, icon: "🔑" });
    if (d.check_out?.trim())
      detailRows.push({ label: "체크아웃", value: d.check_out, icon: "🚪" });
    if (d.amenities?.trim())
      detailRows.push({ label: "편의 시설", value: d.amenities, icon: "🛋️" });
    if (d.breakfast?.trim())
      detailRows.push({ label: "조식", value: d.breakfast, icon: "🍳" });
    if (d.parking?.trim())
      detailRows.push({ label: "주차", value: d.parking, icon: "🅿️" });
    if (d.pet_policy?.trim())
      detailRows.push({ label: "반려동물", value: d.pet_policy, icon: "🐾" });
  }

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-hades-line bg-slate-50/80 p-5 sm:p-6">
        <p className="text-slate-700 text-lg leading-relaxed whitespace-pre-wrap">
          {listing.description || "상세 설명이 곧 추가됩니다."}
        </p>
      </div>

      {detailRows.length > 0 && (
        <section>
          <h3 className="font-bold text-hades-text text-xl mb-4">
            {isExperience ? "체험 정보" : listing.kind === "lodging" ? "숙박 정보" : "상품 정보"}
          </h3>
          <dl className="rounded-2xl border border-hades-line bg-white divide-y divide-slate-100 overflow-hidden">
            {detailRows.map((r) => (
              <div
                key={r.label}
                className="grid grid-cols-[110px_1fr] gap-3 sm:gap-4 px-4 sm:px-5 py-3.5"
              >
                <dt className="text-sm font-semibold text-slate-500 flex items-center gap-1.5">
                  <span aria-hidden>{r.icon}</span>
                  <span>{r.label}</span>
                </dt>
                <dd className="text-slate-800 leading-snug">{r.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {g?.highlights && g.highlights.length > 0 && (
        <section>
          <h3 className="font-bold text-hades-text text-xl mb-4">{highlightsTitle}</h3>
          <ul className="grid gap-3 sm:grid-cols-2">
            {g.highlights.map((h, i) => (
              <li
                key={i}
                className="rounded-xl border border-shop-teal/20 bg-shop-tealLight/40 px-4 py-3 text-slate-800 font-medium leading-snug"
              >
                {h}
              </li>
            ))}
          </ul>
        </section>
      )}

      {steps.length > 0 && (
        <section>
          <h3 className="font-bold text-hades-text text-xl mb-4">체험 상세</h3>
          <ol className="space-y-4">
            {steps.map((s, i) => (
              <li
                key={i}
                className="rounded-2xl border border-hades-line bg-white p-5 shadow-sm flex gap-4"
              >
                <span className="shrink-0 w-10 h-10 rounded-full bg-shop-teal text-white font-bold flex items-center justify-center text-sm">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    {s.time ? (
                      <span className="text-sm font-bold text-shop-tealDark tabular-nums">
                        {s.time}
                      </span>
                    ) : null}
                    <h4 className="font-bold text-hades-text text-lg">{s.title}</h4>
                  </div>
                  <p className="mt-2 text-slate-700 leading-relaxed whitespace-pre-wrap">
                    {s.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

/** 이용 안내 탭 — 환불·만남장소·주의 등 */
export function ListingUsageGuideSections({
  guide,
  listing,
}: {
  guide: ListingGuide | null | undefined;
  listing?: Listing;
}) {
  if (!guide) {
    return (
      <GuideCard icon="📋" title="이용 안내" variant="cream">
        <p className="text-hades-muted text-base">
          이용 안내가 준비 중입니다. 궁금한 점은 판매자에게 문의해 주세요.
        </p>
      </GuideCard>
    );
  }

  const isMarketProduct =
    !!listing && listing.kind === "product" && listing.category !== "experience";

  // 마켓 상품에는 「만남 장소」, 「인근 관광지」가 어울리지 않으므로 숨긴다.
  const showMeeting = !isMarketProduct && !!guide.meeting_place;
  const showNearby = !isMarketProduct && !!guide.nearby && guide.nearby.length > 0;
  const includedTitle = isMarketProduct ? "함께 보내는 것" : "포함 사항";
  const notIncludedTitle = isMarketProduct ? "포함되지 않은 것" : "불포함 사항";
  const precautionsTitle = isMarketProduct ? "보관·취급 안내" : "유의 사항";

  const hasLists =
    (guide.included?.length ?? 0) > 0 ||
    (guide.not_included?.length ?? 0) > 0 ||
    (guide.precautions?.length ?? 0) > 0;

  return (
    <div className="space-y-5 sm:space-y-6">
      {showMeeting ? (
        <GuideCard
          icon="📍"
          title="만남 장소"
          subtitle={guide.address || undefined}
          variant="default"
        >
          <p className="text-base sm:text-lg leading-relaxed">{guide.meeting_place}</p>
        </GuideCard>
      ) : null}

      {hasLists ? (
        <div className="grid gap-5 sm:gap-6 lg:grid-cols-2">
          {(guide.included?.length ?? 0) > 0 ? (
            <GuideCard icon="✅" title={includedTitle} variant="teal">
              <CheckList items={guide.included ?? []} tone="included" />
            </GuideCard>
          ) : null}
          {(guide.not_included?.length ?? 0) > 0 ? (
            <GuideCard icon="🚫" title={notIncludedTitle} variant="default">
              <CheckList items={guide.not_included ?? []} tone="excluded" />
            </GuideCard>
          ) : null}
        </div>
      ) : null}

      {(guide.precautions?.length ?? 0) > 0 ? (
        <GuideCard icon="⚠️" title={precautionsTitle} variant="cream">
          <CheckList items={guide.precautions ?? []} tone="caution" />
        </GuideCard>
      ) : null}

      {guide.refund_policy ? (
        <GuideCard icon="🔄" title="교환 · 반품 · 환불" variant="highlight">
          <p className="text-base sm:text-lg leading-relaxed whitespace-pre-wrap">
            {guide.refund_policy}
          </p>
        </GuideCard>
      ) : null}

      {showNearby ? (
        <section className="space-y-4">
          <div className="flex items-center gap-3 px-1">
            <span className="text-2xl" aria-hidden>
              🗺️
            </span>
            <h3 className="font-bold text-hades-text text-xl">인근 관광지</h3>
          </div>
          <ul className="grid gap-4 sm:grid-cols-2">
            {(guide.nearby ?? []).map((spot, i) => (
              <li
                key={i}
                className="rounded-2xl border border-brand-line bg-white p-5 sm:p-6 shadow-soft overflow-visible"
              >
                <h4 className="font-bold text-lg text-hades-text leading-snug">{spot.name}</h4>
                <dl className="mt-3 space-y-2 text-sm sm:text-base text-slate-700">
                  {spot.address ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-hades-muted">주소</dt>
                      <dd>{spot.address}</dd>
                    </div>
                  ) : null}
                  {spot.hours ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-hades-muted">이용</dt>
                      <dd>{spot.hours}</dd>
                    </div>
                  ) : null}
                  {spot.holiday ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-hades-muted">휴일</dt>
                      <dd>{spot.holiday}</dd>
                    </div>
                  ) : null}
                  {spot.parking ? (
                    <div className="flex gap-2">
                      <dt className="shrink-0 font-semibold text-hades-muted">주차</dt>
                      <dd>{spot.parking}</dd>
                    </div>
                  ) : null}
                </dl>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
