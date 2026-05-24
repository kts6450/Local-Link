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
    return (
      <div className="py-24 flex flex-col items-center gap-4 text-hades-muted">
        <span className="h-12 w-12 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
        <p className="text-base font-medium">불러오는 중…</p>
      </div>
    );
  }
  if (statsError || !stats) {
    return (
      <p className="rounded-2xl bg-rose-50 border border-rose-100 text-rose-800 px-5 py-4 text-base">
        {statsError ?? "데이터 없음"}
      </p>
    );
  }

  return (
    <div className="space-y-10 sm:space-y-12">
      <header className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="eyebrow mb-3">Seller Dashboard</p>
          <h1 className="display-2 text-balance">판매자 대시보드</h1>
          <p className="mt-3 text-base sm:text-lg text-hades-muted">
            한눈에 보는 오늘의 판매 현황
          </p>
        </div>
        <div className="text-sm text-hades-muted">
          {new Date().toLocaleDateString("ko-KR", {
            year: "numeric",
            month: "long",
            day: "numeric",
            weekday: "long",
          })}
        </div>
      </header>

      <section className="grid gap-5 sm:grid-cols-3">
        <article className="stat-card">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-warm text-2xl shrink-0">
            🛒
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-hades-muted">오늘 주문</p>
            <p className="mt-1 text-3xl sm:text-4xl font-bold text-brand-ink tabular-nums tracking-tight">
              {stats.today_order_count}
              <span className="text-lg font-semibold ml-1 text-hades-muted">건</span>
            </p>
          </div>
        </article>
        <article className="stat-card border-brand-ink/10 ring-1 ring-brand-ink/5">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-2xl shrink-0">
            💰
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-hades-muted">오늘 매출</p>
            <p className="mt-1 text-3xl sm:text-4xl font-bold text-brand-ink tabular-nums tracking-tight">
              {stats.today_revenue.toLocaleString()}
              <span className="text-lg font-semibold ml-1 text-hades-muted">원</span>
            </p>
          </div>
        </article>
        <article className="stat-card">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-50 text-2xl shrink-0">
            ⏱
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-hades-muted">처리 대기</p>
            <p className="mt-1 text-3xl sm:text-4xl font-bold text-brand-ink tabular-nums tracking-tight">
              {stats.pending_count}
              <span className="text-lg font-semibold ml-1 text-hades-muted">건</span>
            </p>
          </div>
        </article>
      </section>

      <section className="rounded-[1.75rem] border border-brand-line/80 bg-white p-4 sm:p-5 shadow-soft">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex flex-wrap gap-2">
            {LISTING_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={
                  tab === t.id
                    ? "rounded-full bg-brand-ink text-white text-sm font-bold px-5 py-2.5 shadow-soft transition-all"
                    : "rounded-full border border-brand-line bg-white text-sm font-semibold px-5 py-2.5 text-hades-muted hover:bg-brand-warm hover:text-brand-ink transition-all"
                }
              >
                {t.label}
                <span
                  className={`ml-2 inline-flex items-center justify-center min-w-[1.4rem] h-5 px-1.5 rounded-full text-[11px] font-bold tabular-nums ${
                    tab === t.id ? "bg-white/20 text-white" : "bg-brand-warm text-brand-ink/70"
                  }`}
                >
                  {counts[t.id]}
                </span>
              </button>
            ))}
          </div>
          <div className="flex flex-1 gap-3 lg:justify-end">
            <label className="relative flex-1 max-w-md">
              <span className="sr-only">검색</span>
              <span className="absolute left-5 top-1/2 -translate-y-1/2 text-hades-muted">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
              </span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="상품명이나 지역으로 검색"
                className="w-full rounded-full border border-brand-line bg-brand-cream/50 pl-12 pr-5 py-3 text-base placeholder:text-hades-muted/70 focus:outline-none focus:ring-2 focus:ring-brand-ink/15 focus:border-brand-ink/30 focus:bg-white transition-colors"
              />
            </label>
          </div>
        </div>
      </section>

      {listingsLoading ? (
        <div className="py-20 flex flex-col items-center gap-3 text-hades-muted">
          <span className="h-10 w-10 rounded-full border-2 border-brand-ink border-t-transparent animate-spin" />
          <p>상품 불러오는 중…</p>
        </div>
      ) : myListings.length === 0 ? (
        <div className="card p-16 text-center">
          <p className="text-2xl font-bold text-brand-ink">
            등록된 {LISTING_TABS.find((t) => t.id === tab)?.label}이 없습니다
          </p>
          <p className="mt-3 text-base text-hades-muted">
            음성이나 OCR로 첫 상품을 등록해 보세요.
          </p>
          <Link to="/seller/products" className="inline-flex mt-8 btn-primary">
            <span aria-hidden>+</span> 새로 등록
          </Link>
        </div>
      ) : (
        <ul className="grid gap-6 sm:gap-7 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
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
