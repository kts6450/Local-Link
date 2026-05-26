/** Loople식 등록 탭 — 상품 / 숙박 / 체험 */

import type { ListingCategory } from "./sellerSectors";

export type ListingTab = "product" | "lodging" | "experience";

export const LISTING_TABS: {
  id: ListingTab;
  label: string;
  sub: string;
  emoji: string;
}[] = [
  { id: "product", label: "특산", sub: "농·축·수·특산", emoji: "🛒" },
  { id: "lodging", label: "스테이", sub: "숙소·민박", emoji: "🏠" },
  { id: "experience", label: "체험", sub: "일정·투어", emoji: "🌾" },
];

export function tabLabel(tab: ListingTab): string {
  return LISTING_TABS.find((t) => t.id === tab)?.label ?? tab;
}

export function tabToKind(tab: ListingTab): "product" | "lodging" {
  return tab === "lodging" ? "lodging" : "product";
}

export function tabDefaultCategory(tab: ListingTab): ListingCategory {
  if (tab === "lodging") return "lodging";
  if (tab === "experience") return "experience";
  return "rural";
}

/** 상품 탭에서만 선택 가능한 쇼핑 메뉴 */
export const PRODUCT_MENU_CATEGORIES: ListingCategory[] = [
  "rural",
  "fishing",
  "craft",
  "leisure",
];

export function resolveKindCategory(
  tab: ListingTab,
  category: ListingCategory
): { kind: "product" | "lodging"; category: ListingCategory } {
  if (tab === "lodging") return { kind: "lodging", category: "lodging" };
  if (tab === "experience") return { kind: "product", category: "experience" };
  const cat = PRODUCT_MENU_CATEGORIES.includes(category) ? category : "rural";
  return { kind: "product", category: cat };
}

export function listingToTab(listing: {
  kind: string;
  category?: string | null;
}): ListingTab {
  if (listing.kind === "lodging") return "lodging";
  if (listing.category === "experience") return "experience";
  return "product";
}

export type OcrFieldValue = {
  value?: string | number | null;
  confidence?: number;
  needs_review?: boolean;
};

export type OcrA2aStep = {
  agent: string;
  approved?: boolean;
  applied?: string[];
  fixes?: string[];
  issues?: string[];
  needs_review_keys?: string[];
  corrected_location?: string;
};

export type OcrListingDraft = {
  registration_type: "product" | "reservation" | "order";
  listing_tab: ListingTab;
  confidence_overall: number;
  raw_text: string;
  fields: Record<string, OcrFieldValue>;
  missing_required: string[];
  warnings: string[];
  a2a_pipeline?: "off" | "rules" | "a2a" | "max" | string;
  a2a_steps?: OcrA2aStep[];
  variants?: import("../types").ListingVariant[] | null;
  /** clova+claude | claude_vision | clova | none */
  ocr_engine?: string;
};
