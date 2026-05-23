import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { PageHeader } from "../../components/ui/PageHeader";
import { LocalLinkLogo } from "../../components/brand/LocalLinkLogo";
import { api } from "../../lib/api";
import { useAuthRole } from "../../store/auth";

type Tab = "stats" | "users" | "listings";

interface StatRow {
  label: string;
  value: string;
  hint?: string;
}

export function AdminPage() {
  const role = useAuthRole();
  const [tab, setTab] = useState<Tab>("stats");
  const [stats, setStats] = useState<Awaited<ReturnType<typeof api.adminStats>> | null>(null);
  const [users, setUsers] = useState<Awaited<ReturnType<typeof api.adminListUsers>>>([]);
  const [listings, setListings] = useState<Awaited<ReturnType<typeof api.adminListAllListings>>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (role !== "master") return;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        if (tab === "stats" && !stats) setStats(await api.adminStats());
        if (tab === "users") setUsers(await api.adminListUsers());
        if (tab === "listings") setListings(await api.adminListAllListings());
      } catch (e) {
        setError(e instanceof Error ? e.message : "불러오기 실패");
      } finally {
        setLoading(false);
      }
    })();
  }, [tab, role, stats]);

  if (role !== "master") {
    return <Navigate to="/" replace />;
  }

  const tabCls = (t: Tab) =>
    [
      "px-4 py-2 rounded-xl text-sm font-semibold transition-colors",
      tab === t
        ? "bg-shop-teal text-white shadow-sm"
        : "text-hades-muted hover:bg-shop-tealLight hover:text-shop-tealDark",
    ].join(" ");

  const removeUser = async (uid: string, email: string) => {
    if (!confirm(`${email} 계정을 삭제할까요?`)) return;
    await api.adminDeleteUser(uid);
    setUsers((prev) => prev.filter((u) => u.id !== uid));
  };

  const removeListing = async (id: string, title: string) => {
    if (!confirm(`«${title}»을(를) 삭제할까요?`)) return;
    await api.adminDeleteListing(id);
    setListings((prev) => prev.filter((l) => l.id !== id));
  };

  const statRows: StatRow[] = stats
    ? [
        { label: "회원", value: `${stats.users.toLocaleString()}명`, hint: `구매자 ${stats.consumers} · 공급자 ${stats.sellers}` },
        { label: "등록 상품", value: `${stats.listings.toLocaleString()}건` },
        { label: "주문", value: `${stats.orders.toLocaleString()}건`, hint: `결제 완료 ${stats.paid_orders}` },
        { label: "누적 매출", value: `${stats.revenue.toLocaleString()}원`, hint: "결제 완료 주문 합계" },
        { label: "리뷰", value: `${stats.reviews.toLocaleString()}개` },
      ]
    : [];

  return (
    <div className="min-h-screen bg-brand-cream">
      <header className="bg-white border-b border-hades-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="no-underline text-inherit">
              <LocalLinkLogo size="sm" />
            </Link>
            <span className="text-xs font-bold text-white bg-rose-600 px-2.5 py-1 rounded-full">
              운영자
            </span>
          </div>
          <div className="flex gap-3 text-sm">
            <Link to="/" className="text-hades-muted hover:text-hades-text">
              쇼핑몰
            </Link>
            <Link to="/seller/products" className="text-hades-muted hover:text-hades-text">
              셀러오피스
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <PageHeader badge="운영" title="어드민">
          전체 회원·상품·주문을 관리합니다.
        </PageHeader>

        <nav className="flex gap-2 flex-wrap">
          <button type="button" className={tabCls("stats")} onClick={() => setTab("stats")}>
            통계
          </button>
          <button type="button" className={tabCls("users")} onClick={() => setTab("users")}>
            회원
          </button>
          <button type="button" className={tabCls("listings")} onClick={() => setTab("listings")}>
            상품
          </button>
        </nav>

        {error ? (
          <p className="rounded-xl bg-red-50 border border-red-100 text-red-800 px-4 py-3">{error}</p>
        ) : null}

        {tab === "stats" && (
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {loading && !stats ? (
              <p className="text-hades-muted">불러오는 중…</p>
            ) : (
              statRows.map((r) => (
                <div key={r.label} className="card p-5">
                  <p className="text-sm text-hades-muted">{r.label}</p>
                  <p className="mt-2 text-3xl font-bold text-hades-text tabular-nums">{r.value}</p>
                  {r.hint ? <p className="mt-1 text-xs text-hades-muted">{r.hint}</p> : null}
                </div>
              ))
            )}
          </section>
        )}

        {tab === "users" && (
          <section className="card overflow-hidden p-0">
            {loading && users.length === 0 ? (
              <p className="p-6 text-hades-muted">불러오는 중…</p>
            ) : users.length === 0 ? (
              <p className="p-6 text-hades-muted">가입된 회원이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-hades-muted">
                    <tr>
                      <th className="px-4 py-3">이메일</th>
                      <th className="px-4 py-3">이름</th>
                      <th className="px-4 py-3">역할</th>
                      <th className="px-4 py-3">업종</th>
                      <th className="px-4 py-3">가입일</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-t border-hades-line">
                        <td className="px-4 py-3 font-mono text-xs">{u.email}</td>
                        <td className="px-4 py-3">{u.display_name}</td>
                        <td className="px-4 py-3">
                          <span
                            className={
                              u.role === "seller"
                                ? "rounded-full bg-shop-tealLight px-2 py-0.5 text-xs font-semibold text-shop-tealDark"
                                : "rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700"
                            }
                          >
                            {u.role === "seller" ? "공급자" : "구매자"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-hades-muted">{u.seller_sector ?? "—"}</td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {u.created_at.slice(0, 10)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className="text-sm text-red-600 font-semibold hover:underline"
                            onClick={() => void removeUser(u.id, u.email)}
                          >
                            삭제
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {tab === "listings" && (
          <section className="card overflow-hidden p-0">
            {loading && listings.length === 0 ? (
              <p className="p-6 text-hades-muted">불러오는 중…</p>
            ) : listings.length === 0 ? (
              <p className="p-6 text-hades-muted">등록된 상품이 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-hades-muted">
                    <tr>
                      <th className="px-4 py-3">상품</th>
                      <th className="px-4 py-3">분류</th>
                      <th className="px-4 py-3">가격</th>
                      <th className="px-4 py-3">공급자</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {listings.map((l) => (
                      <tr key={l.id} className="border-t border-hades-line">
                        <td className="px-4 py-3">
                          <Link to={`/listing/${l.id}`} className="font-semibold hover:underline">
                            {l.title}
                          </Link>
                          <p className="text-xs text-hades-muted">{l.location}</p>
                        </td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {l.kind} · {l.category}
                        </td>
                        <td className="px-4 py-3 tabular-nums">{l.price.toLocaleString()}원</td>
                        <td className="px-4 py-3 text-xs text-hades-muted">
                          {l.seller_email ?? l.seller_id}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className="text-sm text-red-600 font-semibold hover:underline"
                            onClick={() => void removeListing(l.id, l.title)}
                          >
                            삭제
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
