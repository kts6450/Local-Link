import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { Listing } from "../types";

function LocalGuideSkeleton() {
  return (
    <div className="grid gap-5 sm:gap-6 lg:grid-cols-2 animate-pulse">
      {[0, 1].map((i) => (
        <div
          key={i}
          className="rounded-2xl border border-brand-line bg-white/60 p-6 sm:p-7 space-y-4"
        >
          <div className="flex gap-4">
            <div className="h-12 w-12 rounded-2xl bg-brand-warm" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="h-5 w-32 rounded-lg bg-brand-warm" />
              <div className="h-4 w-24 rounded-lg bg-brand-warm/80" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-4 w-full rounded bg-brand-warm/70" />
            <div className="h-4 w-5/6 rounded bg-brand-warm/70" />
          </div>
        </div>
      ))}
    </div>
  );
}

function SeasonBadge({ season }: { season?: string }) {
  if (!season) return null;
  const icons: Record<string, string> = {
    봄: "🌸",
    여름: "☀️",
    가을: "🍂",
    겨울: "❄️",
  };
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-sm font-semibold text-shop-tealDark shadow-soft ring-1 ring-shop-teal/10">
      <span aria-hidden>{icons[season] ?? "🗓️"}</span>
      {season} 시즌
    </span>
  );
}

export function ListingLocalGuide({ listing }: { listing: Listing }) {
  const [loading, setLoading] = useState(true);
  const [tourism, setTourism] = useState<Record<string, unknown> | null>(null);
  const [weather, setWeather] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getListingLocalGuide(listing.id)
      .then((r) => {
        setTourism(r.tourism);
        setWeather(r.weather);
      })
      .catch(() => {
        setTourism(null);
        setWeather(null);
      })
      .finally(() => setLoading(false));
  }, [listing.id]);

  return (
    <section className="pt-2 sm:pt-4 overflow-visible">
      <div className="flex items-center gap-3 mb-5 sm:mb-6 px-0.5">
        <span className="h-px flex-1 bg-gradient-to-r from-transparent via-brand-line to-transparent" />
        <h2 className="shrink-0 text-sm font-bold uppercase tracking-wider text-hades-muted">
          지역 · 시즌
        </h2>
        <span className="h-px flex-1 bg-gradient-to-r from-transparent via-brand-line to-transparent" />
      </div>

      {loading ? (
        <LocalGuideSkeleton />
      ) : (
        <div className="grid gap-5 sm:gap-6 lg:grid-cols-2 pb-2">
          {/* 이 지역 둘러보기 */}
          <article className="rounded-2xl border border-shop-teal/15 bg-gradient-to-br from-shop-tealLight/80 to-emerald-50/40 p-6 sm:p-7 shadow-soft overflow-visible">
            <div className="flex items-start gap-4 mb-5">
              <span
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/90 text-2xl shadow-soft"
                aria-hidden
              >
                🗺️
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="font-bold text-shop-tealDark text-lg sm:text-xl leading-snug">
                  이 지역 둘러보기
                </h3>
                <p className="mt-1 text-sm sm:text-base text-hades-muted">
                  {String(tourism?.location ?? listing.location)}
                </p>
              </div>
            </div>
            <ul className="space-y-3">
              {((tourism?.highlights as string[] | undefined) ?? []).length > 0 ? (
                (tourism?.highlights as string[]).map((h, i) => (
                  <li
                    key={i}
                    className="flex gap-3 rounded-xl bg-white/75 border border-white/90 px-4 py-3.5 text-[0.98rem] sm:text-base leading-relaxed"
                  >
                    <span className="text-shop-teal font-bold shrink-0" aria-hidden>
                      •
                    </span>
                    <span>{h}</span>
                  </li>
                ))
              ) : (
                <li className="rounded-xl bg-white/75 border border-white/90 px-4 py-3.5 text-hades-muted text-base leading-relaxed">
                  {listing.location} 주변 명소·축제·체험 정보를 확인해 보세요.
                </li>
              )}
            </ul>
            {tourism?.seller_tip ? (
              <p className="mt-4 rounded-xl bg-white/60 px-4 py-3 text-sm sm:text-base text-slate-600 leading-relaxed">
                💡 {String(tourism.seller_tip)}
              </p>
            ) : null}
          </article>

          {/* 지금 이 시기에 */}
          <article className="rounded-2xl border border-brand-line bg-gradient-to-br from-brand-cream to-brand-warm/70 p-6 sm:p-7 shadow-soft overflow-visible">
            <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
              <div className="flex items-start gap-4 min-w-0">
                <span
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/90 text-2xl shadow-soft"
                  aria-hidden
                >
                  🌿
                </span>
                <div>
                  <h3 className="font-bold text-hades-text text-lg sm:text-xl leading-snug">
                    지금 이 시기에
                  </h3>
                  {weather?.season ? (
                    <p className="mt-1 text-sm text-hades-muted">
                      {String(weather.month)}월 · {String(weather.season)}
                    </p>
                  ) : null}
                </div>
              </div>
              <SeasonBadge season={weather?.season as string | undefined} />
            </div>

            {weather?.summary ? (
              <div className="space-y-3">
                <p className="text-base sm:text-lg text-slate-800 leading-relaxed">
                  {String(weather.summary)}
                </p>
                {weather.regional_note ? (
                  <p className="rounded-xl bg-white/70 border border-white/80 px-4 py-3.5 text-[0.98rem] sm:text-base text-slate-700 leading-relaxed">
                    {String(weather.regional_note)}
                  </p>
                ) : null}
                {weather.caution ? (
                  <p className="text-xs sm:text-sm text-slate-500 leading-relaxed pt-1">
                    {String(weather.caution)}
                  </p>
                ) : null}
              </div>
            ) : (
              <p className="rounded-xl bg-white/70 border border-white/80 px-4 py-3.5 text-base text-slate-600 leading-relaxed">
                {listing.location} 지역의 수확·행사·날씨 정보를 곧 업데이트할 예정입니다.
              </p>
            )}
          </article>
        </div>
      )}
    </section>
  );
}
