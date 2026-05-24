import type { Listing } from "../types";

export type ShopKind = "all" | "product" | "lodging";
/** market = 진짜 상품(농수산·공예) — 체험 제외. */
export type ShopTheme =
  | "all"
  | "market"
  | "experience"
  | "rural"
  | "fishing"
  | "craft"
  | "leisure"
  | "lodging";
export type ShopTab = "best" | "exhibition" | "experience" | "lodging" | "coupon" | "story";

export type ShopSort = "newest" | "price-asc" | "price-desc";

export interface ShopFilters {
  kind: ShopKind;
  theme: ShopTheme;
  tab: ShopTab | null;
  query?: string;
  minPrice?: number;
  maxPrice?: number;
  sort?: ShopSort;
}

export const MEGA_MENU: { theme: ShopTheme; label: string; hint: string }[] = [
  { theme: "market", label: "특산", hint: "농수산·가공·공예" },
  { theme: "experience", label: "체험", hint: "수확·만들기·투어" },
  { theme: "lodging", label: "스테이", hint: "민박·펜션·캠핑" },
];

export const TOP_NAV: { tab: ShopTab; label: string }[] = [
  { tab: "best", label: "베스트" },
  { tab: "exhibition", label: "기획전" },
  { tab: "experience", label: "체험 패키지" },
  { tab: "lodging", label: "숙소/캠핑" },
  { tab: "coupon", label: "쿠폰" },
];

const THEME_KEYWORDS: Partial<Record<ShopTheme, string[]>> = {
  experience: ["체험", "수확", "만들기", "투어", "견학", "잡기"],
  rural: ["농", "특산", "쌀", "과일", "텃밭", "농촌", "햅", "고구마", "사과"],
  fishing: ["어촌", "바다", "해산", "갯벌", "생선", "전복", "멍게"],
  craft: ["공예", "도자", "문화", "전통", "짚", "옻"],
  leisure: ["휴양", "레저", "캠핑", "숲", "트레킹", "자전거", "온천"],
};

export function parseShopFilters(search: string): ShopFilters {
  const p = new URLSearchParams(search);
  const kindRaw = p.get("kind");
  const themeRaw = p.get("theme");
  const tabRaw = p.get("tab");

  const kind: ShopKind =
    kindRaw === "product" || kindRaw === "lodging" ? kindRaw : "all";
  const theme: ShopTheme =
    themeRaw === "market" ||
    themeRaw === "experience" ||
    themeRaw === "rural" ||
    themeRaw === "fishing" ||
    themeRaw === "craft" ||
    themeRaw === "leisure" ||
    themeRaw === "lodging"
      ? themeRaw
      : "all";
  const tab: ShopTab | null =
    tabRaw === "best" ||
    tabRaw === "exhibition" ||
    tabRaw === "experience" ||
    tabRaw === "lodging" ||
    tabRaw === "coupon" ||
    tabRaw === "story"
      ? tabRaw
      : null;

  const query = (p.get("q") ?? "").trim();
  const minRaw = p.get("min");
  const maxRaw = p.get("max");
  const sortRaw = p.get("sort");
  const sort: ShopSort | undefined =
    sortRaw === "price-asc" || sortRaw === "price-desc" || sortRaw === "newest"
      ? sortRaw
      : undefined;
  const minPrice = minRaw && Number.isFinite(Number(minRaw)) ? Number(minRaw) : undefined;
  const maxPrice = maxRaw && Number.isFinite(Number(maxRaw)) ? Number(maxRaw) : undefined;

  return { kind, theme, tab, query, minPrice, maxPrice, sort };
}

export function shopSearchParams(patch: Partial<ShopFilters>): string {
  const p = new URLSearchParams();
  const k = patch.kind ?? "all";
  const t = patch.theme ?? "all";
  const tab = patch.tab ?? null;
  if (k !== "all") p.set("kind", k);
  if (t !== "all") p.set("theme", t);
  if (tab) p.set("tab", tab);
  if (patch.query && patch.query.trim()) p.set("q", patch.query.trim());
  if (typeof patch.minPrice === "number" && patch.minPrice > 0) p.set("min", String(patch.minPrice));
  if (typeof patch.maxPrice === "number" && patch.maxPrice > 0) p.set("max", String(patch.maxPrice));
  if (patch.sort && patch.sort !== "newest") p.set("sort", patch.sort);
  const s = p.toString();
  return s ? `?${s}` : "";
}

function listingText(l: Listing) {
  return `${l.title} ${l.description} ${l.location}`.toLowerCase();
}

export function listingShopTheme(listing: Listing): ShopTheme {
  const c = listing.category;
  if (
    c === "experience" ||
    c === "rural" ||
    c === "fishing" ||
    c === "craft" ||
    c === "leisure" ||
    c === "lodging"
  ) {
    return c;
  }
  if (listing.kind === "lodging") return "lodging";
  return "rural";
}

export function matchesTheme(listing: Listing, theme: ShopTheme): boolean {
  if (theme === "all") return true;
  if (theme === "lodging") return listing.kind === "lodging";

  const cat = listing.category;
  // 가상 그룹 — 마켓 = 진짜 상품 (체험·숙박 제외)
  if (theme === "market") {
    if (listing.kind === "lodging") return false;
    if (cat === "experience") return false;
    return true;
  }
  if (theme === "experience") {
    return listing.kind !== "lodging" && cat === "experience";
  }

  // 세부 카테고리: category 필드가 명시되어 있으면 그 값으로만 판단
  if (cat) return cat === theme;

  // category 가 비어 있는 레거시 항목만 키워드 폴백
  if (listing.kind === "lodging") return false;
  const keys = THEME_KEYWORDS[theme as keyof typeof THEME_KEYWORDS];
  if (!keys) return false;
  const text = listingText(listing);
  if (keys.some((k) => text.includes(k))) return true;
  if (theme === "rural" && listing.kind === "product") return true;
  return false;
}

export function filterShopListings(listings: Listing[], filters: ShopFilters): Listing[] {
  let out = [...listings];

  if (filters.query) {
    const q = filters.query.toLowerCase();
    out = out.filter((l) => listingText(l).includes(q));
  }
  if (typeof filters.minPrice === "number") {
    out = out.filter((l) => l.price >= (filters.minPrice ?? 0));
  }
  if (typeof filters.maxPrice === "number" && filters.maxPrice > 0) {
    out = out.filter((l) => l.price <= (filters.maxPrice ?? Number.MAX_SAFE_INTEGER));
  }

  if (filters.tab === "lodging") {
    out = out.filter((l) => l.kind === "lodging");
  } else if (filters.tab === "experience") {
    out = out.filter((l) => matchesTheme(l, "experience"));
  } else if (filters.theme === "lodging") {
    out = out.filter((l) => l.kind === "lodging");
  } else if (filters.theme !== "all") {
    out = out.filter((l) => matchesTheme(l, filters.theme));
  }

  if (filters.kind !== "all") {
    if (filters.kind === "product" && filters.theme !== "experience" && filters.tab !== "experience") {
      // 마켓류 product 검색일 때 체험은 자동 제외
      out = out.filter((l) => l.kind === "product" && l.category !== "experience");
    } else {
      out = out.filter((l) => l.kind === filters.kind);
    }
  }

  if (filters.tab === "best") {
    out = [...out].sort((a, b) => b.price - a.price || a.title.localeCompare(b.title));
  } else if (filters.tab === "exhibition") {
    out = [...out].reverse();
  } else if (filters.sort === "price-asc") {
    out = [...out].sort((a, b) => a.price - b.price);
  } else if (filters.sort === "price-desc") {
    out = [...out].sort((a, b) => b.price - a.price);
  }

  return out;
}

export function sectionTitle(filters: ShopFilters): string {
  if (filters.tab === "best") return "베스트";
  if (filters.tab === "exhibition") return "기획전";
  if (filters.tab === "coupon") return "쿠폰·혜택";
  if (filters.tab === "story") return "지역 스토리";
  const mega = MEGA_MENU.find((m) => m.theme === filters.theme);
  if (mega) return mega.label;
  if (filters.theme === "rural") return "농촌 특산";
  if (filters.theme === "fishing") return "어촌 해산";
  if (filters.theme === "craft") return "전통 공예";
  if (filters.theme === "leisure") return "휴양·레저";
  if (filters.kind === "product") return "특산";
  if (filters.kind === "lodging") return "스테이";
  return "추천 콘텐츠";
}
