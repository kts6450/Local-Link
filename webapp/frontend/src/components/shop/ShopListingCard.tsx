import { Link } from "react-router-dom";

import { listingDemoRating, listingReviewCount } from "../../lib/listingDisplay";
import type { Listing } from "../../types";
import { SafeImage } from "./SafeImage";

type Props = {
  listing: Listing;
  onAdd: (id: string) => void;
  rank?: number;
};

function categoryBadge(listing: Listing): { label: string; tone: string } {
  if (listing.kind === "lodging") {
    return { label: "스테이", tone: "bg-sky-50 text-sky-700 border-sky-100" };
  }
  if (listing.category === "experience") {
    return { label: "체험", tone: "bg-amber-50 text-amber-700 border-amber-100" };
  }
  return { label: "특산", tone: "bg-emerald-50 text-emerald-700 border-emerald-100" };
}

export function ShopListingCard({ listing, onAdd, rank }: Props) {
  const realRating = typeof listing.rating === "number" ? listing.rating : 0;
  const realReviews = listing.review_count ?? 0;
  const rating = realRating > 0 ? realRating.toFixed(1) : listingDemoRating(listing.id);
  const reviews = realReviews > 0 ? realReviews : listingReviewCount(listing.id);
  const soldOut =
    listing.kind === "product" && listing.stock !== null && listing.stock <= 0;
  const cat = categoryBadge(listing);
  // 체험·숙박은 날짜/인원 예약이 필요 → 즉시 담기 대신 상세에서 예약.
  const needsBooking = listing.kind === "lodging" || listing.category === "experience";
  const statusLabel = soldOut ? "품절" : needsBooking ? "예약가능" : "판매중";

  return (
    <article className="group relative bg-white rounded-[1.75rem] border border-brand-line/80 overflow-hidden shadow-card hover:shadow-card-hover hover:-translate-y-1 transition-all duration-300 flex flex-col h-full">
      {rank ? (
        <span className="absolute top-4 left-4 z-10 inline-flex items-center justify-center h-9 w-9 rounded-full bg-brand-ink text-white text-sm font-extrabold shadow-card tabular-nums">
          {rank}
        </span>
      ) : null}
      <Link
        to={`/listing/${listing.id}`}
        className="block no-underline text-inherit flex-1 flex flex-col"
      >
        <div className="relative aspect-[4/3] bg-brand-warm overflow-hidden">
          <SafeImage
            listing={listing}
            className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          <span
            className={`absolute top-4 ${rank ? "left-16" : "left-4"} inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-bold backdrop-blur-sm shadow-soft ${cat.tone}`}
          >
            {cat.label}
          </span>
          <span
            className={`absolute bottom-4 left-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold shadow-soft backdrop-blur-sm ${
              soldOut ? "bg-white/90 text-hades-muted" : "bg-white/95 text-emerald-700"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${soldOut ? "bg-hades-muted" : "bg-emerald-500 animate-pulse"}`}
            />
            {statusLabel}
          </span>
          {listing.location ? (
            <span className="absolute top-4 right-4 rounded-full bg-brand-ink/85 backdrop-blur-sm px-3 py-1.5 text-xs font-bold text-white">
              {listing.location.split(" ")[0]}
            </span>
          ) : null}
        </div>

        <div className="p-5 sm:p-6 flex-1 flex flex-col">
          <div className="flex items-center gap-2 text-xs sm:text-sm font-semibold text-hades-muted">
            <span className="inline-flex items-center gap-1 text-amber-500">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M12 2.5l2.95 6 6.6.96-4.78 4.66 1.13 6.58L12 17.6l-5.9 3.1 1.13-6.58L2.45 9.46l6.6-.96L12 2.5z" />
              </svg>
              <span className="text-brand-ink font-bold tabular-nums">{rating}</span>
            </span>
            <span className="text-hades-muted/70 tabular-nums">({reviews}개 리뷰)</span>
          </div>
          <h3 className="mt-2 font-bold text-lg sm:text-xl text-brand-ink line-clamp-2 leading-snug tracking-tight">
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
                <span className="text-sm font-medium text-hades-muted"> /1박</span>
              ) : null}
            </p>
            {listing.stock != null && listing.stock <= 5 && !soldOut ? (
              <span className="text-[11px] font-bold text-rose-600 bg-rose-50 px-2.5 py-1 rounded-full">
                마감임박
              </span>
            ) : null}
          </div>
        </div>
      </Link>

      <div className="px-5 sm:px-6 pb-5 sm:pb-6 flex gap-2">
        <Link
          to={`/listing/${listing.id}`}
          className="flex-1 text-center rounded-full bg-brand-ink text-white text-sm font-bold py-3 hover:bg-brand-ink/90 active:scale-[0.98] transition-all no-underline"
        >
          자세히
        </Link>
        {needsBooking ? (
          <Link
            to={`/listing/${listing.id}`}
            className="flex-1 text-center rounded-full border border-brand-line bg-white text-sm font-bold py-3 hover:bg-brand-warm active:scale-[0.98] transition-all text-brand-ink no-underline"
          >
            예약
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => onAdd(listing.id)}
            disabled={soldOut}
            className="flex-1 rounded-full border border-brand-line bg-white text-sm font-bold py-3 hover:bg-brand-warm active:scale-[0.98] transition-all text-brand-ink disabled:opacity-50 disabled:cursor-not-allowed"
          >
            담기
          </button>
        )}
      </div>
    </article>
  );
}
