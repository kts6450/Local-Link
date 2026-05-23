import { Link } from "react-router-dom";

import { listingCoverPhoto } from "../../lib/listingDisplay";
import type { Listing } from "../../types";

type Props = {
  listing: Listing;
  salesCount?: number;
  onRemove?: (id: string) => void;
};

export function SellerListingCard({ listing, salesCount = 0, onRemove }: Props) {
  const photo = listingCoverPhoto(listing);
  const soldOut =
    listing.kind === "product" && listing.stock !== null && listing.stock <= 0;

  return (
    <article className="bg-white rounded-3xl border border-brand-line overflow-hidden shadow-card hover:shadow-card-hover transition-shadow flex flex-col h-full">
      <div className="relative aspect-[4/3] bg-brand-warm">
        <img src={photo} alt="" className="h-full w-full object-cover" loading="lazy" />
        <span
          className={`absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold shadow-sm ${
            soldOut ? "bg-white/90 text-hades-muted" : "bg-white/95 text-hades-ok"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${soldOut ? "bg-hades-muted" : "bg-hades-ok"}`}
          />
          {soldOut ? "품절" : "판매중"}
        </span>
        {listing.location ? (
          <span className="absolute top-3 right-3 rounded-full bg-black/55 backdrop-blur-sm px-3 py-1 text-xs font-semibold text-white">
            {listing.location}
          </span>
        ) : null}
      </div>

      <div className="p-5 flex-1 flex flex-col">
        <h3 className="font-bold text-lg text-brand-ink line-clamp-2 leading-snug">
          {listing.title}
        </h3>
        <p className="mt-2 text-sm text-hades-muted line-clamp-2 flex-1 leading-relaxed">
          {listing.description}
        </p>
        <p className="mt-4 text-xl font-bold text-brand-ink tabular-nums">
          {listing.price.toLocaleString()}원
          {listing.kind === "lodging" ? (
            <span className="text-sm font-semibold text-hades-muted"> / 1박</span>
          ) : null}
        </p>
        <p className="mt-1 text-xs text-hades-muted tabular-nums">
          {listing.stock != null ? `재고 ${listing.stock}개` : "재고 무제한"}
          {salesCount > 0 ? ` · 판매 ${salesCount}회` : null}
        </p>
      </div>

      <div className="px-5 pb-5 flex gap-2">
        <Link
          to="/seller/products"
          className="flex-1 text-center rounded-full bg-brand-ink text-white text-sm font-bold py-2.5 hover:bg-brand-ink/90 transition-colors no-underline"
        >
          수정
        </Link>
        <Link
          to="/seller/orders"
          className="flex-1 text-center rounded-full border border-brand-line bg-white text-sm font-bold py-2.5 hover:bg-brand-warm transition-colors no-underline text-brand-ink"
        >
          주문보기
        </Link>
        {onRemove ? (
          <button
            type="button"
            className="rounded-full border border-red-100 text-red-600 text-xs font-bold px-3 hover:bg-red-50"
            onClick={() => onRemove(listing.id)}
          >
            내리기
          </button>
        ) : null}
      </div>
    </article>
  );
}
