const FEATURES = [
  {
    title: "음성으로 등록",
    body: "말하기만 하면 AI가 상품명·가격·지역을 자동으로 인식해 등록합니다. 손가락은 거들 뿐.",
    badge: "01",
    icon: "🎙️",
    image:
      "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=900&q=85",
    accent: "from-emerald-500/20 to-emerald-500/5",
  },
  {
    title: "손글씨 OCR",
    body: "수기 메모나 손글씨 노트를 촬영하면 자동으로 폼에 채워줍니다. Claude Vision이 글씨를 읽어요.",
    badge: "02",
    icon: "📷",
    image:
      "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=900&q=85",
    accent: "from-amber-500/20 to-amber-500/5",
  },
  {
    title: "AI 글쓰기",
    body: "상품 소개·이용안내·SNS 홍보글까지 AI가 톤에 맞게 자동 생성합니다. 사진까지 한 번에.",
    badge: "03",
    icon: "✍️",
    image:
      "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?auto=format&fit=crop&w=900&q=85",
    accent: "from-sky-500/20 to-sky-500/5",
  },
];

export function LandingFeatures() {
  return (
    <section>
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 mb-10 sm:mb-14">
        <div>
          <p className="eyebrow mb-4">Features</p>
          <h2 className="display-2 text-balance">
            한 손으로 관리하는
            <br />
            농어촌 마켓플레이스
          </h2>
        </div>
        <p className="text-base sm:text-lg text-hades-muted max-w-md leading-relaxed">
          AI가 등록부터 홍보까지 도와드립니다.
          <br />
          손가락 하나로 끝내는 스마트 판매 관리.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <article
            key={f.title}
            className="group relative rounded-[1.75rem] overflow-hidden flex flex-col bg-white border border-brand-line/80 shadow-card hover:shadow-card-hover transition-all duration-300 hover:-translate-y-1"
          >
            <div className="relative aspect-[16/10] overflow-hidden">
              <img
                src={f.image}
                alt=""
                className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
              />
              <div className={`absolute inset-0 bg-gradient-to-br ${f.accent} mix-blend-multiply`} />
              <span className="absolute top-5 left-5 text-xs font-bold text-white/90 tracking-[0.2em]">
                {f.badge}
              </span>
              <span className="absolute bottom-5 left-5 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-2xl shadow-lg">
                {f.icon}
              </span>
            </div>
            <div className="p-6 sm:p-7 flex-1 flex flex-col">
              <h3 className="font-bold text-xl sm:text-2xl text-brand-ink tracking-tight">
                {f.title}
              </h3>
              <p className="mt-3 text-base text-hades-muted leading-relaxed flex-1">
                {f.body}
              </p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
