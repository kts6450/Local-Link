const FEATURES = [
  {
    title: "음성으로 등록",
    body: "말하기만 하면 AI가 상품명, 가격, 지역을 자동으로 인식해 등록합니다.",
    icon: "🎙️",
    image:
      "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=600&q=80",
    imageBottom: false,
  },
  {
    title: "손글씨 OCR",
    body: "수기 메모나 손글씨 노트를 촬영하면 자동으로 폼에 채워줍니다.",
    icon: "📷",
    image:
      "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=600&q=80",
    imageBottom: true,
  },
  {
    title: "AI 글쓰기",
    body: "상품 소개글, 이용안내, SNS 홍보글을 AI가 자동으로 생성합니다.",
    icon: "✍️",
    image:
      "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?auto=format&fit=crop&w=600&q=80",
    imageBottom: true,
  },
];

export function LandingFeatures() {
  return (
    <section className="mb-14 sm:mb-20">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-8">
        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-brand-ink leading-snug">
          한 손으로 관리하는
          <br />
          농어촌 마켓플레이스
        </h2>
        <p className="text-hades-muted text-sm sm:text-base max-w-md lg:text-right leading-relaxed">
          AI가 등록부터 홍보까지 도와드립니다.
          <br />
          손가락 하나로 끝내는 스마트 판매 관리
        </p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <article
            key={f.title}
            className="rounded-3xl bg-brand-warm border border-brand-line/80 overflow-hidden flex flex-col"
          >
            {!f.imageBottom && f.image ? (
              <img src={f.image} alt="" className="w-full h-44 object-cover" />
            ) : null}
            <div className="p-6 flex-1 flex flex-col">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-ink text-white text-lg mb-4">
                {f.icon}
              </span>
              <h3 className="font-bold text-lg text-brand-ink">{f.title}</h3>
              <p className="mt-2 text-sm text-hades-muted leading-relaxed flex-1">{f.body}</p>
            </div>
            {f.imageBottom && f.image ? (
              <img src={f.image} alt="" className="w-full h-40 object-cover mt-auto" />
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
