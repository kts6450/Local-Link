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
  if (raw == null || raw === "" || typeof raw === "number") return null;
  const s = String(raw).trim();
  if (!s) return null;

  // "숫자 + (라벨)" 패턴 추출. 라벨 안에 숫자·g·kg·인분·박·시간 등 허용.
  const itemRe = /(\d[\d,]*)\s*\(\s*([^)]+?)\s*\)/g;
  const items: ListingVariant[] = [];
  let m: RegExpExecArray | null;
  while ((m = itemRe.exec(s)) !== null) {
    const price = parseInt(m[1].replace(/,/g, ""), 10);
    const label = m[2].trim();
    if (!Number.isFinite(price) || price <= 0 || price >= 100_000_000) continue;
    if (!label || label.length > 60) continue;
    items.push({ label, price });
  }
  if (items.length < 2) return null;
  // 라벨 중복 제거
  const seen = new Set<string>();
  const unique = items.filter((v) => {
    if (seen.has(v.label)) return false;
    seen.add(v.label);
    return true;
  });
  return unique.length >= 2 ? unique : null;
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
