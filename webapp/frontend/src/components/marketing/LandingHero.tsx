import { Link } from "react-router-dom";

export function LandingHero() {
  return (
    <section className="full-bleed relative min-h-[480px] sm:min-h-[560px] lg:min-h-[72vh] overflow-hidden mb-10 sm:mb-14">
      <img
        src="https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=2400&q=85"
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
      />
      <div className="absolute inset-0 bg-gradient-to-r from-black/60 via-black/30 to-black/10" />
      <div className="relative page-shell h-full min-h-[480px] sm:min-h-[560px] lg:min-h-[72vh] flex flex-col justify-between py-14 sm:py-20">
        <div className="max-w-2xl">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-[1.15] tracking-tight">
            음성으로 등록하고,
            <br />
            손은 거들 뿐
          </h1>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6 mt-10">
          <Link
            to="/seller/products"
            className="inline-flex items-center gap-3 bg-white text-brand-ink font-bold rounded-full pl-7 pr-2 py-3 shadow-lg hover:bg-white/95 transition-colors w-fit text-base"
          >
            지금 등록하기
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-ink text-white text-lg">
              →
            </span>
          </Link>
          <p className="text-white/90 text-base sm:text-lg max-w-sm sm:text-right leading-relaxed">
            말하기만 하면 AI가 상품을 만들어드립니다
          </p>
        </div>
      </div>
    </section>
  );
}
