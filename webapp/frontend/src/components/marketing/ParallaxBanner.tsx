/** 랜딩 중간 풀폭 배너 — lsh 브랜치에서 참조만 추가되고 파일이 누락되어 있었음. */
export function ParallaxBanner() {
  return (
    <section className="relative overflow-hidden rounded-[2rem] my-4 sm:my-8">
      <div
        className="relative min-h-[220px] sm:min-h-[280px] bg-cover bg-center bg-fixed"
        style={{
          backgroundImage:
            "url(https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1800&q=85)",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-brand-ink/80 via-brand-ink/55 to-brand-ink/30" />
        <div className="relative z-10 flex flex-col justify-center px-8 sm:px-12 py-12 sm:py-16 max-w-2xl">
          <p className="eyebrow text-white/80 mb-3">Local Link</p>
          <h2 className="text-2xl sm:text-3xl font-bold text-white leading-snug text-balance">
            산지에서 식탁까지,
            <br />
            우리 동네가 바로 마켓
          </h2>
          <p className="mt-3 text-sm sm:text-base text-white/85 leading-relaxed">
            음성·OCR·AI로 쉽게 등록하고, 전국 구매자에게 전해 보세요.
          </p>
        </div>
      </div>
    </section>
  );
}
