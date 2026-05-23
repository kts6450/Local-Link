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
  "px-5 py-2 rounded-full text-sm font-semibold transition-colors whitespace-nowrap";
const sectorOn = `${sectorPill} bg-brand-ink text-white shadow-sm`;
const sectorOff = `${sectorPill} text-hades-muted hover:bg-brand-warm hover:text-brand-ink`;

const navLink = "text-sm font-medium transition-colors whitespace-nowrap px-2 py-1";
const navOn = `${navLink} text-brand-ink font-bold`;
const navOff = `${navLink} text-hades-muted hover:text-brand-ink`;

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
        <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-lg border-b border-brand-line">
          <div className="page-shell py-4 flex flex-wrap items-center gap-3 lg:gap-5">
            <Link to="/seller/dashboard" className="shrink-0 no-underline text-inherit">
              <LocalLinkLogo />
            </Link>

            <nav className="flex items-center gap-1 p-1 rounded-full bg-brand-warm/90 border border-brand-line/70 order-last w-full justify-center lg:order-none lg:w-auto lg:flex-1">
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

            <div className="hidden md:flex items-center gap-1 shrink-0">
              <NavLink
                to="/seller/dashboard"
                end
                className={({ isActive }) => (isActive ? navOn : navOff)}
              >
                대시보드
              </NavLink>
              <span className="text-brand-line">·</span>
              <NavLink
                to="/seller/products"
                className={({ isActive }) => (isActive ? navOn : navOff)}
              >
                등록
              </NavLink>
              <span className="text-brand-line">·</span>
              <NavLink
                to="/seller/orders"
                className={({ isActive }) => (isActive ? navOn : navOff)}
              >
                주문
              </NavLink>
              <span className="text-brand-line">·</span>
              <NavLink to="/seller/sns" className={({ isActive }) => (isActive ? navOn : navOff)}>
                SNS
              </NavLink>
            </div>

            <div className="flex items-center gap-2 sm:gap-3 ml-auto shrink-0">
              <Link
                to="/seller/products"
                className="inline-flex items-center rounded-full bg-brand-ink text-white text-sm font-bold px-5 py-2.5 hover:bg-brand-ink/90 transition-colors shadow-sm"
              >
                + 새로 등록
              </Link>
              <span className="hidden xl:inline text-xs font-bold text-brand-ink/70 bg-brand-warm px-2.5 py-1 rounded-full">
                {role === "master" ? "운영" : categoryLabel(sellerSector ?? "rural")}
              </span>
              <span className="hidden lg:inline text-sm text-hades-muted">{displayName}님</span>
              <Link
                to="/"
                className="hidden sm:inline text-sm font-semibold text-hades-muted hover:text-brand-ink"
              >
                쇼핑몰
              </Link>
              <button
                type="button"
                className="text-sm text-hades-muted hover:text-brand-ink"
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
        </header>

        <main className="flex-1 w-full page-shell py-8 sm:py-10">
          <Outlet />
        </main>
      </div>
    </RequireRole>
  );
}
