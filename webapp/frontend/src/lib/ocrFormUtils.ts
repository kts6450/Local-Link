import type { ListingVariant } from "../types";

import type { ListingTab, OcrListingDraft } from "./listingTabs";

/**
 * OCR 가격 문자열에서 다중 단가 옵션을 추출.
 * 예) "13,000(100g) / 25,000(200g) / 60,000(500g) / 110,000(1kg)"
 *  → [{label: "100g", price: 13000}, {label: "200g", price: 25000}, ...]
 * 단일 가격이거나 패턴이 안 맞으면 null.
 */
export function parseOcrPriceVariants(
  raw: string | number | null | undefined
): ListingVariant[] | null {
  if (raw == null || raw === "") return null;
  if (typeof raw === "number") return null;
  return parseOcrPriceVariantsFromText(String(raw).trim());
}

/** raw_text·설명 등 긴 텍스트에서 용량·단가 옵션 추출 (백엔드와 동일 패턴). */
export function parseOcrPriceVariantsFromText(text: string | null | undefined): ListingVariant[] | null {
  const blob = (text ?? "").trim();
  if (!blob) return null;

  const items: ListingVariant[] = [];
  const seen = new Set<string>();

  const add = (label: string, price: number) => {
    const normalized = label.replace(/\s+/g, "");
    if (!normalized || normalized.length > 40) return;
    if (!Number.isFinite(price) || price <= 0 || price >= 100_000_000) return;
    if (seen.has(normalized)) return;
    seen.add(normalized);
    items.push({ label: normalized, price });
  };

  const priceLabelRe = /(\d[\d,]*)\s*원?\s*\(\s*([^)]+?)\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = priceLabelRe.exec(blob)) !== null) {
    add(m[2], parseInt(m[1].replace(/,/g, ""), 10));
  }

  const labelPriceRe =
    /(\d+\s*(?:g|kg|그램|킬로|키로|ml|cc|l|리터|L))\s*(?:\(\s*(\d[\d,]*)\s*원?\s*\)|[:：·]\s*(\d[\d,]*)\s*원?)/gi;
  while ((m = labelPriceRe.exec(blob)) !== null) {
    const priceStr = m[2] ?? m[3];
    if (priceStr) add(m[1], parseInt(priceStr.replace(/,/g, ""), 10));
  }

  for (const seg of blob.split(/[/|,;]+|\s+·\s+/)) {
    const trimmed = seg.trim();
    if (!trimmed) continue;
    const wm = trimmed.match(/(\d+\s*(?:g|kg|그램|킬로|키로|ml|cc|l|리터|L))/i);
    const pm = trimmed.match(/(\d[\d,]*)\s*원/);
    if (wm && pm) add(wm[1], parseInt(pm[1].replace(/,/g, ""), 10));
  }

  return items.length >= 2 ? items : null;
}

/** OCR 초안에서 옵션 후보 추출 — API variants 우선, 없으면 raw_text 파싱. */
export function extractOcrVariants(draft: OcrListingDraft): ListingVariant[] | null {
  if (draft.variants && draft.variants.length >= 2) return draft.variants;
  const fromPrice = parseOcrPriceVariants(draft.fields?.price?.value);
  if (fromPrice && fromPrice.length >= 2) return fromPrice;
  const qty = String(draft.fields?.quantity?.value ?? "");
  const desc = String(draft.fields?.description?.value ?? "");
  const blob = [draft.raw_text, qty, desc].filter(Boolean).join("\n");
  return parseOcrPriceVariantsFromText(blob);
}

/** 보관방법 OCR 오타·화살표 잡음 정리 */
export function cleanOcrStorageMethod(raw: string | null | undefined): string {
  let s = (raw ?? "").trim();
  if (!s) return "";
  s = s.replace(/^[→\-–—>\s]+/, "");
  s = s.replace(/\s*[→\-–—>]+\s*(?:가을|봄|여름|겨울|환절기)\s*$/u, "");
  s = s.replace(/\s*[→\-–—>]+\s*[가-힣]{1,4}\s*$/u, "");
  s = s.replace(/냉공/g, "냉장");
  s = s.replace(/냉쟁/g, "냉장");
  return s.replace(/\s{2,}/g, " ").trim();
}

/** OCR 가격 문자열 → 대표 1개 가격 + (선택) 다중 단가 안내 */
export function parseOcrPrice(raw: string | number | null | undefined): {
  price: string;
  detailNote: string | null;
} {
  if (raw == null || raw === "") return { price: "", detailNote: null };
  if (typeof raw === "number" && Number.isFinite(raw)) {
    const n = Math.round(raw);
    if (n > 0 && n < 100_000_000) return { price: String(n), detailNote: null };
    return { price: "", detailNote: null };
  }

  const s = String(raw).trim();
  if (!s) return { price: "", detailNote: null };

  const segments = s.split(/[/|,;]+|\s+·\s+/).map((x) => x.trim()).filter(Boolean);
  const firstSeg = segments[0] ?? s;
  const m = firstSeg.match(/(\d[\d,]*)/);
  if (!m) return { price: "", detailNote: s.length > 3 ? s : null };

  const n = parseInt(m[1].replace(/,/g, ""), 10);
  if (!Number.isFinite(n) || n <= 0 || n >= 100_000_000) {
    return { price: "", detailNote: s };
  }

  const detailNote =
    segments.length > 1 || /\(.*\)/.test(s) || s.includes("kg") || s.includes("g")
      ? s
      : null;

  return { price: String(n), detailNote };
}

/** 동네 필드 — 국산·국내산 접두 제거, 괄호 정리 */
export function cleanOcrLocation(raw: string | null | undefined): string {
  let s = (raw ?? "").trim();
  if (!s) return "";

  s = s.replace(/^국산\s*[·\-/]?\s*/i, "");
  s = s.replace(/^국내산\s*[·\-/]?\s*/i, "");
  s = s.replace(/^원산지\s*[:：]\s*/i, "");

  const paren = s.match(/^\(([^)]+)\)\s*(.*)$/);
  if (paren) {
    const inner = paren[1].replace(/^국산\s*/i, "").trim();
    const rest = paren[2].trim();
    s = rest ? `${inner} ${rest}`.trim() : inner;
  }

  s = s.replace(/^\(([^)]+)\)$/, "$1");
  return s.replace(/\s{2,}/g, " ").trim();
}

export function buildOcrImagePrompt(
  fields: OcrListingDraft["fields"],
  tab: ListingTab,
  titleFallback = ""
): string {
  const title = String(fields?.title?.value ?? titleFallback).trim();
  const loc = cleanOcrLocation(String(fields?.location?.value ?? ""));
  const qty = String(fields?.quantity?.value ?? "").trim();
  const desc = String(fields?.description?.value ?? fields?.notes?.value ?? "").trim();

  const parts: string[] = [];
  if (title) parts.push(title);
  if (loc) parts.push(loc);
  if (qty) parts.push(qty);

  if (tab === "experience") {
    return `${parts.join(" ")} 체험 장면, 참여하는 모습, 밝은 자연광`.trim();
  }
  if (tab === "lodging") {
    return `${parts.join(" ")} 아늑한 민박·숙소 외관, 따뜻한 분위기`.trim();
  }
  if (desc.slice(0, 40)) {
    return `${parts.join(" ")} — ${desc.slice(0, 60)}, 산지 특산품 포장 사진`.trim();
  }
  return `${parts.join(" ")} 산지 특산품, 정갈한 포장, 자연광 상품 촬영`.trim();
}

export function buildImagePromptFromListing(
  title: string,
  location: string,
  description: string,
  tab: ListingTab
): string {
  return buildOcrImagePrompt(
    {
      title: { value: title },
      location: { value: location },
      description: { value: description },
    },
    tab,
    title
  );
}
