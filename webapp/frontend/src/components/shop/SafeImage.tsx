import { useEffect, useState } from "react";

import { listingCoverPhoto, listingFallbackPhoto } from "../../lib/listingDisplay";
import type { Listing } from "../../types";

type Props = {
  listing: Pick<Listing, "id" | "kind" | "category" | "cover_image_url" | "emoji" | "title">;
  alt?: string;
  className?: string;
  loading?: "lazy" | "eager";
  sizes?: string;
};

type Stage = "cover" | "pool" | "placeholder";

/** 깨진 listing 이미지를 단계적으로 폴백.
 *  cover → 카테고리 풀 → emoji 그라데이션 placeholder
 */
export function SafeImage({ listing, alt = "", className, loading = "lazy", sizes }: Props) {
  const cover = listingCoverPhoto(listing as Listing);
  const fallback = listingFallbackPhoto(listing);
  const [stage, setStage] = useState<Stage>("cover");

  useEffect(() => {
    setStage("cover");
  }, [listing.id, listing.cover_image_url]);

  if (stage === "placeholder") {
    return (
      <div
        className={`flex items-center justify-center bg-gradient-to-br from-brand-warm via-brand-cream to-brand-line ${className ?? ""}`}
        aria-label={alt || listing.title || "이미지 없음"}
      >
        <span className="text-5xl select-none" aria-hidden>
          {listing.emoji || "🏷️"}
        </span>
      </div>
    );
  }

  const src = stage === "cover" ? cover : fallback;
  return (
    <img
      src={src}
      alt={alt}
      loading={loading}
      sizes={sizes}
      referrerPolicy="no-referrer"
      className={className}
      onError={() => {
        setStage((prev) => {
          if (prev === "cover" && fallback && fallback !== cover) return "pool";
          if (prev === "pool") return "placeholder";
          return "placeholder";
        });
      }}
    />
  );
}
