import type { Listing } from "../types";

const GRADIENTS = [
  "from-teal-600 via-cyan-700 to-slate-900",
  "from-emerald-600 via-teal-800 to-slate-900",
  "from-cyan-600 via-blue-800 to-slate-900",
  "from-green-700 via-emerald-900 to-slate-950",
  "from-teal-700 via-cyan-900 to-indigo-950",
  "from-emerald-800 via-teal-900 to-slate-900",
];

const SUFFIX = "?auto=format&fit=crop&w=1600&q=85";

/** 시드·새 글 모두 쓸 수 있는 고정 매핑 + 종류별 풀 (백엔드 demo_images.py와 동기화) */
const COVER_BY_ID: Record<string, string> = {
  "seed-rice-10kg": `https://images.unsplash.com/photo-1586201375761-83865001e31c${SUFFIX}`,
  "seed-hanok-night": `https://images.unsplash.com/photo-1600585154340-be6161a56a0c${SUFFIX}`,
  "seed-honey": `https://images.unsplash.com/photo-1587049352846-4a222e784d38${SUFFIX}`,
  "seed-guesthouse": `https://images.unsplash.com/photo-1611892440504-42a792e24d32${SUFFIX}`,
};

const PRODUCT_POOL = [
  `https://images.unsplash.com/photo-1586201375761-83865001e31c${SUFFIX}`,
  `https://images.unsplash.com/photo-1568702846914-96b305d2aaeb${SUFFIX}`,
  `https://images.unsplash.com/photo-1606851094291-6efae152bb87${SUFFIX}`,
  `https://images.unsplash.com/photo-1576092768241-dec231879fc3${SUFFIX}`,
  `https://images.unsplash.com/photo-1597481499750-3e6b22637e12${SUFFIX}`,
  `https://images.unsplash.com/photo-1547514701-42782101795e${SUFFIX}`,
  `https://images.unsplash.com/photo-1544025162-d76694265947${SUFFIX}`,
  `https://images.unsplash.com/photo-1562967914-608f82629710${SUFFIX}`,
  `https://images.unsplash.com/photo-1631452180519-c014fe946bc7${SUFFIX}`,
  `https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6${SUFFIX}`,
  `https://images.unsplash.com/photo-1564890369478-c89ca6d9cde9${SUFFIX}`,
  `https://images.unsplash.com/photo-1559339352-11d035aa65de${SUFFIX}`,
  `https://images.unsplash.com/photo-1504674900247-0877df9cc836${SUFFIX}`,
  `https://images.unsplash.com/photo-1455390582262-044cdead277a${SUFFIX}`,
  `https://images.unsplash.com/photo-1521478706270-f2e33c203d95${SUFFIX}`,
  `https://images.unsplash.com/photo-1543589077-47d81606c1bf${SUFFIX}`,
];

const LODGING_POOL = [
  `https://images.unsplash.com/photo-1568084680786-a84f91d1153c${SUFFIX}`,
  `https://images.unsplash.com/photo-1505691938895-1758d7feb511${SUFFIX}`,
  `https://images.unsplash.com/photo-1600585154340-be6161a56a0c${SUFFIX}`,
  `https://images.unsplash.com/photo-1582719478250-c89cae4dc85b${SUFFIX}`,
  `https://images.unsplash.com/photo-1520250497591-112f2f40a3f4${SUFFIX}`,
  `https://images.unsplash.com/photo-1487730116645-74489c95b41b${SUFFIX}`,
  `https://images.unsplash.com/photo-1564013799919-ab600027ffc6${SUFFIX}`,
  `https://images.unsplash.com/photo-1566073771259-6a8506099945${SUFFIX}`,
  `https://images.unsplash.com/photo-1571896349842-33c89424de2d${SUFFIX}`,
  `https://images.unsplash.com/photo-1582719508461-905c673771fd${SUFFIX}`,
  `https://images.unsplash.com/photo-1611892440504-42a792e24d32${SUFFIX}`,
  `https://images.unsplash.com/photo-1568605114967-8130f3a36994${SUFFIX}`,
  `https://images.unsplash.com/photo-1602002418082-a4443e081dd1${SUFFIX}`,
  `https://images.unsplash.com/photo-1551918120-9739cb430c6d${SUFFIX}`,
  `https://images.unsplash.com/photo-1505873242700-f289a29e1e0f${SUFFIX}`,
  `https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9${SUFFIX}`,
];

const EXPERIENCE_POOL = [
  `https://images.unsplash.com/photo-1500382017468-9049fed747ef${SUFFIX}`,
  `https://images.unsplash.com/photo-1466692476868-aef1dfb1e735${SUFFIX}`,
  `https://images.unsplash.com/photo-1500380804539-4e1e8c1e7118${SUFFIX}`,
  `https://images.unsplash.com/photo-1500916434205-0c77489c6cf7${SUFFIX}`,
  `https://images.unsplash.com/photo-1502680390469-be75c86b636f${SUFFIX}`,
  `https://images.unsplash.com/photo-1530549387789-4c1017266635${SUFFIX}`,
  `https://images.unsplash.com/photo-1559827260-dc66d52bef19${SUFFIX}`,
  `https://images.unsplash.com/photo-1551776235-dde6d482980b${SUFFIX}`,
  `https://images.unsplash.com/photo-1469854523086-cc02fe5d8800${SUFFIX}`,
  `https://images.unsplash.com/photo-1564501049412-61c2a3083791${SUFFIX}`,
  `https://images.unsplash.com/photo-1532339142463-fd0a8979791a${SUFFIX}`,
  `https://images.unsplash.com/photo-1582719508461-905c673771fd${SUFFIX}`,
];

function hashId(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) {
    h = Math.imul(31, h) + id.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

export function listingHeroGradient(listing: Pick<Listing, "id">): string {
  return GRADIENTS[hashId(listing.id) % GRADIENTS.length];
}

function categoryPool(listing: Pick<Listing, "kind" | "category">): string[] {
  if (listing.kind === "lodging") return LODGING_POOL;
  if (listing.category === "experience") return EXPERIENCE_POOL;
  return PRODUCT_POOL;
}

/** 카드·상세 커버 사진 — 서버에 저장된 AI/업로드 이미지 우선 */
export function listingCoverPhoto(listing: Listing): string {
  const raw = listing.cover_image_url;
  if (raw && typeof raw === "string" && raw.trim()) {
    const u = raw.trim();
    if (u.startsWith("http://") || u.startsWith("https://")) return u;
    return u.startsWith("/") ? u : `/${u}`;
  }
  const known = COVER_BY_ID[listing.id];
  if (known) return known;
  const pool = categoryPool(listing);
  return pool[hashId(listing.id) % pool.length];
}

/** 깨진 cover 이미지를 위한 폴백 — 카테고리별 풀에서 결정적으로 하나 선택 */
export function listingFallbackPhoto(listing: Pick<Listing, "id" | "kind" | "category">): string {
  const pool = categoryPool(listing);
  const idx = (hashId(listing.id) + 1) % pool.length;
  return pool[idx];
}

export function listingDemoViewCount(id: string): number {
  const h = hashId(id);
  return 320 + (h % 2100);
}

export function listingDemoRating(id: string): string {
  const v = 46 + (hashId(id) % 5);
  return (v / 10).toFixed(1);
}

export function listingReviewCount(id: string): number {
  return 8 + (hashId(id) % 112);
}
