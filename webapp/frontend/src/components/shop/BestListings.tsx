import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../lib/api";
import type { Listing } from "../../types";
import { useCart } from "../../store/cart";
import { SafeImage } from "./SafeImage";

function categoryLabel(it: Listing): string {
  if (it.kind === "lodging") return "스테이";
  if (it.category === "experience") return "체험";
  return "특산";
}

export function BestListings() {
  const [items, setItems] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const add = useCart((s) => s.add);

  useEffect(() => {
    api
      .getBestListings(8)
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <section>
        <div className="h-72 rounded-[2rem] bg-brand-warm/60 animate-pulse" />
      </section>
    );
  }
  if (items.length === 0) return null;

  const top = items.slice(0, 8);

  return (
    <section>
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-8 sm:mb-10">
        <div>
          <p className="eyebrow mb-3">Best of Local Link</p>
          <h2 className="display-2 text-balance">
            지금 가장 사랑받는
            <br />
            로컬링크 베스트
          </h2>
          <p className="mt-3 text-base sm:text-lg text-hades-muted max-w-xl leading-relaxed">
            실제 구매자 리뷰 평점과 후기 수를 기준으로 매주 자동 선정됩니다.
          </p>
        </div>
        <Link
          to="/?kind=all"
          className="hidden lg:inline-flex items-center gap-2 rounded-full border border-brand-line bg-white px-6 py-3 text-sm font-bold text-brand-ink hover:bg-brand-warm transition-colors no-underline"
        >
          전체 상품 보기
          <span aria-hidden>→</span>
        </Link>
      </div>

      <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {top.map((it, i) => {
          const rating = (it.rating ?? 0).toFixed(1);
          return (
            <li
              key={it.id}
              className="reveal group relative bg-white rounded-[1.75rem] border border-brand-line/80 overflow-hidden shadow-card hover:shadow-card-hover hover:-translate-y-1 transition-all duration-300"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <Link to={`/listing/${it.id}`} className="block no-underline text-inherit">
                <div className="relative aspect-[4/3] bg-brand-warm overflow-hidden">
                  <SafeImage
                    listing={it}
                    className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
                  />
                  <span className="absolute top-4 left-4 inline-flex items-center justify-center h-10 w-10 rounded-full bg-brand-ink text-white text-base font-extrabold shadow-card tabular-nums">
                    {i + 1}
                  </span>
                  <span className="absolute top-4 right-4 rounded-full bg-white/95 px-3 py-1.5 text-xs font-bold text-brand-ink backdrop-blur-sm shadow-soft">
                    {categoryLabel(it)}
                  </span>
                  <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/65 to-transparent">
                    <p className="text-white/80 text-xs font-medium">{it.location}</p>
                  </div>
                </div>
                <div className="p-5">
                  <div className="flex items-center gap-2 text-xs font-semibold mb-2">
                    <span className="inline-flex items-center gap-1 text-amber-500">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                        <path d="M12 2.5l2.95 6 6.6.96-4.78 4.66 1.13 6.58L12 17.6l-5.9 3.1 1.13-6.58L2.45 9.46l6.6-.96L12 2.5z" />
                      </svg>
                      <span className="text-brand-ink font-bold tabular-nums">{rating}</span>
                    </span>
                    <span className="text-hades-muted tabular-nums">
                      ({it.review_count ?? 0}개 리뷰)
                    </span>
                  </div>
                  <h3 className="font-bold text-base text-brand-ink line-clamp-2 leading-snug tracking-tight">
                    {it.title}
                  </h3>
                  <p className="mt-3 text-lg font-bold text-brand-ink tabular-nums tracking-tight">
                    {it.price.toLocaleString()}
                    <span className="text-xs font-semibold text-hades-muted ml-0.5">원</span>
                    {it.kind === "lodging" ? (
                      <span className="text-xs font-medium text-hades-muted"> /1박</span>
                    ) : null}
                  </p>
                </div>
              </Link>
              <div className="px-5 pb-5">
                <button
                  type="button"
                  onClick={() => add(it.id, 1)}
                  className="w-full rounded-full bg-brand-warm hover:bg-brand-line text-brand-ink text-sm font-bold py-2.5 transition-colors"
                >
                  담기
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
