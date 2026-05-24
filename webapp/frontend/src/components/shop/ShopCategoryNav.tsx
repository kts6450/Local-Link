import { Link, useLocation } from "react-router-dom";

import { parseShopFilters } from "../../lib/shopNavigation";

const pill =
  "group relative px-5 sm:px-6 py-2.5 rounded-full text-sm sm:text-base font-bold transition-all whitespace-nowrap flex items-center gap-2";
const on = `${pill} bg-brand-ink text-white shadow-soft`;
const off = `${pill} text-hades-muted hover:bg-white hover:text-brand-ink`;

type Item = {
  label: string;
  en: string;
  icon: string;
  kind: "product" | "lodging";
  theme: "market" | "experience" | "lodging";
};

const ITEMS: Item[] = [
  { label: "특산", en: "SHOP", icon: "🛒", kind: "product", theme: "market" },
  { label: "스테이", en: "STAY", icon: "🏠", kind: "lodging", theme: "lodging" },
  { label: "체험", en: "CLASS", icon: "🌾", kind: "product", theme: "experience" },
];

function isActive(filters: ReturnType<typeof parseShopFilters>, item: Item): boolean {
  if (item.theme === "lodging") return filters.kind === "lodging";
  if (item.theme === "experience") {
    return filters.theme === "experience" || filters.tab === "experience";
  }
  return filters.theme === "market";
}

function itemSearch(item: Item): string {
  const p = new URLSearchParams();
  p.set("kind", item.kind);
  p.set("theme", item.theme);
  return p.toString();
}

export function ShopCategoryNav() {
  const { search } = useLocation();
  const filters = parseShopFilters(search);

  return (
    <nav className="flex items-center gap-1 p-1 rounded-full bg-brand-warm border border-brand-line/60 shadow-soft">
      {ITEMS.map((item) => {
        const active = isActive(filters, item);
        return (
          <Link
            key={item.label}
            to={{ pathname: "/", search: itemSearch(item) }}
            className={active ? on : off}
            aria-current={active ? "page" : undefined}
          >
            <span aria-hidden className="text-base">
              {item.icon}
            </span>
            <span className="flex items-baseline gap-1.5">
              <span>{item.label}</span>
              <span
                className={`text-[10px] font-extrabold tracking-[0.2em] ${
                  active ? "text-white/70" : "text-hades-muted/70"
                }`}
              >
                {item.en}
              </span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
