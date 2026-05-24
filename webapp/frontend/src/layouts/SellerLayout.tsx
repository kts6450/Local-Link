import { Link, NavLink, Outlet, useSearchParams } from "react-router-dom";

import { RequireRole } from "../components/RequireRole";
import { LocalLinkLogo } from "../components/brand/LocalLinkLogo";
import { FontSizeToggle } from "../components/FontSizeToggle";
import { LISTING_TABS, type ListingTab } from "../lib/listingTabs";
import { categoryLabel } from "../lib/sellerSectors";
import {
  useAuth,
  useAuthDisplayName,
  useAuthRole,
  useAuthSellerSector,
} from "../store/auth";

const sectorPill =
  "px-6 py-2.5 rounded-full text-sm sm:text-base font-bold transition-all whitespace-nowrap";
const sectorOn = `${sectorPill} bg-brand-ink text-white shadow-soft`;
const sectorOff = `${sectorPill} text-hades-muted hover:bg-white hover:text-brand-ink`;

const navLink = "text-sm font-semibold transition-colors whitespace-nowrap px-3 py-1.5 rounded-full";
const navOn = `${navLink} text-brand-ink bg-brand-warm`;
const navOff = `${navLink} text-hades-muted hover:text-brand-ink hover:bg-brand-warm/60`;

export function SellerLayout() {
  const displayName = useAuthDisplayName();
  const logout = useAuth((s) => s.logout);
  const sellerSector = useAuthSellerSector();
  const role = useAuthRole();
  const [searchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as ListingTab | null) ?? "product";

  return (
    <RequireRole role="seller">
      <div className="min-h-screen flex flex-col bg-brand-cream">
        <header className="sticky top-0 z-40 bg-brand-cream/85 backdrop-blur-xl border-b border-brand-line/60">
          <div className="page-shell h-[72px] sm:h-[84px] flex items-center justify-between gap-4 lg:gap-8">
            <Link to="/seller/dashboard" className="shrink-0 no-underline text-inherit">
              <LocalLinkLogo />
            </Link>

            <nav className="hidden lg:flex items-center gap-1 p-1 rounded-full bg-brand-warm border border-brand-line/60">
              {LISTING_TABS.map((t, i) => {
                const active = activeTab === t.id;
                return (
                  <div key={t.id} className="flex items-center">
                    <NavLink
                      to={`/seller/dashboard?tab=${t.id}`}
                      className={active ? sectorOn : sectorOff}
                    >
                      {t.label}
                    </NavLink>
                    {i < LISTING_TABS.length - 1 && !active && (
                      <span className="text-brand-line/70 mx-0.5" aria-hidden>
                        ◆
                      </span>
                    )}
                  </div>
                );
              })}
            </nav>

            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              <Link
                to="/seller/products"
                className="inline-flex items-center gap-1.5 rounded-full bg-brand-ink text-white text-sm sm:text-base font-bold px-5 py-2.5 sm:px-6 sm:py-3 hover:bg-brand-ink/90 active:scale-[0.98] transition-all shadow-soft"
              >
                <span className="text-lg leading-none" aria-hidden>+</span>
                <span>새로 등록</span>
              </Link>
              <span className="hidden 2xl:inline text-xs font-bold text-brand-ink/70 bg-brand-warm px-3 py-1.5 rounded-full">
                {role === "master" ? "운영" : categoryLabel(sellerSector ?? "rural")}
              </span>
              <span className="hidden xl:inline text-sm text-hades-muted">{displayName}님</span>
              <Link
                to="/"
                className="hidden md:inline text-sm font-semibold text-hades-muted hover:text-brand-ink transition-colors"
              >
                쇼핑몰
              </Link>
              <button
                type="button"
                className="hidden sm:inline text-sm text-hades-muted hover:text-brand-ink transition-colors"
                onClick={() => {
                  logout();
                  window.location.href = "/login?role=seller";
                }}
              >
                나가기
              </button>
              <FontSizeToggle variant="seller" />
            </div>
          </div>

          <div className="border-t border-brand-line/60 page-shell">
            <div className="flex items-center justify-between gap-4 py-2.5 overflow-x-auto scrollbar-hide">
              <div className="flex items-center gap-1">
                <NavLink
                  to="/seller/dashboard"
                  end
                  className={({ isActive }) => (isActive ? navOn : navOff)}
                >
                  대시보드
                </NavLink>
                <NavLink
                  to="/seller/products"
                  className={({ isActive }) => (isActive ? navOn : navOff)}
                >
                  상품 등록
                </NavLink>
                <NavLink
                  to="/seller/orders"
                  className={({ isActive }) => (isActive ? navOn : navOff)}
                >
                  주문 · 알림
                </NavLink>
                <NavLink
                  to="/seller/sns"
                  className={({ isActive }) => (isActive ? navOn : navOff)}
                >
                  SNS 홍보
                </NavLink>
                {role === "master" ? (
                  <NavLink
                    to="/admin"
                    className={({ isActive }) => (isActive ? navOn : navOff)}
                  >
                    어드민
                  </NavLink>
                ) : null}
              </div>
              <nav className="lg:hidden flex items-center gap-1 p-1 rounded-full bg-brand-warm border border-brand-line/60 shrink-0">
                {LISTING_TABS.map((t) => (
                  <NavLink
                    key={t.id}
                    to={`/seller/dashboard?tab=${t.id}`}
                    className={activeTab === t.id ? sectorOn : sectorOff}
                  >
                    {t.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          </div>
        </header>

        <main className="flex-1 w-full page-shell py-10 sm:py-14">
          <Outlet />
        </main>
      </div>
    </RequireRole>
  );
}
