import { Link, NavLink, Outlet } from "react-router-dom";

import { SiteFooter } from "../components/marketing/SiteFooter";
import { LocalLinkLogo } from "../components/brand/LocalLinkLogo";
import { ShopCategoryNav } from "../components/shop/ShopCategoryNav";
import { AssistantWidget } from "../components/shop/AssistantWidget";
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
    <div className="min-h-screen flex flex-col bg-brand-cream text-brand-ink">
      <header className="sticky top-0 z-50 bg-brand-cream/85 backdrop-blur-xl border-b border-brand-line/60">
        <div className="page-shell h-[72px] sm:h-[84px] flex items-center justify-between gap-4 lg:gap-8">
          <Link to="/" className="shrink-0 no-underline text-inherit">
            <LocalLinkLogo />
          </Link>

          <div className="hidden lg:flex flex-1 justify-center">
            <ShopCategoryNav />
          </div>

          <div className="flex items-center gap-3 sm:gap-4 shrink-0">
            <span className="hidden xl:inline text-sm font-medium text-hades-muted">
              <Link
                to="/mypage"
                className="font-semibold text-brand-ink hover:underline transition-all cursor-pointer"
              >
                {displayName}님
              </Link>
              {role === "master" ? " · 운영" : ""}
            </span>
            {role === "seller" || role === "master" ? (
              <Link
                to="/seller/dashboard"
                className="hidden lg:inline text-sm font-semibold text-hades-muted hover:text-brand-ink transition-colors"
              >
                판매자
              </Link>
            ) : null}
            {role === "master" ? (
              <Link
                to="/admin"
                className="hidden lg:inline text-sm font-semibold text-rose-700 hover:text-rose-900 transition-colors"
              >
                어드민
              </Link>
            ) : null}
            <NavLink
              to="/checkout"
              className="inline-flex items-center gap-2 rounded-full bg-brand-ink text-white font-bold text-sm px-5 py-2.5 sm:px-6 sm:py-3 hover:bg-brand-ink/90 active:scale-[0.98] transition-all shadow-soft"
            >
              <span aria-hidden>🛒</span>
              <span className="hidden sm:inline">장바구니</span>
              {n > 0 && (
                <span className="min-w-[1.4rem] h-5 flex items-center justify-center rounded-full bg-white text-brand-ink text-[11px] font-bold px-1.5 tabular-nums">
                  {n}
                </span>
              )}
            </NavLink>
            <button
              type="button"
              className="hidden sm:inline text-sm font-medium text-hades-muted hover:text-brand-ink transition-colors"
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

        <div className="lg:hidden border-t border-brand-line/60 page-shell py-2.5 flex justify-center">
          <ShopCategoryNav />
        </div>
      </header>

      <main className="flex-1 w-full">
        <Outlet />
      </main>

      <SiteFooter />
      <AssistantWidget />
    </div>
  );
}
