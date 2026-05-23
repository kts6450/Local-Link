import { Link, useLocation } from "react-router-dom";

import { parseShopFilters } from "../../lib/shopNavigation";

const pill =
  "px-5 py-2 rounded-full text-sm font-semibold transition-colors whitespace-nowrap";
const on = `${pill} bg-brand-ink text-white shadow-sm`;
const off = `${pill} text-hades-muted hover:bg-brand-warm hover:text-brand-ink`;

const ITEMS = [
  { label: "상품", kind: "product" as const, theme: "rural" as const },
  { label: "숙박", kind: "lodging" as const, theme: "lodging" as const },
  { label: "체험", kind: "product" as const, theme: "experience" as const, tab: "experience" as const },
];

function isActive(
  filters: ReturnType<typeof parseShopFilters>,
  item: (typeof ITEMS)[number]
): boolean {
  if (item.kind === "lodging") return filters.kind === "lodging";
  if (item.theme === "experience") {
    return filters.theme === "experience" || filters.tab === "experience";
  }
  return filters.kind !== "lodging" && filters.theme !== "experience" && filters.tab !== "experience";
}

function itemSearch(item: (typeof ITEMS)[number]): string {
  const p = new URLSearchParams();
  p.set("kind", item.kind);
  p.set("theme", item.theme);
  if ("tab" in item && item.tab) p.set("tab", item.tab);
  return p.toString();
}

export function ShopCategoryNav() {
  const { search } = useLocation();
  const filters = parseShopFilters(search);

  return (
    <nav className="flex items-center gap-1 p-1 rounded-full bg-brand-warm/90 border border-brand-line/70">
      {ITEMS.map((item) => (
        <Link
          key={item.label}
          to={{ pathname: "/", search: itemSearch(item) }}
          className={isActive(filters, item) ? on : off}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
