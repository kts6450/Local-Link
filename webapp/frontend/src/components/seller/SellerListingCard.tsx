import { Link } from "react-router-dom";

import type { Listing } from "../../types";
import { SafeImage } from "../shop/SafeImage";

type Props = {
  listing: Listing;
  salesCount?: number;
  onRemove?: (id: string) => void;
};

export function SellerListingCard({ listing, salesCount = 0, onRemove }: Props) {
  const soldOut =
    listing.kind === "product" && listing.stock !== null && listing.stock <= 0;

  return (
    <article className="group bg-white rounded-[1.75rem] border border-brand-line/80 overflow-hidden shadow-card hover:shadow-card-hover hover:-translate-y-1 transition-all duration-300 flex flex-col h-full">
      <div className="relative aspect-[4/3] bg-brand-warm overflow-hidden">
        <SafeImage
          listing={listing}
          className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        />
        <span
          className={`absolute top-4 left-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold shadow-soft backdrop-blur-sm ${
            soldOut ? "bg-white/90 text-hades-muted" : "bg-white/95 text-emerald-700"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full ${soldOut ? "bg-hades-muted" : "bg-emerald-500 animate-pulse"}`}
          />
          {soldOut ? "품절" : "판매중"}
        </span>
        {listing.location ? (
          <span className="absolute top-4 right-4 rounded-full bg-brand-ink/85 backdrop-blur-sm px-3 py-1.5 text-xs font-bold text-white">
            {listing.location}
          </span>
        ) : null}
      </div>

      <div className="p-5 sm:p-6 flex-1 flex flex-col">
        <h3 className="font-bold text-lg sm:text-xl text-brand-ink line-clamp-2 leading-snug tracking-tight">
          {listing.title}
        </h3>
        <p className="mt-2 text-sm text-hades-muted line-clamp-2 flex-1 leading-relaxed">
          {listing.description}
        </p>

        <div className="mt-4 flex items-end justify-between gap-3">
          <p className="text-xl sm:text-2xl font-bold text-brand-ink tabular-nums tracking-tight">
            {listing.price.toLocaleString()}
            <span className="text-sm font-semibold text-hades-muted ml-0.5">원</span>
            {listing.kind === "lodging" ? (
              <span className="text-sm font-medium text-hades-muted"> / 1박</span>
            ) : null}
          </p>
          <div className="text-right text-xs text-hades-muted leading-tight tabular-nums">
            <p>
              {listing.stock != null ? (
                <>
                  재고 <span className="font-bold text-brand-ink">{listing.stock}</span>
                </>
              ) : (
                "재고 무제한"
              )}
            </p>
            {salesCount > 0 ? (
              <p className="mt-0.5">
                판매 <span className="font-bold text-brand-ink">{salesCount}</span>회
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="px-5 sm:px-6 pb-5 sm:pb-6 flex gap-2">
        <Link
          to="/seller/products"
          className="flex-1 text-center rounded-full bg-brand-ink text-white text-sm font-bold py-3 hover:bg-brand-ink/90 active:scale-[0.98] transition-all no-underline"
        >
          수정
        </Link>
        <Link
          to="/seller/orders"
          className="flex-1 text-center rounded-full border border-brand-line bg-white text-sm font-bold py-3 hover:bg-brand-warm active:scale-[0.98] transition-all no-underline text-brand-ink"
        >
          주문보기
        </Link>
        {onRemove ? (
          <button
            type="button"
            className="rounded-full border border-rose-200 text-rose-600 text-xs font-bold px-3 hover:bg-rose-50 transition-colors"
            onClick={() => onRemove(listing.id)}
          >
            내리기
          </button>
        ) : null}
      </div>
    </article>
  );
}
