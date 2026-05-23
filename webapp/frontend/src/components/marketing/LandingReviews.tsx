const REVIEWS = [
  {
    name: "김영희",
    role: "홍천 사과농장",
    text: "70대 어머니도 5분이면 등록하세요. 음성으로 말하면 AI가 알아서 채워줘요.",
    stars: 5,
  },
  {
    name: "박철수",
    role: "강릉 갯벌체험",
    text: "주문 관리가 한눈에 보여서 놓치는 게 없어요. 알림톡 초안도 AI가 써줍니다.",
    stars: 5,
  },
  {
    name: "이순자",
    role: "순창 고추장",
    text: "아버지가 사진 찍어서 10분 만에 올리셨어요. OCR이 손글씨도 읽어요.",
    stars: 5,
  },
];

export function LandingReviews() {
  return (
    <section className="mb-14 sm:mb-20 py-10 sm:py-14 rounded-3xl bg-brand-warm/80 border border-brand-line/60">
      <p className="text-center text-xs font-bold tracking-widest text-brand-orange uppercase mb-2">
        Reviews
      </p>
      <h2 className="text-center text-2xl sm:text-3xl font-bold text-brand-ink mb-2">
        이웃 판매자들의 실제 이용 후기
      </h2>
      <p className="text-center text-sm text-hades-muted mb-10">
        전국 농어촌 판매자들의 생생한 이야기
      </p>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 px-2 sm:px-4">
        {REVIEWS.map((r) => (
          <article key={r.name} className="bg-white rounded-2xl p-6 shadow-card">
            <p className="text-brand-orange text-sm mb-3">{"★".repeat(r.stars)}</p>
            <p className="text-sm text-hades-text leading-relaxed">&ldquo;{r.text}&rdquo;</p>
            <div className="mt-5 flex items-center gap-3">
              <span className="h-10 w-10 rounded-full bg-brand-warm flex items-center justify-center text-lg">
                👤
              </span>
              <div>
                <p className="font-bold text-sm">{r.name}</p>
                <p className="text-xs text-hades-muted">{r.role}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
