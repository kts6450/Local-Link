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
  const steps = g?.steps ?? [];

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-hades-line bg-slate-50/80 p-5 sm:p-6">
        <p className="text-slate-700 text-lg leading-relaxed whitespace-pre-wrap">
          {listing.description || "상세 설명이 곧 추가됩니다."}
        </p>
      </div>

      {g?.highlights && g.highlights.length > 0 && (
        <section>
          <h3 className="font-bold text-hades-text text-xl mb-4">체험 포인트</h3>
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
export function ListingUsageGuideSections({ guide }: { guide: ListingGuide | null | undefined }) {
  if (!guide) {
    return (
      <GuideCard icon="📋" title="이용 안내" variant="cream">
        <p className="text-hades-muted text-base">
          이용 안내가 준비 중입니다. 궁금한 점은 판매자에게 문의해 주세요.
        </p>
      </GuideCard>
    );
  }

  const hasLists =
    (guide.included?.length ?? 0) > 0 ||
    (guide.not_included?.length ?? 0) > 0 ||
    (guide.precautions?.length ?? 0) > 0;

  return (
    <div className="space-y-5 sm:space-y-6">
      {guide.meeting_place ? (
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
            <GuideCard icon="✅" title="포함 사항" variant="teal">
              <CheckList items={guide.included ?? []} tone="included" />
            </GuideCard>
          ) : null}
          {(guide.not_included?.length ?? 0) > 0 ? (
            <GuideCard icon="🚫" title="불포함 사항" variant="default">
              <CheckList items={guide.not_included ?? []} tone="excluded" />
            </GuideCard>
          ) : null}
        </div>
      ) : null}

      {(guide.precautions?.length ?? 0) > 0 ? (
        <GuideCard icon="⚠️" title="유의 사항" variant="cream">
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

      {guide.nearby && guide.nearby.length > 0 ? (
        <section className="space-y-4">
          <div className="flex items-center gap-3 px-1">
            <span className="text-2xl" aria-hidden>
              🗺️
            </span>
            <h3 className="font-bold text-hades-text text-xl">인근 관광지</h3>
          </div>
          <ul className="grid gap-4 sm:grid-cols-2">
            {guide.nearby.map((spot, i) => (
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
