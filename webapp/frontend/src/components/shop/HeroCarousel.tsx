import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listingCoverPhoto, listingFallbackPhoto } from "../../lib/listingDisplay";
import type { Listing } from "../../types";

const FALLBACK_SLIDES = [
  {
    id: "demo-1",
    eyebrow: "농촌 체험",
    title: "친환경 인증 연천 딸기수확 체험",
    subtitle: "아이와 함께 떠나는 주말 농장",
    image:
      "https://images.unsplash.com/photo-1464454709131-ffd692591ee5?auto=format&fit=crop&w=2000&q=85",
    to: "/?theme=experience",
    location: "경기 연천",
    price: "1인 25,000원",
  },
  {
    id: "demo-2",
    eyebrow: "숙소·캠핑",
    title: "노을 지는 서해 한옥 캠핑",
    subtitle: "지역 호스트가 직접 운영하는 프라이빗 스테이",
    image:
      "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?auto=format&fit=crop&w=2000&q=85",
    to: "/?kind=lodging",
    location: "충남 태안",
    price: "1박 120,000원",
  },
  {
    id: "demo-3",
    eyebrow: "어촌 체험",
    title: "어촌 갯벌 체험 · 싱싱한 해산물",
    subtitle: "바다 위에서 보내는 잊지 못할 하루",
    image:
      "https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=2000&q=85",
    to: "/?theme=fishing",
    location: "전남 신안",
    price: "1인 38,000원",
  },
] as const;

type Slide = {
  id: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  image: string;
  fallback?: string;
  to: string;
  location: string;
  price: string;
};

export function HeroCarousel({ listings }: { listings: Listing[] }) {
  const slides: Slide[] = useMemo(() => {
    if (listings.length === 0) {
      return FALLBACK_SLIDES.map((s) => ({ ...s }));
    }
    return listings.slice(0, 5).map((l) => ({
      id: l.id,
      eyebrow:
        l.kind === "lodging"
          ? "스테이"
          : l.category === "experience"
            ? "체험"
            : "지역 특산",
      title: l.title,
      subtitle: l.description?.slice(0, 60) || "지역 판매자가 직접 올린 상품",
      image: listingCoverPhoto(l),
      fallback: listingFallbackPhoto(l),
      to: `/listing/${l.id}`,
      location: l.location,
      price:
        l.kind === "lodging"
          ? `1박 ${l.price.toLocaleString()}원`
          : `${l.price.toLocaleString()}원`,
    }));
  }, [listings]);

  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (slides.length <= 1) return;
    const t = window.setInterval(() => {
      setIndex((i) => (i + 1) % slides.length);
    }, 6500);
    return () => window.clearInterval(t);
  }, [slides.length]);

  const slide = slides[index] ?? slides[0];
  if (!slide) return null;

  return (
    <section className="relative rounded-[2rem] overflow-hidden bg-brand-ink shadow-card-hover isolate">
      <div
        className="flex transition-transform duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{ transform: `translateX(-${index * 100}%)` }}
      >
        {slides.map((s) => (
          <div
            key={s.id}
            className="min-w-full relative aspect-[16/10] sm:aspect-[21/9] lg:aspect-[24/9]"
          >
            <img
              src={s.image}
              alt=""
              className="absolute inset-0 w-full h-full object-cover scale-105"
              onError={(e) => {
                const el = e.currentTarget;
                if (s.fallback && el.src !== s.fallback) el.src = s.fallback;
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-r from-black/75 via-black/40 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />

            <div className="absolute inset-0 flex flex-col justify-end px-6 sm:px-12 lg:px-16 pb-10 sm:pb-14 lg:pb-16">
              <div className="max-w-2xl">
                <p className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold uppercase tracking-[0.2em] text-white/80 mb-4">
                  <span className="h-px w-8 bg-white/50" />
                  {s.eyebrow}
                </p>
                <p className="text-white/85 text-sm sm:text-base font-medium mb-3">
                  {s.location}
                </p>
                <h2 className="display-2 text-white !text-balance drop-shadow-lg">
                  {s.title}
                </h2>
                <p className="mt-4 text-white/90 text-base sm:text-lg max-w-xl leading-relaxed">
                  {s.subtitle}
                </p>
                <div className="mt-7 flex flex-wrap items-center gap-4">
                  <Link
                    to={s.to}
                    className="inline-flex items-center gap-3 rounded-full bg-white text-brand-ink font-bold text-base px-7 py-3.5 no-underline hover:bg-white/95 transition-all shadow-lg active:scale-[0.98]"
                  >
                    바로 예약하기
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-ink text-white text-sm">
                      →
                    </span>
                  </Link>
                  <span className="text-white font-bold text-lg sm:text-xl tabular-nums">
                    {s.price}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {slides.length > 1 && (
        <div className="absolute bottom-6 right-6 sm:right-12 flex items-center gap-3">
          <span className="text-white/70 text-sm font-bold tabular-nums">
            {String(index + 1).padStart(2, "0")}
            <span className="text-white/40 mx-1">/</span>
            {String(slides.length).padStart(2, "0")}
          </span>
          <div className="flex gap-1.5">
            {slides.map((s, i) => (
              <button
                key={s.id}
                type="button"
                aria-label={`${i + 1}번 슬라이드`}
                className={`h-1.5 rounded-full transition-all ${
                  i === index ? "w-10 bg-white" : "w-1.5 bg-white/40 hover:bg-white/70"
                }`}
                onClick={() => setIndex(i)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
