import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { SellerListingCard } from "../../components/seller/SellerListingCard";
import { useListingsPoll } from "../../hooks/useListingsPoll";
import { api } from "../../lib/api";
import { listingToTab, LISTING_TABS, type ListingTab } from "../../lib/listingTabs";
import { useAuthSellerId } from "../../store/auth";

type Stats = Awaited<ReturnType<typeof api.getSellerDashboard>>;

export function SellerDashboardPage() {
  const sellerId = useAuthSellerId();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get("tab") as ListingTab | null) ?? "product";
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const { listings, loading: listingsLoading } = useListingsPoll();

  useEffect(() => {
    api
      .getSellerDashboard()
      .then(setStats)
      .catch((e) => setStatsError(e instanceof Error ? e.message : "불러오기 실패"))
      .finally(() => setStatsLoading(false));
  }, []);

  const myListings = useMemo(() => {
    const mine = sellerId ? listings.filter((l) => l.seller_id === sellerId) : listings;
    const q = query.trim().toLowerCase();
    return mine.filter((l) => {
      if (listingToTab(l) !== tab) return false;
      if (!q) return true;
      return (
        l.title.toLowerCase().includes(q) ||
        l.location.toLowerCase().includes(q) ||
        l.description.toLowerCase().includes(q)
      );
    });
  }, [listings, sellerId, tab, query]);

  const counts = useMemo(() => {
    const mine = sellerId ? listings.filter((l) => l.seller_id === sellerId) : listings;
    return LISTING_TABS.reduce(
      (acc, t) => {
        acc[t.id] = mine.filter((l) => listingToTab(l) === t.id).length;
        return acc;
      },
      {} as Record<ListingTab, number>
    );
  }, [listings, sellerId]);

  const setTab = (next: ListingTab) => {
    const p = new URLSearchParams(searchParams);
    p.set("tab", next);
    setSearchParams(p);
  };

  if (statsLoading) {
    return <p className="py-16 text-center text-hades-muted">불러오는 중…</p>;
  }
  if (statsError || !stats) {
    return (
      <p className="rounded-2xl bg-red-50 border border-red-100 text-red-800 px-4 py-3">
        {statsError ?? "데이터 없음"}
      </p>
    );
  }

  return (
    <div className="space-y-8 sm:space-y-10">
      <header>
        <h1 className="text-3xl sm:text-4xl font-bold text-brand-ink tracking-tight">
          판매자 대시보드
        </h1>
        <p className="mt-2 text-hades-muted">한눈에 보는 오늘의 판매 현황</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="card p-6 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-warm text-xl">
            🛒
          </span>
          <div>
            <p className="text-sm text-hades-muted">오늘 주문</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {stats.today_order_count}
              <span className="text-lg font-semibold ml-0.5">건</span>
            </p>
          </div>
        </div>
        <div className="card p-6 sm:-mt-1 sm:mb-1 sm:shadow-lg flex items-start gap-4 border-brand-ink/10">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-xl">
            💰
          </span>
          <div>
            <p className="text-sm text-hades-muted">오늘 매출</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {stats.today_revenue.toLocaleString()}
              <span className="text-lg font-semibold">원</span>
            </p>
          </div>
        </div>
        <div className="card p-6 flex items-start gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-xl">
            ⏱
          </span>
          <div>
            <p className="text-sm text-hades-muted">처리 대기</p>
            <p className="mt-1 text-3xl font-bold text-brand-ink tabular-nums">
              {stats.pending_count}
              <span className="text-lg font-semibold ml-0.5">건</span>
            </p>
          </div>
        </div>
      </section>

      <section className="card p-4 sm:p-5">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex flex-wrap gap-2">
            {LISTING_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={
                  tab === t.id
                    ? "rounded-full bg-brand-ink text-white text-sm font-bold px-4 py-2"
                    : "rounded-full border border-brand-line bg-white text-sm font-semibold px-4 py-2 text-hades-muted hover:bg-brand-warm"
                }
              >
                {t.label} {counts[t.id]}
              </button>
            ))}
          </div>
          <div className="flex flex-1 gap-3 lg:justify-end">
            <label className="relative flex-1 max-w-md">
              <span className="sr-only">검색</span>
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-hades-muted">🔍</span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="상품명이나 지역으로 검색"
                className="w-full rounded-full border border-brand-line bg-brand-cream/50 pl-11 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-ink/20"
              />
            </label>
            <Link
              to="/seller/products"
              className="hidden sm:inline-flex items-center rounded-full bg-brand-ink text-white text-sm font-bold px-5 py-2.5 hover:bg-brand-ink/90 shrink-0"
            >
              + 새로 등록
            </Link>
          </div>
        </div>
      </section>

      {listingsLoading ? (
        <p className="py-16 text-center text-hades-muted">상품 불러오는 중…</p>
      ) : myListings.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-lg font-semibold text-brand-ink">등록된 {LISTING_TABS.find((t) => t.id === tab)?.label}이 없습니다</p>
          <p className="mt-2 text-sm text-hades-muted">음성이나 OCR로 첫 상품을 등록해 보세요.</p>
          <Link to="/seller/products" className="inline-block mt-6 btn-primary">
            + 새로 등록
          </Link>
        </div>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {myListings.map((listing) => (
            <li key={listing.id}>
              <SellerListingCard
                listing={listing}
                salesCount={stats.sales_by_listing?.[listing.id] ?? 0}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
