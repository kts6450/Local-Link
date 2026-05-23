import { useSearchParams } from "react-router-dom";

import { HeroCarousel } from "../components/shop/HeroCarousel";
import { ShopListingCard } from "../components/shop/ShopListingCard";
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
    <div className="page-shell space-y-10 sm:space-y-12 py-6 sm:py-8">
      <HeroCarousel listings={listings} />

      <section>
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl sm:text-3xl font-bold text-brand-ink tracking-tight">
              {isLandingView ? "지역 특산품 둘러보기" : title}
            </h2>
            {isLandingView ? (
              <p className="mt-1 text-hades-muted">전국 농어촌의 신선한 상품을 만나보세요</p>
            ) : null}
          </div>
        </div>

        <div className="card p-4 sm:p-5 mb-8">
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
                onClick={() => setQuick({ kind: "product", theme: "rural", tab: null })}
                className={filters.theme === "rural" && filters.kind === "product" ? "chip-active" : "chip"}
              >
                특산·상품
              </button>
              <button
                type="button"
                onClick={() => setQuick({ kind: "lodging", theme: "lodging", tab: null })}
                className={filters.kind === "lodging" ? "chip-active" : "chip"}
              >
                숙박
              </button>
              <button
                type="button"
                onClick={() =>
                  setQuick({ kind: "product", theme: "experience", tab: "experience" })
                }
                className={filters.theme === "experience" ? "chip-active" : "chip"}
              >
                체험
              </button>
            </div>
            <label className="relative flex-1 lg:max-w-xl">
              <span className="sr-only">검색</span>
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-hades-muted">🔍</span>
              <input
                type="search"
                placeholder="상품명이나 지역으로 검색"
                className="w-full rounded-full border border-brand-line bg-brand-cream/60 pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-ink/20"
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
          <div className="py-20 flex flex-col items-center gap-3 text-hades-muted">
            <span className="h-10 w-10 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
            <p>불러오는 중…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-12 text-center text-hades-muted">
            <p className="text-lg font-semibold text-brand-ink">이 조건에 맞는 상품이 없습니다</p>
            <button
              type="button"
              className="mt-4 btn-primary text-sm"
              onClick={() => setQuick({ kind: "all", theme: "all", tab: null })}
            >
              전체 보기
            </button>
          </div>
        ) : (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {filtered.map((item) => (
              <li key={item.id}>
                <ShopListingCard listing={item} onAdd={(id) => add(id, 1)} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
