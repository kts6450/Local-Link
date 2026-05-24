import { useSearchParams } from "react-router-dom";

import { HeroCarousel } from "../components/shop/HeroCarousel";
import { ShopListingCard } from "../components/shop/ShopListingCard";
import { BestListings } from "../components/shop/BestListings";
import { LandingFeatures } from "../components/marketing/LandingFeatures";
import { LandingMission } from "../components/marketing/LandingMission";
import { LandingReviews } from "../components/marketing/LandingReviews";
import { useListingsPoll } from "../hooks/useListingsPoll";
import {
  filterShopListings,
  parseShopFilters,
  sectionTitle,
  shopSearchParams,
} from "../lib/shopNavigation";
import { useCart } from "../store/cart";

export function ShopPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = parseShopFilters(`?${searchParams.toString()}`);
  const { listings, loading } = useListingsPoll();
  const add = useCart((s) => s.add);

  const filtered = filterShopListings(listings, filters);
  const title = sectionTitle(filters);
  const isLandingView =
    filters.kind === "all" &&
    filters.theme === "all" &&
    !filters.tab &&
    !filters.query &&
    !filters.minPrice &&
    !filters.maxPrice;

  const setQuick = (patch: Partial<typeof filters>) => {
    const qs = shopSearchParams({ ...filters, ...patch });
    setSearchParams(qs ? new URLSearchParams(qs.slice(1)) : {});
  };

  return (
    <div className="page-shell pt-6 sm:pt-8 pb-16 sm:pb-24 space-y-12 sm:space-y-16 lg:space-y-20">
      <HeroCarousel listings={listings} />

      <section>
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-8 sm:mb-10">
          <div>
            <p className="eyebrow mb-3">Discover Local</p>
            <h2 className="display-2 text-balance">
              {isLandingView ? "지역 특산품 둘러보기" : title}
            </h2>
            {isLandingView ? (
              <p className="mt-3 text-base sm:text-lg text-hades-muted max-w-xl leading-relaxed">
                전국 농어촌 판매자가 직접 올린 신선한 상품을 만나보세요.
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2 text-sm text-hades-muted">
            <span className="hidden sm:inline">총</span>
            <span className="font-bold text-brand-ink tabular-nums">{filtered.length}</span>
            <span>개 상품</span>
          </div>
        </div>

        <div className="rounded-[1.75rem] border border-brand-line/80 bg-white p-4 sm:p-5 mb-10 shadow-soft">
          <div className="flex flex-col lg:flex-row lg:items-center gap-4">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setQuick({ kind: "all", theme: "all", tab: null })}
                className={
                  filters.kind === "all" && filters.theme === "all" && !filters.tab
                    ? "chip-active"
                    : "chip"
                }
              >
                전체
              </button>
              <button
                type="button"
                onClick={() => setQuick({ kind: "product", theme: "market", tab: null })}
                className={filters.theme === "market" ? "chip-active" : "chip"}
              >
                특산
              </button>
              <button
                type="button"
                onClick={() => setQuick({ kind: "lodging", theme: "lodging", tab: null })}
                className={filters.kind === "lodging" ? "chip-active" : "chip"}
              >
                스테이
              </button>
              <button
                type="button"
                onClick={() =>
                  setQuick({ kind: "product", theme: "experience", tab: null })
                }
                className={filters.theme === "experience" ? "chip-active" : "chip"}
              >
                체험
              </button>
            </div>
            <label className="relative flex-1 lg:max-w-2xl">
              <span className="sr-only">검색</span>
              <span className="absolute left-5 top-1/2 -translate-y-1/2 text-hades-muted">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
              </span>
              <input
                type="search"
                placeholder="상품명이나 지역으로 검색"
                className="w-full rounded-full border border-brand-line bg-brand-cream/60 pl-12 pr-5 py-3.5 text-base placeholder:text-hades-muted/70 focus:outline-none focus:ring-2 focus:ring-brand-ink/15 focus:border-brand-ink/30 focus:bg-white transition-colors"
                defaultValue={filters.query ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  window.clearTimeout((window as any).__shopQTimer);
                  (window as any).__shopQTimer = window.setTimeout(
                    () => setQuick({ query: v }),
                    200
                  );
                }}
              />
            </label>
          </div>
        </div>

        {loading ? (
          <div className="py-24 flex flex-col items-center gap-4 text-hades-muted">
            <span className="h-12 w-12 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
            <p className="text-base font-medium">불러오는 중…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-16 text-center">
            <p className="text-2xl font-bold text-brand-ink">이 조건에 맞는 상품이 없습니다</p>
            <p className="mt-3 text-base text-hades-muted">검색어나 필터를 바꿔보세요.</p>
            <button
              type="button"
              className="btn-primary mt-8"
              onClick={() => setQuick({ kind: "all", theme: "all", tab: null })}
            >
              전체 보기
            </button>
          </div>
        ) : (
          <ul className="grid gap-6 sm:gap-7 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {filtered.map((item, i) => (
              <li
                key={item.id}
                className="reveal"
                style={{ animationDelay: `${Math.min(i, 12) * 50}ms` }}
              >
                <ShopListingCard listing={item} onAdd={(id) => add(id, 1)} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {isLandingView && !loading ? (
        <>
          <BestListings />
          <LandingFeatures />
          <LandingMission />
          <LandingReviews />
        </>
      ) : null}
    </div>
  );
}
