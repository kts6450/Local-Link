import { Link, NavLink, Outlet } from "react-router-dom";

import { SiteFooter } from "../components/marketing/SiteFooter";
import { LocalLinkLogo } from "../components/brand/LocalLinkLogo";
import { ShopCategoryNav } from "../components/shop/ShopCategoryNav";
import { FontSizeToggle } from "../components/FontSizeToggle";
import {
  useAuth,
  useAuthDisplayName,
  useAuthRole,
} from "../store/auth";
import { useCart } from "../store/cart";

export function ConsumerLayout() {
  const n = useCart((s) => s.lines.reduce((a, l) => a + l.quantity, 0));
  const role = useAuthRole();
  const displayName = useAuthDisplayName();
  const logout = useAuth((s) => s.logout);

  return (
    <div className="min-h-screen flex flex-col bg-brand-cream text-hades-text">
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-lg border-b border-brand-line">
        <div className="page-shell py-3 flex flex-wrap items-center justify-between gap-3 lg:gap-6">
          <Link to="/" className="shrink-0 no-underline text-inherit">
            <LocalLinkLogo />
          </Link>

          <div className="order-last w-full flex justify-center lg:order-none lg:w-auto lg:flex-1">
            <ShopCategoryNav />
          </div>

          <div className="flex items-center gap-2 sm:gap-3 ml-auto lg:ml-0 shrink-0">
            <span className="hidden md:inline text-sm text-hades-muted">
              {displayName}님
              {role === "master" ? " · 운영" : ""}
            </span>
            {role === "seller" || role === "master" ? (
              <Link
                to="/seller/dashboard"
                className="hidden lg:inline text-sm font-semibold text-hades-muted hover:text-brand-ink"
              >
                판매자
              </Link>
            ) : null}
            {role === "master" ? (
              <Link
                to="/admin"
                className="hidden lg:inline text-sm font-semibold text-rose-700 hover:text-rose-900"
              >
                어드민
              </Link>
            ) : null}
            <NavLink
              to="/checkout"
              className="inline-flex items-center gap-2 rounded-full bg-brand-ink text-white font-bold text-sm px-5 py-2.5 hover:bg-brand-ink/90 transition-colors"
            >
              장바구니
              {n > 0 && (
                <span className="min-w-[1.25rem] h-5 flex items-center justify-center rounded-full bg-white/20 text-xs px-1.5">
                  {n}
                </span>
              )}
            </NavLink>
            <button
              type="button"
              className="text-sm text-hades-muted hover:text-brand-ink"
              onClick={() => {
                logout();
                window.location.href = "/login?role=consumer";
              }}
            >
              나가기
            </button>
            <FontSizeToggle variant="consumer" />
          </div>
        </div>
      </header>

      <main className="flex-1 w-full">
        <Outlet />
      </main>

      <SiteFooter />
    </div>
  );
}
